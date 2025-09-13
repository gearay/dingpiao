import time
import threading
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from queue import Queue

from models import Passenger, TrainInfo, TicketInfo, SeatType, BunkType
from ticket_manager import TicketManager
from auto_booking import AutoBooking, BookingStatus


class BookingTask:
    """预订任务"""
    def __init__(self, ticket_info: TicketInfo, start_time: datetime, 
                 max_retries: int = 3, priority: int = 0):
        self.ticket_info = ticket_info
        self.start_time = start_time
        self.pre_search_start_time = start_time - timedelta(minutes=5)  # 提前5分钟开始查询
        self.max_retries = max_retries
        self.priority = priority
        self.created_at = datetime.now()
        self.status = "pending"
        self.error_message = ""
        self.retry_count = 0
        self.result = None
        self.search_started = False
        self.booking_attempted = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "ticket_info": self.ticket_info.to_dict(),
            "start_time": self.start_time.isoformat(),
            "pre_search_start_time": self.pre_search_start_time.isoformat(),
            "max_retries": self.max_retries,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "result": self.result,
            "search_started": self.search_started,
            "booking_attempted": self.booking_attempted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BookingTask':
        """从字典创建任务对象"""
        ticket_info = TicketInfo.from_dict(data["ticket_info"])
        task = cls(
            ticket_info=ticket_info,
            start_time=datetime.fromisoformat(data["start_time"]),
            max_retries=data["max_retries"],
            priority=data["priority"]
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.status = data["status"]
        task.error_message = data["error_message"]
        task.retry_count = data["retry_count"]
        task.result = data["result"]
        
        # 处理新增字段（向后兼容）
        task.search_started = data.get("search_started", False)
        task.booking_attempted = data.get("booking_attempted", False)
        
        return task


class TimedBooking:
    """定时购票管理器"""
    
    def __init__(self, ticket_manager: TicketManager, headless: bool = False):
        self.ticket_manager = ticket_manager
        self.auto_booking = AutoBooking(ticket_manager, headless)
        self.tasks: list[BookingTask] = []
        self.running = False
        self.worker_thread = None
        self.logger = self._setup_logger()
        self.status_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        
        # 任务队列
        self.task_queue = Queue()
        self.active_tasks: Dict[str, BookingTask] = {}
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("TimedBooking")
        logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler("timed_booking.log", encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        
        return logger
    
    def pre_login(self, username: str = None, password: str = None, 
                  captcha_callback: Optional[Callable] = None) -> bool:
        """预登录（打开浏览器等待人工登录，无车次查询）"""
        try:
            self.logger.info("开始预登录")
            # 直接打开浏览器进行登录，不需要车次信息
            success = self.auto_booking.open_browser_for_login_only()
            if success:
                self.logger.info("预登录成功")
            else:
                self.logger.error("预登录失败")
            return success
        except Exception as e:
            self.logger.error(f"预登录异常: {e}")
            return False
    
    def add_task(self, ticket_info: TicketInfo, start_time: datetime, 
                 max_retries: int = 3, priority: int = 0) -> str:
        """添加预订任务"""
        task = BookingTask(ticket_info, start_time, max_retries, priority)
        self.tasks.append(task)
        
        # 按优先级和开始时间排序
        self.tasks.sort(key=lambda t: (-t.priority, t.start_time))
        
        self.logger.info(f"添加预订任务: {ticket_info.train_info.train_number} at {start_time}")
        return task.created_at.isoformat()
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        for i, task in enumerate(self.tasks):
            if task.created_at.isoformat() == task_id:
                # 如果任务正在运行，先取消
                if task.status == "running":
                    self.auto_booking.cancel_booking()
                
                self.tasks.pop(i)
                self.logger.info(f"移除任务: {task_id}")
                return True
        return False
    
    def get_tasks(self) -> list[BookingTask]:
        """获取所有任务"""
        return self.tasks.copy()
    
    def get_task_by_id(self, task_id: str) -> Optional[BookingTask]:
        """根据ID获取任务"""
        for task in self.tasks:
            if task.created_at.isoformat() == task_id:
                return task
        return None
    
    def start_scheduler(self) -> None:
        """启动调度器"""
        if self.running:
            self.logger.warning("调度器已在运行")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.logger.info("调度器已启动")
    
    def stop_scheduler(self) -> None:
        """停止调度器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消所有正在运行的任务
        for task in self.active_tasks.values():
            if task.status == "running":
                self.auto_booking.cancel_booking()
        
        # 等待工作线程结束
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        self.logger.info("调度器已停止")
    
    def _worker_loop(self) -> None:
        """工作线程循环"""
        while self.running:
            try:
                current_time = datetime.now()
                
                for task in self.tasks:
                    task_key = task.created_at.isoformat()
                    
                    # 检查是否需要开始预搜索（提前5分钟）
                    if (task.status == "pending" and 
                        not task.search_started and
                        current_time >= task.pre_search_start_time and
                        task_key not in self.active_tasks):
                        
                        # 开始预搜索阶段
                        task.search_started = True
                        task.status = "searching"
                        self.active_tasks[task_key] = task
                        
                        # 在新线程中开始预搜索
                        search_thread = threading.Thread(
                            target=self._execute_enhanced_booking,
                            args=(task,),
                            daemon=True
                        )
                        search_thread.start()
                        
                        self.logger.info(f"开始预搜索列车: {task.ticket_info.train_info.train_number} (预定时间: {task.start_time})")
                    
                    # 检查是否到达精确的预定时间（传统模式，向后兼容）
                    elif (task.status == "pending" and 
                           not task.search_started and
                           current_time >= task.start_time and
                           task_key not in self.active_tasks):
                        
                        # 传统模式：直接启动任务
                        self._start_task(task)
                
                # 清理已完成或失败的任务
                self._cleanup_tasks()
                
                # 精确控制循环间隔（毫秒级）
                time.sleep(0.01)  # 10ms检查间隔，确保时间精确
                
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")
                time.sleep(0.1)  # 100ms for faster operation
    
    def _start_task(self, task: BookingTask) -> None:
        """启动任务"""
        task.status = "running"
        self.active_tasks[task.created_at.isoformat()] = task
        
        # 在新线程中执行任务
        task_thread = threading.Thread(
            target=self._execute_task,
            args=(task,),
            daemon=True
        )
        task_thread.start()
        
        self.logger.info(f"启动任务: {task.ticket_info.train_info.train_number}")
    
    def _execute_task(self, task: BookingTask) -> None:
        """执行任务"""
        try:
            task.retry_count = 0
            
            while task.retry_count < task.max_retries:
                try:
                    task.retry_count += 1
                    self.logger.info(f"执行任务 (第{task.retry_count}次): {task.ticket_info.train_info.train_number}")
                    
                    # 执行预订
                    success = self.auto_booking.auto_book_ticket(task.ticket_info)
                    
                    if success:
                        task.status = "completed"
                        task.result = "success"
                        self.logger.info(f"任务完成: {task.ticket_info.train_info.train_number}")
                        
                        if self.status_callback:
                            self.status_callback(task)
                        
                        break
                    else:
                        if task.retry_count >= task.max_retries:
                            task.status = "failed"
                            task.error_message = self.auto_booking.error_message
                            self.logger.error(f"任务失败: {task.ticket_info.train_info.train_number}")
                            
                            if self.error_callback:
                                self.error_callback(task)
                        else:
                            self.logger.warning(f"任务重试中: {task.retry_count}/{task.max_retries}")
                            time.sleep(0.1)  # 100ms for faster operation
                
                except Exception as e:
                    task.error_message = str(e)
                    self.logger.error(f"任务执行异常: {e}")
                    
                    if task.retry_count >= task.max_retries:
                        task.status = "failed"
                        
                        if self.error_callback:
                            self.error_callback(task)
                    else:
                        time.sleep(0.1)  # 100ms for faster operation
        
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.logger.error(f"任务执行失败: {e}")
            
            if self.error_callback:
                self.error_callback(task)
        
        finally:
            # 从活跃任务中移除
            task_id = task.created_at.isoformat()
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    def _execute_enhanced_booking(self, task: BookingTask) -> None:
        """执行增强的定时预订任务"""
        try:
            self.logger.info(f"开始增强预订任务: {task.ticket_info.train_info.train_number}")
            
            # 阶段1: 预搜索阶段（提前5分钟到预定时间）
            pre_search_end_time = task.start_time
            current_time = datetime.now()
            
            if current_time < pre_search_end_time:
                self.logger.info(f"进入预搜索阶段，将在 {pre_search_end_time} 开始正式预订")
                
                # 在预搜索阶段开始时就打开浏览器并登录
                try:
                    self.logger.info("预搜索阶段：打开浏览器并准备登录...")
                    
                    # 提取车票信息
                    from_station = task.ticket_info.train_info.departure_station
                    to_station = task.ticket_info.train_info.arrival_station
                    departure_date = task.ticket_info.train_info.date
                    
                    # 打开浏览器并等待登录
                    login_success = self.auto_booking.open_browser_and_wait_for_login(
                        from_station, to_station, departure_date
                    )
                    
                    if not login_success:
                        self.logger.error("预搜索阶段：浏览器打开或登录失败")
                        task.status = "failed"
                        task.error_message = "预搜索阶段登录失败"
                        return
                    
                    self.logger.info("预搜索阶段：浏览器已打开，用户已登录")
                    
                    # 执行初始查询，获取车次信息
                    search_success = self.auto_booking.search_tickets()
                    if search_success:
                        self.logger.info("预搜索阶段：初始查询成功，车次信息已加载")
                    else:
                        self.logger.warning("预搜索阶段：初始查询失败，将在预定时间重试")
                    
                except Exception as e:
                    self.logger.error(f"预搜索阶段浏览器操作异常: {e}")
                    task.status = "failed"
                    task.error_message = f"预搜索阶段异常: {str(e)}"
                    return
                
                # 持续监控和定期刷新，保持页面活跃
                while current_time < pre_search_end_time and task.status == "searching":
                    try:
                        # 计算距离预定时间还有多久
                        time_remaining = (pre_search_end_time - current_time).total_seconds()
                        
                        if time_remaining > 120:  # 超过2分钟，每30秒刷新一次
                            self.logger.debug(f"距离预定时间还有 {int(time_remaining)} 秒，保持页面活跃")
                            if time_remaining % 30 < 1:  # 每30秒刷新
                                try:
                                    self.auto_booking.search_tickets()
                                    self.logger.debug("预搜索阶段：刷新查询成功")
                                except:
                                    self.logger.debug("预搜索阶段：刷新查询失败")
                            time.sleep(0.1)  # 100ms for faster operation
                        elif time_remaining > 60:  # 1-2分钟，每15秒刷新
                            self.logger.debug(f"即将开始预订，还有 {int(time_remaining)} 秒")
                            if time_remaining % 15 < 1:  # 每15秒刷新
                                try:
                                    self.auto_booking.search_tickets()
                                    self.logger.debug("预搜索阶段：高频刷新查询成功")
                                except:
                                    self.logger.debug("预搜索阶段：高频刷新查询失败")
                            time.sleep(0.1)  # 100ms for faster operation
                        elif time_remaining > 10:  # 10-60秒，每5秒刷新
                            self.logger.debug(f"即将开始预订，还有 {int(time_remaining)} 秒")
                            if time_remaining % 5 < 1:  # 每5秒刷新
                                try:
                                    self.auto_booking.search_tickets()
                                    self.logger.debug("预搜索阶段：超高频刷新查询成功")
                                except:
                                    self.logger.debug("预搜索阶段：超高频刷新查询失败")
                            time.sleep(0.05)  # 50ms for faster operation
                        else:  # 最后10秒，准备精确点击
                            self.logger.info(f"最后倒计时：{int(time_remaining * 1000)} 毫秒")
                            if time_remaining > 3:  # 3-10秒，每2秒刷新
                                time.sleep(0.05)  # 50ms for faster operation
                                try:
                                    self.auto_booking.search_tickets()
                                except:
                                    pass
                            else:  # 最后3秒，精确等待
                                time.sleep(0.01)  # 10ms检查间隔
                        
                        current_time = datetime.now()
                        
                    except Exception as e:
                        self.logger.warning(f"预搜索阶段监控异常: {e}")
                        time.sleep(0.05)  # 50ms for faster operation
            
            # 阶段2: 精确时间点开始预订
            if task.status != "searching":
                return  # 任务被取消或已结束
            
            # 精确时间同步：确保在准确的时间点开始
            final_wait_time = (pre_search_end_time - datetime.now()).total_seconds()
            if final_wait_time > 0:
                self.logger.info(f"精确等待 {final_wait_time:.3f} 秒到预定时间...")
                time.sleep(final_wait_time)
            
            # 记录实际开始时间
            actual_start_time = datetime.now()
            time_offset = (actual_start_time - task.start_time).total_seconds()
            
            self.logger.info(f"到达预定时间，开始精确预订: {task.ticket_info.train_info.train_number} "
                           f"(时间偏移: {time_offset:+.3f}秒)")
            task.status = "booking"
            task.booking_attempted = True
            
            # 在开始预订前最后一次刷新查询，确保数据最新
            try:
                self.logger.info("预订前最后一次刷新查询...")
                self.auto_booking.search_tickets()
            except Exception as e:
                self.logger.warning(f"预订前刷新失败: {e}")
            
            # 阶段3: 不规则间隔重试机制
            task.retry_count = 0
            
            while task.retry_count < task.max_retries and task.status == "booking":
                try:
                    task.retry_count += 1
                    
                    # 精确时间戳记录
                    attempt_time = datetime.now()
                    time_diff = (attempt_time - task.start_time).total_seconds()
                    
                    self.logger.info(f"预订尝试 (第{task.retry_count}次): {task.ticket_info.train_info.train_number} "
                                   f"(时间偏移: +{time_diff:.3f}秒)")
                    
                    # 执行预订
                    success = self.auto_booking.auto_book_ticket(task.ticket_info)
                    
                    if success:
                        task.status = "completed"
                        task.result = "success"
                        final_time = datetime.now()
                        total_time = (final_time - task.start_time).total_seconds()
                        
                        self.logger.info(f"预订成功! {task.ticket_info.train_info.train_number} "
                                       f"(总耗时: {total_time:.3f}秒, 重试次数: {task.retry_count})")
                        
                        if self.status_callback:
                            self.status_callback(task)
                        
                        break
                    else:
                        if task.retry_count >= task.max_retries:
                            task.status = "failed"
                            task.error_message = self.auto_booking.error_message
                            self.logger.error(f"预订失败: {task.ticket_info.train_info.train_number} "
                                           f"(错误: {task.error_message})")
                            
                            if self.error_callback:
                                self.error_callback(task)
                        else:
                            # 预订失败后，先重新查询再重试
                            self.logger.info(f"预订失败，重新查询车次信息...")
                            
                            # 执行重新查询
                            try:
                                refresh_success = self.auto_booking.search_tickets()
                                if refresh_success:
                                    self.logger.info(f"重新查询成功，准备第{task.retry_count + 1}次预订尝试")
                                else:
                                    self.logger.warning(f"重新查询失败，但仍将继续尝试预订")
                            except Exception as refresh_e:
                                self.logger.warning(f"重新查询异常: {refresh_e}，继续预订尝试")
                            
                            # 不规则毫秒间隔重试
                            if task.retry_count == 1:
                                # 第一次失败：等待100-300ms
                                wait_time = random.uniform(0.1, 0.3)
                            elif task.retry_count == 2:
                                # 第二次失败：等待200-500ms
                                wait_time = random.uniform(0.2, 0.5)
                            else:
                                # 后续失败：等待500-1000ms
                                wait_time = random.uniform(0.5, 1.0)
                            
                            self.logger.info(f"{wait_time*1000:.0f}ms后进行第{task.retry_count + 1}次预订尝试...")
                            time.sleep(wait_time)
                
                except Exception as e:
                    task.retry_count += 1
                    self.logger.error(f"预订尝试异常 (第{task.retry_count}次): {e}")
                    
                    if task.retry_count >= task.max_retries:
                        task.status = "failed"
                        task.error_message = str(e)
                        self.logger.error(f"预订最终失败: {task.ticket_info.train_info.train_number}")
                        
                        if self.error_callback:
                            self.error_callback(task)
                        break
                    else:
                        # 异常后的不规则等待
                        wait_time = random.uniform(0.3, 0.8)
                        self.logger.info(f"异常后等待{wait_time*1000:.0f}ms重试...")
                        time.sleep(wait_time)
        
        except Exception as e:
            self.logger.error(f"增强预订任务异常: {e}")
            task.status = "failed"
            task.error_message = str(e)
        
        finally:
            # 从活跃任务中移除
            task_key = task.created_at.isoformat()
            if task_key in self.active_tasks:
                del self.active_tasks[task_key]
    
    def _cleanup_tasks(self) -> None:
        """清理任务"""
        # 移除已完成且超过24小时的任务
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        self.tasks = [
            task for task in self.tasks 
            if not (task.status in ["completed", "failed"] and 
                   task.created_at < cutoff_time)
        ]
    
    def set_status_callback(self, callback: Callable[[BookingTask], None]) -> None:
        """设置状态回调"""
        self.status_callback = callback
    
    def set_error_callback(self, callback: Callable[[BookingTask], None]) -> None:
        """设置错误回调"""
        self.error_callback = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_tasks = len(self.tasks)
        pending_tasks = len([t for t in self.tasks if t.status == "pending"])
        searching_tasks = len([t for t in self.tasks if t.status == "searching"])
        booking_tasks = len([t for t in self.tasks if t.status == "booking"])
        running_tasks = len([t for t in self.tasks if t.status == "running"])
        completed_tasks = len([t for t in self.tasks if t.status == "completed"])
        failed_tasks = len([t for t in self.tasks if t.status == "failed"])
        
        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "searching_tasks": searching_tasks,  # 预搜索中
            "booking_tasks": booking_tasks,      # 预订中
            "running_tasks": running_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "active_tasks": len(self.active_tasks),
            "scheduler_running": self.running,
            "auto_booking_status": self.auto_booking.get_status()
        }
    
    def cancel_all_tasks(self) -> None:
        """取消所有任务"""
        for task in self.tasks:
            if task.status in ["running", "searching", "booking"]:
                task.status = "cancelled"
        
        self.auto_booking.cancel_booking()
        self.logger.info("已取消所有任务")
    
    def cancel_task(self, task_identifier: str) -> bool:
        """取消指定任务"""
        try:
            # 支持多种标识符：车次、创建时间、索引
            cancelled_task = None
            
            for task in self.tasks:
                # 检查车次匹配
                if task.ticket_info.train_info.train_number == task_identifier:
                    cancelled_task = task
                    break
                # 检查创建时间匹配
                elif task.created_at.isoformat() == task_identifier:
                    cancelled_task = task
                    break
            
            if cancelled_task and cancelled_task.status in ["pending", "searching", "booking", "running"]:
                original_status = cancelled_task.status
                cancelled_task.status = "cancelled"
                
                # 根据任务状态进行不同的清理操作
                if original_status in ["searching", "booking", "running"]:
                    # 取消自动预订操作
                    self.auto_booking.cancel_booking()
                    self.logger.info(f"已取消{original_status}状态的任务: {cancelled_task.ticket_info.train_info.train_number}")
                else:
                    self.logger.info(f"已取消待处理任务: {cancelled_task.ticket_info.train_info.train_number}")
                
                # 从活跃任务中移除
                task_key = cancelled_task.created_at.isoformat()
                if task_key in self.active_tasks:
                    del self.active_tasks[task_key]
                
                return True
            else:
                self.logger.warning(f"未找到可取消的任务: {task_identifier}")
                return False
                
        except Exception as e:
            self.logger.error(f"取消任务时出错: {e}")
            return False
    
    def pause_scheduler(self) -> None:
        """暂停调度器"""
        self.running = False
        self.logger.info("调度器已暂停")
    
    def resume_scheduler(self) -> None:
        """恢复调度器"""
        if not self.running:
            self.running = True
            if not self.worker_thread or not self.worker_thread.is_alive():
                self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                self.worker_thread.start()
            self.logger.info("调度器已恢复")
    
    def get_next_task_time(self) -> Optional[datetime]:
        """获取下一个任务的时间"""
        pending_tasks = [t for t in self.tasks if t.status == "pending"]
        if not pending_tasks:
            return None
        
        return min(task.start_time for task in pending_tasks)
    
    def validate_task_time(self, start_time: datetime) -> bool:
        """验证任务时间"""
        now = datetime.now()
        
        # 任务时间不能是过去时间
        if start_time <= now:
            return False
        
        # 任务时间不能太远（限制在30天内）
        if start_time > now + timedelta(days=30):
            return False
        
        return True
    
    def close(self) -> None:
        """关闭定时购票管理器"""
        self.stop_scheduler()
        self.auto_booking.close()
        self.logger.info("定时购票管理器已关闭")