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
    
    def set_status_callback(self, callback: Optional[Callable]) -> None:
        """设置状态回调函数"""
        self.status_callback = callback
    
    def set_error_callback(self, callback: Optional[Callable]) -> None:
        """设置错误回调函数"""
        self.error_callback = callback
    
    def validate_task_time(self, start_time: datetime) -> bool:
        """验证任务时间是否有效"""
        try:
            # 检查时间是否在未来
            current_time = datetime.now()
            if start_time <= current_time:
                self.logger.warning(f"任务时间 {start_time} 必须在未来，当前时间 {current_time}")
                return False
            
            # 检查时间是否太远（比如超过30天）
            max_days = 30
            if (start_time - current_time).days > max_days:
                self.logger.warning(f"任务时间 {start_time} 超过 {max_days} 天限制")
                return False
            
            self.logger.info(f"任务时间验证通过: {start_time}")
            return True
            
        except Exception as e:
            self.logger.error(f"验证任务时间时发生异常: {e}")
            return False
    
    def pre_login(self, username: str = None, password: str = None, 
                  captcha_callback: Optional[Callable] = None) -> bool:
        """预登录（打开浏览器等待人工登录，无车次查询）"""
        try:
            self.logger.info("开始预登录")
            # 直接打开浏览器进行登录，不需要车次信息
            success = self.auto_booking.open_browser_and_wait_for_login()
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
        """执行简化的定时预订任务"""
        try:
            self.logger.info(f"开始预订任务: {task.ticket_info.train_info.train_number}")
            
            target_time = task.start_time
            current_time = datetime.now()
            
            self.logger.info(f"当前时间: {current_time}, 预定时间: {target_time}")
            
            # 计算真正的预登录开始时间（预定时间前2分钟）
            pre_login_time = target_time - timedelta(minutes=2)
            
            # 如果当前时间早于预登录时间，先等待
            if current_time < pre_login_time:
                wait_time = (pre_login_time - current_time).total_seconds()
                self.logger.info(f"距离预登录时间还有 {wait_time:.1f} 秒，等待中...")
                time.sleep(wait_time)
            
            # 预登录阶段（预定时间前2分钟开始）
            if datetime.now() < target_time:
                self.logger.info("开始预登录阶段...")
                
                # 打开浏览器并等待登录
                login_success = self.auto_booking.open_browser_and_wait_for_login()
                if not login_success:
                    self.logger.error("浏览器打开或登录失败")
                    task.status = "failed"
                    task.error_message = "登录失败"
                    return
                
                self.logger.info("浏览器已打开，用户已登录")
                
                # 预定时间前1分钟填充搜索表单
                pre_fill_time = target_time - timedelta(minutes=1)
                if datetime.now() < pre_fill_time:
                    wait_time = (pre_fill_time - datetime.now()).total_seconds()
                    self.logger.info(f"等待 {wait_time:.1f} 秒到填充搜索表单时间...")
                    time.sleep(wait_time)
                
                # 填充搜索表单
                try:
                    self.auto_booking._fill_search_form(
                        task.ticket_info.train_info.departure_station,
                        task.ticket_info.train_info.arrival_station,
                        task.ticket_info.train_info.date
                    )
                    self.logger.info("搜索表单填充完成")
                except Exception as e:
                    self.logger.error(f"填充搜索表单失败: {e}")
                    task.status = "failed"
                    task.error_message = f"填充表单异常: {str(e)}"
                    return
                
                # 等待到预定时间前5秒进行查询
                pre_query_time = target_time - timedelta(seconds=5)
                if datetime.now() < pre_query_time:
                    wait_time = (pre_query_time - datetime.now()).total_seconds()
                    self.logger.info(f"等待 {wait_time:.1f} 秒到预查询时间...")
                    time.sleep(wait_time)
                
                # 预定时间前5秒进行查询
                try:
                    self.logger.info("进行预查询...")
                    if not self.auto_booking.search_tickets():
                        self.logger.error("车票查询失败")
                        task.status = "failed"
                        task.error_message = "查询失败"
                        return
                    self.logger.info("预查询成功")
                except Exception as e:
                    self.logger.error(f"预查询失败: {e}")
                    task.status = "failed"
                    task.error_message = f"预查询异常: {str(e)}"
                    return
                
                # 等待到精确的预定时间
                final_wait_time = (target_time - datetime.now()).total_seconds()
                if final_wait_time > 0:
                    self.logger.info(f"最后等待 {final_wait_time:.1f} 秒到预定时间...")
                    time.sleep(final_wait_time)
            
            # 到达预定时间，开始预订
            actual_start_time = datetime.now()
            time_offset = (actual_start_time - target_time).total_seconds()
            self.logger.info(f"🎯 到达预定时间，开始预订: {task.ticket_info.train_info.train_number} (时间偏移: {time_offset:+.3f}秒)")
            
            # 执行预订步骤
            self._execute_booking_steps(task, target_time)
            
        except Exception as e:
            self.logger.error(f"预订任务异常: {e}")
            task.status = "failed"
            task.error_message = str(e)
            
            if self.error_callback:
                self.error_callback(task)
    
    def _execute_booking_steps(self, task: BookingTask, target_time: datetime) -> None:
        """执行预订步骤"""
        try:
            # 如果浏览器还没有打开，先打开并登录
            if not self.auto_booking.driver or not self.auto_booking.driver.current_url:
                login_success = self.auto_booking.open_browser_and_wait_for_login()
                if not login_success:
                    self.logger.error("浏览器打开或登录失败")
                    task.status = "failed"
                    task.error_message = "登录失败"
                    return
            
            # 执行预订步骤
            self.logger.info("开始执行预订步骤...")
            task.status = "booking"
            
            # 重试机制
            max_retries = 3
            for retry in range(max_retries):
                try:
                    retry_start_time = datetime.now()
                    retry_offset = (retry_start_time - target_time).total_seconds()
                    self.logger.info(f"预订尝试 (第{retry + 1}次): 时间偏移 {retry_offset:+.3f}秒")
                    
                    # 选择车次
                    if not self.auto_booking.select_train(task.ticket_info.train_info.train_number):
                        self.logger.warning("选择车次失败，等待外部重试...")
                        time.sleep(0.5)  # 外部重试间隔500ms
                        continue
                    
                    # 选择乘客和座位
                    if not self.auto_booking.select_passengers_and_seats(task.ticket_info):
                        self.logger.warning("选择乘客和座位失败")
                        time.sleep(0.01)
                        continue
                    
                    # 提交订单
                    if not self.auto_booking.submit_order():
                        self.logger.warning("提交订单失败")
                        time.sleep(0.01)
                        continue
                    
                    # 确认订单
                    if not self.auto_booking.confirm_order():
                        self.logger.warning("确认订单失败")
                        time.sleep(0.01)
                        continue
                    
                    # 预订成功
                    task.status = "completed"
                    task.result = "success"
                    
                    final_time = datetime.now()
                    total_time = (final_time - target_time).total_seconds()
                    
                    self.logger.info(f"预订成功! {task.ticket_info.train_info.train_number} "
                                   f"(总耗时: {total_time:.3f}秒, 重试次数: {retry + 1})")
                    
                    if self.status_callback:
                        self.status_callback(task)
                    
                    return
                    
                except Exception as e:
                    self.logger.warning(f"预订步骤执行失败: {e}")
                    time.sleep(0.01)
            
            # 所有重试都失败
            task.status = "failed"
            task.error_message = f"预订失败，已重试{max_retries}次"
            self.logger.error(f"预订失败: {task.ticket_info.train_info.train_number} - {task.error_message}")
            
            if self.error_callback:
                self.error_callback(task)
                
        except Exception as e:
            self.logger.error(f"预订步骤异常: {e}")
            task.status = "failed"
            task.error_message = str(e)
            
            if self.error_callback:
                self.error_callback(task)
