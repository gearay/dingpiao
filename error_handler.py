import time
import logging
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timedelta

from models import TicketInfo
from auto_booking import AutoBooking


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "网络错误"
    LOGIN_ERROR = "登录错误"
    CAPTCHA_ERROR = "验证码错误"
    NO_TICKET_ERROR = "无票错误"
    SEAT_ERROR = "席次错误"
    PASSENGER_ERROR = "乘客错误"
    SUBMIT_ERROR = "提交错误"
    PAYMENT_ERROR = "支付错误"
    SYSTEM_ERROR = "系统错误"
    UNKNOWN_ERROR = "未知错误"


class UserChoice(Enum):
    """用户选择枚举"""
    RETRY = "重试"
    MANUAL_BOOKING = "手动预订"
    SKIP_TASK = "跳过任务"
    CANCEL_ALL = "取消所有"
    WAIT_AND_RETRY = "等待后重试"
    CHANGE_STRATEGY = "改变策略"


class ErrorHandler:
    """错误处理器 - 提供错误处理和用户选择机制"""
    
    def __init__(self, auto_booking: AutoBooking):
        self.auto_booking = auto_booking
        self.logger = self._setup_logger()
        self.error_history: List[Dict[str, Any]] = []
        self.max_retry_count = 3
        self.retry_delay = 5
        self.user_callback: Optional[Callable[[ErrorType, str], UserChoice]] = None
        
        # 错误类型对应的默认策略
        self.default_strategies = {
            ErrorType.NETWORK_ERROR: UserChoice.RETRY,
            ErrorType.LOGIN_ERROR: UserChoice.MANUAL_BOOKING,
            ErrorType.CAPTCHA_ERROR: UserChoice.MANUAL_BOOKING,
            ErrorType.NO_TICKET_ERROR: UserChoice.WAIT_AND_RETRY,
            ErrorType.SEAT_ERROR: UserChoice.CHANGE_STRATEGY,
            ErrorType.PASSENGER_ERROR: UserChoice.MANUAL_BOOKING,
            ErrorType.SUBMIT_ERROR: UserChoice.RETRY,
            ErrorType.PAYMENT_ERROR: UserChoice.MANUAL_BOOKING,
            ErrorType.SYSTEM_ERROR: UserChoice.CANCEL_ALL,
            ErrorType.UNKNOWN_ERROR: UserChoice.RETRY
        }
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("ErrorHandler")
        logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler("error_handler.log", encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        
        return logger
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> UserChoice:
        """处理错误"""
        # 分析错误类型
        error_type = self._analyze_error(error)
        
        # 记录错误
        self._log_error(error, error_type, context)
        
        # 获取用户选择
        user_choice = self._get_user_choice(error_type, str(error))
        
        # 执行相应的处理策略
        self._execute_strategy(user_choice, error_type, error)
        
        return user_choice
    
    def _analyze_error(self, error: Exception) -> ErrorType:
        """分析错误类型"""
        error_message = str(error).lower()
        
        # 网络错误
        if any(keyword in error_message for keyword in [
            "network", "connection", "timeout", "unreachable", "dns"
        ]):
            return ErrorType.NETWORK_ERROR
        
        # 登录错误
        elif any(keyword in error_message for keyword in [
            "login", "authentication", "username", "password", "session"
        ]):
            return ErrorType.LOGIN_ERROR
        
        # 验证码错误
        elif any(keyword in error_message for keyword in [
            "captcha", "verification", "code", "图片", "验证码"
        ]):
            return ErrorType.CAPTCHA_ERROR
        
        # 无票错误
        elif any(keyword in error_message for keyword in [
            "no ticket", "sold out", "无票", "售完", "ticket not available"
        ]):
            return ErrorType.NO_TICKET_ERROR
        
        # 席次错误
        elif any(keyword in error_message for keyword in [
            "seat", "席次", "座位", "berth", "铺位"
        ]):
            return ErrorType.SEAT_ERROR
        
        # 乘客错误
        elif any(keyword in error_message for keyword in [
            "passenger", "乘客", "id card", "身份证", "name"
        ]):
            return ErrorType.PASSENGER_ERROR
        
        # 提交错误
        elif any(keyword in error_message for keyword in [
            "submit", "提交", "order", "订单"
        ]):
            return ErrorType.SUBMIT_ERROR
        
        # 支付错误
        elif any(keyword in error_message for keyword in [
            "payment", "支付", "pay", "结算"
        ]):
            return ErrorType.PAYMENT_ERROR
        
        # 系统错误
        elif any(keyword in error_message for keyword in [
            "system", "server", "internal", "系统", "服务器", "内部错误"
        ]):
            return ErrorType.SYSTEM_ERROR
        
        # 未知错误
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def _log_error(self, error: Exception, error_type: ErrorType, 
                   context: Optional[Dict[str, Any]] = None) -> None:
        """记录错误"""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type.value,
            "error_message": str(error),
            "context": context or {},
            "auto_booking_status": self.auto_booking.get_status()
        }
        
        self.error_history.append(error_record)
        self.logger.error(f"{error_type.value}: {error}")
    
    def _get_user_choice(self, error_type: ErrorType, error_message: str) -> UserChoice:
        """获取用户选择"""
        if self.user_callback:
            try:
                return self.user_callback(error_type, error_message)
            except Exception as e:
                self.logger.error(f"用户回调失败: {e}")
        
        # 使用默认策略
        return self.default_strategies.get(error_type, UserChoice.RETRY)
    
    def _execute_strategy(self, choice: UserChoice, error_type: ErrorType, 
                         error: Exception) -> None:
        """执行处理策略"""
        self.logger.info(f"执行策略: {choice.value}")
        
        if choice == UserChoice.RETRY:
            self._retry_strategy()
        elif choice == UserChoice.MANUAL_BOOKING:
            self._manual_booking_strategy(error_type)
        elif choice == UserChoice.SKIP_TASK:
            self._skip_task_strategy()
        elif choice == UserChoice.CANCEL_ALL:
            self._cancel_all_strategy()
        elif choice == UserChoice.WAIT_AND_RETRY:
            self._wait_and_retry_strategy(error_type)
        elif choice == UserChoice.CHANGE_STRATEGY:
            self._change_strategy_strategy(error_type)
    
    def _retry_strategy(self) -> None:
        """重试策略"""
        self.logger.info("执行重试策略")
        # 等待一段时间后重试
        time.sleep(self.retry_delay)
    
    def _manual_booking_strategy(self, error_type: ErrorType) -> None:
        """手动预订策略"""
        self.logger.info(f"切换到手动预订模式 - 错误类型: {error_type.value}")
        # 取消自动预订，提示用户手动处理
        self.auto_booking.cancel_booking()
    
    def _skip_task_strategy(self) -> None:
        """跳过任务策略"""
        self.logger.info("跳过当前任务")
        self.auto_booking.cancel_booking()
    
    def _cancel_all_strategy(self) -> None:
        """取消所有任务策略"""
        self.logger.info("取消所有任务")
        self.auto_booking.cancel_booking()
    
    def _wait_and_retry_strategy(self, error_type: ErrorType) -> None:
        """等待后重试策略"""
        wait_time = self._calculate_wait_time(error_type)
        self.logger.info(f"等待 {wait_time} 秒后重试")
        time.sleep(wait_time)
    
    def _change_strategy_strategy(self, error_type: ErrorType) -> None:
        """改变策略策略"""
        self.logger.info(f"改变预订策略 - 错误类型: {error_type.value}")
        # 根据错误类型调整策略
        if error_type == ErrorType.SEAT_ERROR:
            self.logger.info("建议尝试其他席次类型")
        elif error_type == ErrorType.NO_TICKET_ERROR:
            self.logger.info("建议尝试其他车次或日期")
    
    def _calculate_wait_time(self, error_type: ErrorType) -> int:
        """计算等待时间"""
        wait_times = {
            ErrorType.NETWORK_ERROR: 10,
            ErrorType.NO_TICKET_ERROR: 30,
            ErrorType.SEAT_ERROR: 5,
            ErrorType.SUBMIT_ERROR: 15,
            ErrorType.UNKNOWN_ERROR: 10
        }
        return wait_times.get(error_type, self.retry_delay)
    
    def set_user_callback(self, callback: Callable[[ErrorType, str], UserChoice]) -> None:
        """设置用户回调函数"""
        self.user_callback = callback
    
    def set_retry_config(self, max_retry_count: int, retry_delay: int) -> None:
        """设置重试配置"""
        self.max_retry_count = max_retry_count
        self.retry_delay = retry_delay
    
    def set_default_strategy(self, error_type: ErrorType, strategy: UserChoice) -> None:
        """设置默认策略"""
        self.default_strategies[error_type] = strategy
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        if not self.error_history:
            return {"total_errors": 0}
        
        error_type_count = {}
        for record in self.error_history:
            error_type = record["error_type"]
            error_type_count[error_type] = error_type_count.get(error_type, 0) + 1
        
        recent_errors = [
            record for record in self.error_history
            if datetime.fromisoformat(record["timestamp"]) > datetime.now() - timedelta(hours=24)
        ]
        
        return {
            "total_errors": len(self.error_history),
            "error_type_distribution": error_type_count,
            "recent_errors_24h": len(recent_errors),
            "last_error": self.error_history[-1] if self.error_history else None
        }
    
    def clear_error_history(self) -> None:
        """清空错误历史"""
        self.error_history.clear()
        self.logger.info("错误历史已清空")
    
    def save_error_report(self, filename: str) -> bool:
        """保存错误报告"""
        try:
            import json
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "statistics": self.get_error_statistics(),
                "error_history": self.error_history
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"错误报告已保存到: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存错误报告失败: {e}")
            return False
    
    def should_retry(self, error_type: ErrorType, retry_count: int) -> bool:
        """判断是否应该重试"""
        if retry_count >= self.max_retry_count:
            return False
        
        # 某些错误类型不建议重试
        no_retry_types = [
            ErrorType.LOGIN_ERROR,
            ErrorType.CAPTCHA_ERROR,
            ErrorType.PASSENGER_ERROR,
            ErrorType.SYSTEM_ERROR
        ]
        
        return error_type not in no_retry_types
    
    def get_recovery_suggestions(self, error_type: ErrorType) -> List[str]:
        """获取恢复建议"""
        suggestions = {
            ErrorType.NETWORK_ERROR: [
                "检查网络连接",
                "稍后重试",
                "尝试使用代理或VPN"
            ],
            ErrorType.LOGIN_ERROR: [
                "检查用户名和密码",
                "手动登录12306网站",
                "确认账号状态正常"
            ],
            ErrorType.CAPTCHA_ERROR: [
                "手动输入验证码",
                "检查验证码图片显示",
                "尝试刷新验证码"
            ],
            ErrorType.NO_TICKET_ERROR: [
                "尝试其他车次",
                "尝试其他日期",
                "选择其他席次类型"
            ],
            ErrorType.SEAT_ERROR: [
                "检查席次选择是否正确",
                "尝试其他席次类型",
                "确认乘客信息完整"
            ],
            ErrorType.PASSENGER_ERROR: [
                "检查乘客信息",
                "确认身份证号正确",
                "添加乘客到12306账号"
            ],
            ErrorType.SUBMIT_ERROR: [
                "检查订单信息",
                "稍后重试",
                "尝试清除浏览器缓存"
            ],
            ErrorType.PAYMENT_ERROR: [
                "检查支付方式",
                "确认账户余额",
                "联系客服处理"
            ],
            ErrorType.SYSTEM_ERROR: [
                "等待系统恢复",
                "查看12306公告",
                "稍后重试"
            ],
            ErrorType.UNKNOWN_ERROR: [
                "记录错误信息",
                "联系技术支持",
                "尝试重启程序"
            ]
        }
        
        return suggestions.get(error_type, ["联系技术支持"])
    
    def create_error_report(self) -> Dict[str, Any]:
        """创建错误报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "auto_booking_status": self.auto_booking.get_status(),
            "statistics": self.get_error_statistics(),
            "suggestions": {
                error_type.value: self.get_recovery_suggestions(error_type)
                for error_type in ErrorType
            }
        }