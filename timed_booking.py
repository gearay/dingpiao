import time
import threading
import logging
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
        self.max_retries = max_retries
        self.priority = priority
        self.created_at = datetime.now()
        self.status = "pending"
        self.error_message = ""
        self.retry_count = 0
        self.result = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "ticket_info": self.ticket_info.to_dict(),
            "start_time": self.start_time.isoformat(),
            "max_retries": self.max_retries,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "result": self.result
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
    
    def pre_login(self, username: str, password: str, 
                  captcha_callback: Optional[Callable] = None) -> bool:
        """预登录（现在改为打开浏览器等待人工登录）"""
        try:
            self.logger.info("开始预登录")
            # 获取一个示例车票信息来打开浏览器
            tickets = self.ticket_manager.get_tickets()
            if tickets:
                # 使用第一个车票信息打开浏览器
                ticket = tickets[0]
                success = self.auto_booking.open_browser_and_wait_for_login(
                    ticket.train_info.departure_station,
                    ticket.train_info.arrival_station,
                    ticket.train_info.date
                )
                if success:
                    self.logger.info("预登录成功")
                else:
                    self.logger.error("预登录失败")
                return success
            else:
                self.logger.error("没有可用的车票信息进行预登录")
                return False
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
                # 检查是否有任务需要执行
                current_time = datetime.now()
                
                for task in self.tasks:
                    if (task.status == "pending" and 
                        current_time >= task.start_time and
                        task.created_at.isoformat() not in self.active_tasks):
                        
                        # 启动任务
                        self._start_task(task)
                
                # 清理已完成或失败的任务
                self._cleanup_tasks()
                
                # 等待一段时间
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")
                time.sleep(5)
    
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
                            time.sleep(5)
                
                except Exception as e:
                    task.error_message = str(e)
                    self.logger.error(f"任务执行异常: {e}")
                    
                    if task.retry_count >= task.max_retries:
                        task.status = "failed"
                        
                        if self.error_callback:
                            self.error_callback(task)
                    else:
                        time.sleep(5)
        
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
        running_tasks = len([t for t in self.tasks if t.status == "running"])
        completed_tasks = len([t for t in self.tasks if t.status == "completed"])
        failed_tasks = len([t for t in self.tasks if t.status == "failed"])
        
        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
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
            if task.status == "running":
                task.status = "cancelled"
        
        self.auto_booking.cancel_booking()
        self.logger.info("已取消所有任务")
    
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