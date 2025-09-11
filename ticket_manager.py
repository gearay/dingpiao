import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import Passenger, TrainInfo, TicketInfo, SeatType, BunkType


class TicketManager:
    """票务管理器 - 负责乘客信息和车票信息的管理"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.passengers_file = os.path.join(data_dir, "passengers.json")
        self.tickets_file = os.path.join(data_dir, "tickets.json")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 加载现有数据
        self.passengers = self._load_passengers()
        self.tickets = self._load_tickets()
    
    def _load_passengers(self) -> List[Passenger]:
        """加载乘客数据"""
        if os.path.exists(self.passengers_file):
            try:
                with open(self.passengers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [Passenger.from_dict(p) for p in data]
            except Exception as e:
                print(f"加载乘客数据失败: {e}")
        return []
    
    def _load_tickets(self) -> List[TicketInfo]:
        """加载车票数据"""
        if os.path.exists(self.tickets_file):
            try:
                with open(self.tickets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [TicketInfo.from_dict(t) for t in data]
            except Exception as e:
                print(f"加载车票数据失败: {e}")
        return []
    
    def _save_passengers(self) -> None:
        """保存乘客数据"""
        try:
            with open(self.passengers_file, 'w', encoding='utf-8') as f:
                data = [p.to_dict() for p in self.passengers]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存乘客数据失败: {e}")
    
    def _save_tickets(self) -> None:
        """保存车票数据"""
        try:
            with open(self.tickets_file, 'w', encoding='utf-8') as f:
                data = [t.to_dict() for t in self.tickets]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存车票数据失败: {e}")
    
    # 乘客管理
    def add_passenger(self, passenger: Passenger) -> bool:
        """添加乘客"""
        # 检查是否已存在相同身份证号的乘客
        for existing_passenger in self.passengers:
            if existing_passenger.id_number == passenger.id_number:
                print(f"身份证号 {passenger.id_number} 已存在")
                return False
        
        self.passengers.append(passenger)
        self._save_passengers()
        return True
    
    def get_passengers(self) -> List[Passenger]:
        """获取所有乘客"""
        return self.passengers.copy()
    
    def get_passenger_by_index(self, index: int) -> Optional[Passenger]:
        """根据索引获取乘客"""
        if 0 <= index < len(self.passengers):
            return self.passengers[index]
        return None
    
    def get_passenger_by_id(self, id_number: str) -> Optional[Passenger]:
        """根据身份证号获取乘客"""
        for passenger in self.passengers:
            if passenger.id_number == id_number:
                return passenger
        return None
    
    def update_passenger(self, index: int, passenger: Passenger) -> bool:
        """更新乘客信息"""
        if 0 <= index < len(self.passengers):
            # 检查身份证号冲突
            for i, existing_passenger in enumerate(self.passengers):
                if i != index and existing_passenger.id_number == passenger.id_number:
                    print(f"身份证号 {passenger.id_number} 已存在")
                    return False
            
            self.passengers[index] = passenger
            self._save_passengers()
            return True
        return False
    
    def delete_passenger(self, index: int) -> bool:
        """删除乘客"""
        if 0 <= index < len(self.passengers):
            self.passengers.pop(index)
            self._save_passengers()
            return True
        return False
    
    def search_passengers(self, keyword: str) -> List[Passenger]:
        """搜索乘客"""
        keyword = keyword.lower()
        results = []
        for passenger in self.passengers:
            if (keyword in passenger.name.lower() or 
                keyword in passenger.id_number or
                keyword in passenger.mobile):
                results.append(passenger)
        return results
    
    # 车票管理
    def create_ticket(self, train_info: TrainInfo, passengers: List[Passenger]) -> TicketInfo:
        """创建车票信息"""
        ticket = TicketInfo(train_info=train_info, passengers=passengers.copy())
        self.tickets.append(ticket)
        self._save_tickets()
        return ticket
    
    def get_tickets(self) -> List[TicketInfo]:
        """获取所有车票"""
        return self.tickets.copy()
    
    def get_ticket_by_index(self, index: int) -> Optional[TicketInfo]:
        """根据索引获取车票"""
        if 0 <= index < len(self.tickets):
            return self.tickets[index]
        return None
    
    def update_ticket(self, index: int, ticket: TicketInfo) -> bool:
        """更新车票信息"""
        if 0 <= index < len(self.tickets):
            self.tickets[index] = ticket
            self._save_tickets()
            return True
        return False
    
    def delete_ticket(self, index: int) -> bool:
        """删除车票"""
        if 0 <= index < len(self.tickets):
            self.tickets.pop(index)
            self._save_tickets()
            return True
        return False
    
    def search_tickets(self, train_number: str = None, date: str = None, 
                     departure: str = None, arrival: str = None) -> List[TicketInfo]:
        """搜索车票"""
        results = []
        for ticket in self.tickets:
            match = True
            if train_number and ticket.train_info.train_number != train_number:
                match = False
            if date and ticket.train_info.date != date:
                match = False
            if departure and ticket.train_info.departure_station != departure:
                match = False
            if arrival and ticket.train_info.arrival_station != arrival:
                match = False
            if match:
                results.append(ticket)
        return results
    
    def get_available_seat_types(self) -> List[SeatType]:
        """获取可用的席次类型"""
        return list(SeatType)
    
    def get_available_bunk_types(self) -> List[BunkType]:
        """获取可用的铺位类型"""
        return list(BunkType)
    
    def validate_ticket_info(self, ticket: TicketInfo) -> Dict[str, Any]:
        """验证车票信息"""
        errors = []
        warnings = []
        
        # 验证乘客信息
        if not ticket.passengers:
            errors.append("至少需要一个乘客")
        
        for i, passenger in enumerate(ticket.passengers):
            if not passenger.name.strip():
                errors.append(f"乘客{i+1}姓名不能为空")
            if not passenger.id_number.strip():
                errors.append(f"乘客{i+1}身份证号不能为空")
            if not passenger.mobile.strip():
                warnings.append(f"乘客{i+1}手机号为空")
        
        # 验证列车信息
        if not ticket.train_info.train_number.strip():
            errors.append("车次不能为空")
        if not ticket.train_info.departure_station.strip():
            errors.append("出发站不能为空")
        if not ticket.train_info.arrival_station.strip():
            errors.append("到达站不能为空")
        if not ticket.train_info.date.strip():
            errors.append("出发日期不能为空")
        
        # 检查席次逻辑
        if ticket.has_conflicting_seat_types():
            warnings.append("乘客选择了不同的席次类型，请确认是否正确")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def backup_data(self, backup_dir: str = "backup") -> str:
        """备份数据"""
        backup_dir = os.path.join(self.data_dir, backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 备份乘客数据
        passengers_backup = os.path.join(backup_dir, f"passengers_{timestamp}.json")
        with open(passengers_backup, 'w', encoding='utf-8') as f:
            data = [p.to_dict() for p in self.passengers]
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 备份车票数据
        tickets_backup = os.path.join(backup_dir, f"tickets_{timestamp}.json")
        with open(tickets_backup, 'w', encoding='utf-8') as f:
            data = [t.to_dict() for t in self.tickets]
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return backup_dir
    
    def restore_data(self, backup_file: str) -> bool:
        """恢复数据"""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "passengers" in backup_file:
                self.passengers = [Passenger.from_dict(p) for p in data]
                self._save_passengers()
            elif "tickets" in backup_file:
                self.tickets = [TicketInfo.from_dict(t) for t in data]
                self._save_tickets()
            
            return True
        except Exception as e:
            print(f"恢复数据失败: {e}")
            return False
    
    def clear_all_data(self) -> None:
        """清空所有数据"""
        self.passengers.clear()
        self.tickets.clear()
        self._save_passengers()
        self._save_tickets()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        seat_type_count = {}
        for ticket in self.tickets:
            for passenger in ticket.passengers:
                seat_type = passenger.seat_type.value
                seat_type_count[seat_type] = seat_type_count.get(seat_type, 0) + 1
        
        return {
            "total_passengers": len(self.passengers),
            "total_tickets": len(self.tickets),
            "seat_type_distribution": seat_type_count,
            "last_updated": datetime.now().isoformat()
        }