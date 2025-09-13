from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class SeatType(Enum):
    """席次类别枚举"""
    SECOND_CLASS = "二等座"
    FIRST_CLASS = "一等座"
    BUSINESS_CLASS = "商务座"
    HARD_SEAT = "硬座"
    SOFT_SEAT = "软座"
    NO_SEAT = "无座"
    HARD_SLEEPER = "硬卧"
    SOFT_SLEEPER = "软卧"
    DYNAMIC_SLEEPER = "动卧"
    FIRST_SLEEPER = "一等卧"
    SECOND_SLEEPER = "二等卧"
    ADVANCED_SOFT_SLEEPER = "高级软卧"


class BunkType(Enum):
    """铺位类型枚举"""
    UPPER_BUNK = "上铺"
    MIDDLE_BUNK = "中铺"
    LOWER_BUNK = "下铺"
    NO_BUNK = "无"


@dataclass
class Passenger:
    """乘客信息 - 适配12306自动购票系统"""
    name: str
    id_type: str = "二代身份证"
    id_number: str = ""
    mobile: str = ""
    email: str = ""
    seat_type: SeatType = SeatType.SECOND_CLASS
    bunk_type: Optional[BunkType] = None
    ticket_type: str = "成人票"
    passenger_type: str = "成人"
    
    def __post_init__(self):
        """初始化后验证，确保关键字段不为空"""
        if not self.name or not self.name.strip():
            raise ValueError("乘客姓名不能为空")
        if not self.seat_type:
            self.seat_type = SeatType.SECOND_CLASS
        if not self.ticket_type or not self.ticket_type.strip():
            self.ticket_type = "成人票"
        if not self.passenger_type or not self.passenger_type.strip():
            self.passenger_type = "成人"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "name": self.name,
            "id_type": self.id_type,
            "id_number": self.id_number,
            "mobile": self.mobile,
            "email": self.email,
            "ticket_type": self.ticket_type,
            "passenger_type": self.passenger_type,
            "seat_type": self.seat_type.value,
        }
        if self.bunk_type:
            result["bunk_type"] = self.bunk_type.value
        return result
    
    def get_booking_info(self) -> Dict[str, Any]:
        """获取自动购票所需的信息"""
        return {
            "name": self.name,
            "seat_type": self.seat_type,
            "ticket_type": self.ticket_type,
            "bunk_type": self.bunk_type,
            "passenger_type": self.passenger_type,
            "id_number": self.id_number,
            "mobile": self.mobile
        }
    
    def has_valid_booking_info(self) -> bool:
        """检查是否有有效的购票信息"""
        return bool(
            self.name and self.name.strip() and
            self.seat_type and
            self.ticket_type and self.ticket_type.strip() and
            self.id_number and self.id_number.strip()
        )
    
    def get_seat_display_name(self) -> str:
        """获取席次显示名称"""
        if hasattr(self.seat_type, 'value'):
            return self.seat_type.value
        return str(self.seat_type or "二等座")
    
    def get_bunk_display_name(self) -> str:
        """获取铺位显示名称"""
        if self.bunk_type and hasattr(self.bunk_type, 'value'):
            return self.bunk_type.value
        return "无"
    
    def needs_bunk_selection(self) -> bool:
        """检查是否需要选择铺位"""
        if not self.seat_type:
            return False
        seat_name = self.get_seat_display_name()
        return "卧" in seat_name and not self.bunk_type
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Passenger':
        """从字典创建乘客对象"""
        seat_type = SeatType(data.get("seat_type", "二等座"))
        bunk_type = None
        if "bunk_type" in data:
            bunk_type = BunkType(data["bunk_type"])
        
        return cls(
            name=data["name"],
            id_type=data.get("id_type", "二代身份证"),
            id_number=data.get("id_number", ""),
            mobile=data.get("mobile", ""),
            email=data.get("email", ""),
            seat_type=seat_type,
            bunk_type=bunk_type,
            ticket_type=data.get("ticket_type", "成人票"),
            passenger_type=data.get("passenger_type", "成人")
        )


@dataclass
class TrainInfo:
    """列车信息"""
    train_number: str
    departure_station: str
    arrival_station: str
    departure_time: str
    arrival_time: str
    duration: str
    date: str
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            "train_number": self.train_number,
            "departure_station": self.departure_station,
            "arrival_station": self.arrival_station,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "duration": self.duration,
            "date": self.date
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'TrainInfo':
        """从字典创建列车信息对象"""
        return cls(**data)


@dataclass
class TicketInfo:
    """车票信息（支持多个乘客的不同席次选择）"""
    train_info: TrainInfo
    passengers: List[Passenger] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后验证"""
        if not self.train_info:
            raise ValueError("列车信息不能为空")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "train_info": self.train_info.to_dict(),
            "passengers": [passenger.to_dict() for passenger in self.passengers]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TicketInfo':
        """从字典创建车票信息对象"""
        train_info = TrainInfo.from_dict(data["train_info"])
        passengers = [Passenger.from_dict(p) for p in data["passengers"]]
        return cls(train_info=train_info, passengers=passengers)
    
    def add_passenger(self, passenger: Passenger) -> None:
        """添加乘客"""
        if passenger.has_valid_booking_info():
            self.passengers.append(passenger)
        else:
            raise ValueError("乘客信息不完整，无法添加")
    
    def remove_passenger(self, index: int) -> None:
        """移除乘客"""
        if 0 <= index < len(self.passengers):
            self.passengers.pop(index)
    
    def update_passenger(self, index: int, passenger: Passenger) -> None:
        """更新乘客信息"""
        if 0 <= index < len(self.passengers):
            if passenger.has_valid_booking_info():
                self.passengers[index] = passenger
            else:
                raise ValueError("乘客信息不完整，无法更新")
    
    def get_seat_types(self) -> List[SeatType]:
        """获取所有乘客选择的席次类型"""
        return [passenger.seat_type for passenger in self.passengers]
    
    def has_conflicting_seat_types(self) -> bool:
        """检查是否存在席次冲突（用于逻辑验证）"""
        if len(self.passengers) <= 1:
            return False
        seat_types = self.get_seat_types()
        return len(set(seat_types)) > 1
    
    def get_booking_summary(self) -> Dict[str, Any]:
        """获取购票摘要信息"""
        if not self.passengers:
            return {"valid": False, "message": "没有乘客信息"}
        
        # 检查所有乘客信息是否有效
        invalid_passengers = [p for p in self.passengers if not p.has_valid_booking_info()]
        if invalid_passengers:
            return {
                "valid": False, 
                "message": f"有 {len(invalid_passengers)} 个乘客信息不完整"
            }
        
        # 统计席次分布
        seat_distribution = {}
        for passenger in self.passengers:
            seat_name = passenger.get_seat_display_name()
            seat_distribution[seat_name] = seat_distribution.get(seat_name, 0) + 1
        
        # 检查是否需要铺位选择
        needs_bunk = [p for p in self.passengers if p.needs_bunk_selection()]
        
        return {
            "valid": True,
            "train_number": self.train_info.train_number,
            "departure_station": self.train_info.departure_station,
            "arrival_station": self.train_info.arrival_station,
            "date": self.train_info.date,
            "passenger_count": len(self.passengers),
            "seat_distribution": seat_distribution,
            "has_conflicting_seats": self.has_conflicting_seat_types(),
            "needs_bunk_selection": len(needs_bunk) > 0,
            "passengers_needing_bunk": len(needs_bunk)
        }