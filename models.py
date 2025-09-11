from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class SeatType(Enum):
    """席次类别枚举"""
    SECOND_CLASS = "二等座"
    FIRST_CLASS = "一等座"
    BUSINESS_CLASS = "商务座"
    NO_SEAT = "无座"
    HARD_SEAT = "硬座"
    SOFT_SEAT = "软座"
    HARD_SLEEPER = "硬卧"
    SOFT_SLEEPER = "软卧"
    ADVANCED_SOFT_SLEEPER = "高级软卧"


class BunkType(Enum):
    """铺位类型枚举"""
    UPPER_BUNK = "上铺"
    MIDDLE_BUNK = "中铺"
    LOWER_BUNK = "下铺"
    NO_BUNK = "无"


@dataclass
class Passenger:
    """乘客信息"""
    name: str
    id_type: str = "二代身份证"
    id_number: str = ""
    mobile: str = ""
    email: str = ""
    seat_type: SeatType = SeatType.SECOND_CLASS
    bunk_type: Optional[BunkType] = None
    ticket_type: str = "成人票"
    passenger_type: str = "成人"
    
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
        self.passengers.append(passenger)
    
    def remove_passenger(self, index: int) -> None:
        """移除乘客"""
        if 0 <= index < len(self.passengers):
            self.passengers.pop(index)
    
    def update_passenger(self, index: int, passenger: Passenger) -> None:
        """更新乘客信息"""
        if 0 <= index < len(self.passengers):
            self.passengers[index] = passenger
    
    def get_seat_types(self) -> List[SeatType]:
        """获取所有乘客选择的席次类型"""
        return [passenger.seat_type for passenger in self.passengers]
    
    def has_conflicting_seat_types(self) -> bool:
        """检查是否存在席次冲突（用于逻辑验证）"""
        if len(self.passengers) <= 1:
            return False
        seat_types = self.get_seat_types()
        return len(set(seat_types)) > 1