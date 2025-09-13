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
    id_number: str = ""  # 身份证号用于12306验证
    passenger_type: str = "成人"
    
    def __post_init__(self):
        """初始化后验证，确保关键字段不为空"""
        if not self.name or not self.name.strip():
            raise ValueError("乘客姓名不能为空")
        if not self.passenger_type or not self.passenger_type.strip():
            self.passenger_type = "成人"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "name": self.name,
            "id_number": self.id_number,
            "passenger_type": self.passenger_type,
        }
        return result
    
    def get_booking_info(self) -> Dict[str, Any]:
        """获取自动购票所需的信息"""
        return {
            "name": self.name,
            "passenger_type": self.passenger_type,
            "id_number": self.id_number
        }
    
    def has_valid_booking_info(self) -> bool:
        """检查是否有有效的购票信息"""
        return bool(
            self.name and self.name.strip() and
            self.passenger_type and self.passenger_type.strip() and
            self.id_number and self.id_number.strip()
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Passenger':
        """从字典创建乘客对象"""
        return cls(
            name=data["name"],
            id_number=data.get("id_number", ""),
            passenger_type=data.get("passenger_type", "成人")
        )


@dataclass
class TicketPassenger:
    """车票中的乘客信息（包含席次和铺位信息）"""
    passenger: Passenger
    seat_type: SeatType
    bunk_type: Optional[BunkType] = None
    ticket_type: str = "成人票"
    
    def __post_init__(self):
        """初始化后验证"""
        if not self.seat_type:
            self.seat_type = SeatType.SECOND_CLASS
        if not self.ticket_type or not self.ticket_type.strip():
            self.ticket_type = "成人票"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "name": self.passenger.name,
            "id_number": self.passenger.id_number,
            "passenger_type": self.passenger.passenger_type,
            "ticket_type": self.ticket_type,
            "seat_type": self.seat_type.value,
        }
        if self.bunk_type:
            result["bunk_type"] = self.bunk_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TicketPassenger':
        """从字典创建车票乘客对象"""
        passenger = Passenger(
            name=data["name"],
            id_number=data.get("id_number", ""),
            passenger_type=data.get("passenger_type", "成人")
        )
        
        seat_type = SeatType(data.get("seat_type", "二等座"))
        bunk_type = None
        if "bunk_type" in data:
            bunk_type = BunkType(data["bunk_type"])
        
        return cls(
            passenger=passenger,
            seat_type=seat_type,
            bunk_type=bunk_type,
            ticket_type=data.get("ticket_type", "成人票")
        )
    
    def get_booking_info(self) -> Dict[str, Any]:
        """获取自动购票所需的信息"""
        return {
            "name": self.passenger.name,
            "seat_type": self.seat_type,
            "ticket_type": self.ticket_type,
            "bunk_type": self.bunk_type,
            "id_number": self.passenger.id_number
        }


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
    ticket_passengers: List[TicketPassenger] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后验证"""
        if not self.train_info:
            raise ValueError("列车信息不能为空")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "train_info": self.train_info.to_dict(),
            "passengers": [tp.to_dict() for tp in self.ticket_passengers]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TicketInfo':
        """从字典创建车票信息对象"""
        train_info = TrainInfo.from_dict(data["train_info"])
        ticket_passengers = [TicketPassenger.from_dict(p) for p in data["passengers"]]
        return cls(train_info=train_info, ticket_passengers=ticket_passengers)
    
    def add_ticket_passenger(self, ticket_passenger: TicketPassenger) -> None:
        """添加车票乘客"""
        if ticket_passenger.passenger.has_valid_booking_info():
            self.ticket_passengers.append(ticket_passenger)
        else:
            raise ValueError("乘客信息不完整，无法添加")
    
    @property
    def passengers(self) -> List[Passenger]:
        """获取基础乘客信息列表（向后兼容）"""
        return [tp.passenger for tp in self.ticket_passengers]
    
    def remove_ticket_passenger(self, index: int) -> None:
        """移除车票乘客"""
        if 0 <= index < len(self.ticket_passengers):
            self.ticket_passengers.pop(index)
    
    def update_ticket_passenger(self, index: int, ticket_passenger: TicketPassenger) -> None:
        """更新车票乘客信息"""
        if 0 <= index < len(self.ticket_passengers):
            if ticket_passenger.passenger.has_valid_booking_info():
                self.ticket_passengers[index] = ticket_passenger
            else:
                raise ValueError("乘客信息不完整，无法更新")
    
    def get_seat_types(self) -> List[SeatType]:
        """获取所有乘客选择的席次类型"""
        return [tp.seat_type for tp in self.ticket_passengers]
    
    def has_conflicting_seat_types(self) -> bool:
        """检查是否存在席次冲突（用于逻辑验证）"""
        if len(self.ticket_passengers) <= 1:
            return False
        seat_types = self.get_seat_types()
        return len(set(seat_types)) > 1
    
    def get_booking_summary(self) -> Dict[str, Any]:
        """获取购票摘要信息"""
        if not self.ticket_passengers:
            return {"valid": False, "message": "没有乘客信息"}
        
        # 检查所有乘客信息是否有效
        invalid_passengers = [tp for tp in self.ticket_passengers if not tp.passenger.has_valid_booking_info()]
        if invalid_passengers:
            return {
                "valid": False, 
                "message": f"有 {len(invalid_passengers)} 个乘客信息不完整"
            }
        
        # 统计席次分布
        seat_distribution = {}
        for tp in self.ticket_passengers:
            seat_name = tp.seat_type.value
            seat_distribution[seat_name] = seat_distribution.get(seat_name, 0) + 1
        
        # 检查是否需要铺位选择
        needs_bunk = [tp for tp in self.ticket_passengers if "卧" in tp.seat_type.value and not tp.bunk_type]
        
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