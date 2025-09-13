import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from models import Passenger, TrainInfo, TicketInfo, SeatType, BunkType
from ticket_manager import TicketManager
from auto_booking import AutoBooking, BookingStatus
from timed_booking import TimedBooking
from error_handler import ErrorHandler, ErrorType, UserChoice


class MainApp:
    """12306自动购票系统主应用"""
    
    def __init__(self):
        self.ticket_manager = TicketManager()
        self.auto_booking = AutoBooking(self.ticket_manager, headless=False)
        self.timed_booking = TimedBooking(self.ticket_manager, headless=False)
        self.error_handler = ErrorHandler(self.auto_booking)
        
        # 配置
        self.config_file = "config.json"
        self.load_config()
        
        # 设置回调
        self.setup_callbacks()
        
        # 运行状态
        self.running = True
        
        print("=== 12306自动购票系统 ===")
        print("系统初始化完成")
    
    def load_config(self) -> None:
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print("配置文件加载成功")
            else:
                self.config = {
                    "username": "",
                    "password": "",
                    "max_retries": 3,
                    "retry_delay": 5,
                    "headless": False,
                    "auto_save": True
                }
                self.save_config()
                print("配置文件创建成功")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self.config = {}
    
    def save_config(self) -> None:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def setup_callbacks(self) -> None:
        """设置回调函数"""
        self.error_handler.set_user_callback(self.on_error)
        self.timed_booking.set_status_callback(self.on_task_status)
        self.timed_booking.set_error_callback(self.on_task_error)
    
    def on_error(self, error_type: ErrorType, error_message: str) -> UserChoice:
        """错误处理回调"""
        print(f"\n错误发生: {error_type.value}")
        print(f"错误信息: {error_message}")
        
        # 显示恢复建议
        suggestions = self.error_handler.get_recovery_suggestions(error_type)
        print("恢复建议:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
        
        # 提供选择
        print("\n请选择处理方式:")
        print("1. 重试")
        print("2. 手动预订")
        print("3. 跳过任务")
        print("4. 取消所有")
        print("5. 等待后重试")
        print("6. 改变策略")
        
        while True:
            try:
                choice = input("请输入选择 (1-6): ").strip()
                choice_map = {
                    "1": UserChoice.RETRY,
                    "2": UserChoice.MANUAL_BOOKING,
                    "3": UserChoice.SKIP_TASK,
                    "4": UserChoice.CANCEL_ALL,
                    "5": UserChoice.WAIT_AND_RETRY,
                    "6": UserChoice.CHANGE_STRATEGY
                }
                return choice_map.get(choice, UserChoice.RETRY)
            except:
                print("输入无效，请重试")
    
    def on_task_status(self, task) -> None:
        """任务状态回调"""
        print(f"\n任务状态更新: {task.ticket_info.train_info.train_number}")
        print(f"状态: {task.status}")
        if task.result:
            print(f"结果: {task.result}")
    
    def on_task_error(self, task) -> None:
        """任务错误回调"""
        print(f"\n任务执行失败: {task.ticket_info.train_info.train_number}")
        print(f"错误: {task.error_message}")
        print(f"重试次数: {task.retry_count}")
    
    def show_main_menu(self) -> None:
        """显示主菜单"""
        while self.running:
            print("\n" + "="*50)
            print("12306自动购票系统 - 主菜单")
            print("="*50)
            print("1. 乘客管理")
            print("2. 车票管理")
            print("3. 自动购票")
            print("4. 定时购票")
            print("5. 系统设置")
            print("6. 查看统计")
            print("7. 帮助")
            print("8. 退出")
            
            choice = input("请选择功能 (1-8): ").strip()
            
            if choice == "1":
                self.passenger_management()
            elif choice == "2":
                self.ticket_management()
            elif choice == "3":
                self.auto_booking_menu()
            elif choice == "4":
                self.timed_booking_menu()
            elif choice == "5":
                self.system_settings()
            elif choice == "6":
                self.show_statistics()
            elif choice == "7":
                self.show_help()
            elif choice == "8":
                self.exit_app()
            else:
                print("无效选择，请重试")
    
    def passenger_management(self) -> None:
        """乘客管理"""
        while True:
            print("\n--- 乘客管理 ---")
            print("1. 查看所有乘客")
            print("2. 添加乘客")
            print("3. 编辑乘客")
            print("4. 删除乘客")
            print("5. 搜索乘客")
            print("6. 返回主菜单")
            
            choice = input("请选择 (1-6): ").strip()
            
            if choice == "1":
                self.show_all_passengers()
            elif choice == "2":
                self.add_passenger()
            elif choice == "3":
                self.edit_passenger()
            elif choice == "4":
                self.delete_passenger()
            elif choice == "5":
                self.search_passengers()
            elif choice == "6":
                break
            else:
                print("无效选择")
    
    def show_all_passengers(self) -> None:
        """显示所有乘客"""
        passengers = self.ticket_manager.get_passengers()
        if not passengers:
            print("暂无乘客信息")
            return
        
        print(f"\n共有 {len(passengers)} 位乘客:")
        print("-" * 60)
        print(f"{'序号':<4} {'姓名':<10} {'身份证号':<20} {'乘客类型':<8}")
        print("-" * 60)
        
        for i, passenger in enumerate(passengers, 1):
            print(f"{i:<4} {passenger.name:<10} {passenger.id_number:<20} {passenger.passenger_type:<8}")
        
        print("\n💡 提示: 席次和铺位信息在车票管理模块中设置")
    
    def add_passenger(self) -> None:
        """添加乘客"""
        print("\n--- 添加乘客 ---")
        
        name = input("姓名: ").strip()
        if not name:
            print("姓名不能为空")
            return
        
        id_number = input("身份证号: ").strip()
        if not id_number:
            print("身份证号不能为空")
            return
        
        # 选择乘客类型（简化为：成人，儿童，学生，残军）
        print("选择乘客类型:")
        passenger_types = ["成人", "儿童", "学生", "残军"]
        for i, p_type in enumerate(passenger_types, 1):
            print(f"{i}. {p_type}")
        
        try:
            type_choice = int(input("请选择乘客类型 (1-{}): ".format(len(passenger_types))))
            passenger_type = passenger_types[type_choice - 1]
        except:
            print("无效选择，使用默认类型")
            passenger_type = "成人"
        
        passenger = Passenger(
            name=name,
            id_number=id_number,
            passenger_type=passenger_type
        )
        
        if self.ticket_manager.add_passenger(passenger):
            print("乘客添加成功")
        else:
            print("乘客添加失败")
    
    def edit_passenger(self) -> None:
        """编辑乘客"""
        self.show_all_passengers()
        passengers = self.ticket_manager.get_passengers()
        
        if not passengers:
            return
        
        try:
            index = int(input("请输入要编辑的乘客序号: ")) - 1
            if 0 <= index < len(passengers):
                passenger = passengers[index]
                
                print(f"当前信息:")
                print(f"姓名: {passenger.name}")
                print(f"身份证号: {passenger.id_number}")
                print(f"乘客类型: {passenger.passenger_type}")
                
                # 输入新信息
                name = input(f"姓名 [{passenger.name}]: ").strip()
                if name:
                    passenger.name = name
                
                id_number = input(f"身份证号 [{passenger.id_number}]: ").strip()
                if id_number:
                    passenger.id_number = id_number
                
                # 选择乘客类型
                print("选择乘客类型:")
                passenger_types = ["成人", "儿童", "学生", "残军"]
                for i, p_type in enumerate(passenger_types, 1):
                    print(f"{i}. {p_type}")
                    if p_type == passenger.passenger_type:
                        print(f"   (当前选择)")
                
                try:
                    type_choice = int(input(f"请选择乘客类型 (1-{len(passenger_types)}, 当前为{passenger.passenger_type}): "))
                    if 1 <= type_choice <= len(passenger_types):
                        passenger.passenger_type = passenger_types[type_choice - 1]
                except:
                    print("无效选择，保持原类型")
                
                if self.ticket_manager.update_passenger(index, passenger):
                    print("乘客信息更新成功")
                else:
                    print("乘客信息更新失败")
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def delete_passenger(self) -> None:
        """删除乘客"""
        self.show_all_passengers()
        passengers = self.ticket_manager.get_passengers()
        
        if not passengers:
            return
        
        try:
            index = int(input("请输入要删除的乘客序号: ")) - 1
            if 0 <= index < len(passengers):
                passenger = passengers[index]
                confirm = input(f"确认删除乘客 '{passenger.name}'? (y/N): ").strip().lower()
                if confirm == 'y':
                    if self.ticket_manager.delete_passenger(index):
                        print("乘客删除成功")
                    else:
                        print("乘客删除失败")
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def search_passengers(self) -> None:
        """搜索乘客"""
        keyword = input("请输入搜索关键词: ").strip()
        if not keyword:
            return
        
        results = self.ticket_manager.search_passengers(keyword)
        if not results:
            print("未找到匹配的乘客")
            return
        
        print(f"\n找到 {len(results)} 位匹配的乘客:")
        print("-" * 50)
        print(f"{'姓名':<10} {'身份证号':<20} {'乘客类型':<8}")
        print("-" * 50)
        
        for passenger in results:
            print(f"{passenger.name:<10} {passenger.id_number:<20} {passenger.passenger_type:<8}")
    
    def ticket_management(self) -> None:
        """车票管理"""
        while True:
            print("\n--- 车票管理 ---")
            print("1. 查看所有车票")
            print("2. 创建车票")
            print("3. 编辑车票")
            print("4. 删除车票")
            print("5. 搜索车票")
            print("6. 返回主菜单")
            
            choice = input("请选择 (1-6): ").strip()
            
            if choice == "1":
                self.show_all_tickets()
            elif choice == "2":
                self.create_ticket()
            elif choice == "3":
                self.edit_ticket()
            elif choice == "4":
                self.delete_ticket()
            elif choice == "5":
                self.search_tickets()
            elif choice == "6":
                break
            else:
                print("无效选择")
    
    def show_all_tickets(self) -> None:
        """显示所有车票"""
        tickets = self.ticket_manager.get_tickets()
        if not tickets:
            print("暂无车票信息")
            return
        
        print(f"\n共有 {len(tickets)} 张车票:")
        print("-" * 100)
        for i, ticket in enumerate(tickets, 1):
            print(f"{i}. {ticket.train_info.train_number} "
                  f"{ticket.train_info.departure_station} -> {ticket.train_info.arrival_station} "
                  f"{ticket.train_info.date} {len(ticket.passengers)}人")
    
    def create_ticket(self) -> None:
        """创建车票"""
        print("\n--- 创建车票 ---")
        
        # 输入列车信息
        train_number = input("车次: ").strip()
        departure_station = input("出发站: ").strip()
        arrival_station = input("到达站: ").strip()
        departure_time = input("出发时间: ").strip()
        arrival_time = input("到达时间: ").strip()
        duration = input("历时: ").strip()
        date = input("出发日期 (YYYY-MM-DD): ").strip()
        
        train_info = TrainInfo(
            train_number=train_number,
            departure_station=departure_station,
            arrival_station=arrival_station,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=duration,
            date=date
        )
        
        # 选择乘客
        passengers = self.ticket_manager.get_passengers()
        if not passengers:
            print("请先添加乘客")
            return
        
        print("选择乘客:")
        for i, passenger in enumerate(passengers, 1):
            print(f"{i}. {passenger.name} ({passenger.passenger_type})")
        
        selected_passengers = []
        while True:
            try:
                choice = input("请选择乘客序号 (输入序号，用逗号分隔): ").strip()
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
                
                for index in indices:
                    if 0 <= index < len(passengers):
                        selected_passengers.append(passengers[index])
                
                break
            except:
                print("输入错误，请重试")
        
        # 为每个乘客选择席次和铺位
        ticket_passengers = []
        for passenger in selected_passengers:
            print(f"\n为乘客 {passenger.name} 选择席次和票种:")
            
            # 选择票种（基于乘客类型映射到具体票种）
            print("选择票种:")
            ticket_mapping = {
                "成人": ["成人票"],
                "儿童": ["儿童票"],
                "学生": ["学生票"],
                "残军": ["残军票"]
            }
            
            available_tickets = ticket_mapping.get(passenger.passenger_type, ["成人票"])
            for i, ticket in enumerate(available_tickets, 1):
                print(f"{i}. {ticket}")
            
            try:
                ticket_choice = int(input(f"请选择票种 (1-{len(available_tickets)}): ")) - 1
                if 0 <= ticket_choice < len(available_tickets):
                    ticket_type = available_tickets[ticket_choice]
                else:
                    ticket_type = available_tickets[0]
            except:
                ticket_type = available_tickets[0]
            
            # 选择席次
            print("选择席次类型:")
            seat_types = self.ticket_manager.get_available_seat_types()
            for i, seat_type in enumerate(seat_types, 1):
                print(f"{i}. {seat_type.value}")
            
            try:
                seat_choice = int(input("请选择席次 (1-{}): ".format(len(seat_types))))
                seat_type = seat_types[seat_choice - 1]
            except:
                print("无效选择，使用默认席次")
                seat_type = SeatType.SECOND_CLASS
            
            # 如果是卧铺，选择铺位
            bunk_type = None
            if "卧" in seat_type.value:
                print("选择铺位类型:")
                bunk_types = self.ticket_manager.get_available_bunk_types()
                for i, bunk in enumerate(bunk_types, 1):
                    print(f"{i}. {bunk.value}")
                
                try:
                    bunk_choice = int(input("请选择铺位 (1-{}): ".format(len(bunk_types))))
                    bunk_type = bunk_types[bunk_choice - 1]
                except:
                    print("无效选择，不选择铺位")
            
            # 创建车票乘客对象
            from models import TicketPassenger
            ticket_passenger = TicketPassenger(
                passenger=passenger,
                seat_type=seat_type,
                bunk_type=bunk_type,
                ticket_type=ticket_type
            )
            ticket_passengers.append(ticket_passenger)
        
        # 创建车票
        ticket = self.ticket_manager.create_ticket_with_ticket_passengers(train_info, ticket_passengers)
        print("车票创建成功")
    
    def edit_ticket(self) -> None:
        """编辑车票"""
        # 实现编辑车票逻辑
        print("编辑车票功能开发中...")
    
    def delete_ticket(self) -> None:
        """删除车票"""
        self.show_all_tickets()
        tickets = self.ticket_manager.get_tickets()
        
        if not tickets:
            return
        
        try:
            index = int(input("请输入要删除的车票序号: ")) - 1
            if 0 <= index < len(tickets):
                ticket = tickets[index]
                confirm = input(f"确认删除车票 '{ticket.train_info.train_number}'? (y/N): ").strip().lower()
                if confirm == 'y':
                    if self.ticket_manager.delete_ticket(index):
                        print("车票删除成功")
                    else:
                        print("车票删除失败")
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def search_tickets(self) -> None:
        """搜索车票"""
        train_number = input("请输入车次 (留空跳过): ").strip()
        date = input("请输入日期 (留空跳过): ").strip()
        departure = input("请输入出发站 (留空跳过): ").strip()
        arrival = input("请输入到达站 (留空跳过): ").strip()
        
        tickets = self.ticket_manager.search_tickets(
            train_number=train_number if train_number else None,
            date=date if date else None,
            departure=departure if departure else None,
            arrival=arrival if arrival else None
        )
        
        if not tickets:
            print("未找到匹配的车票")
            return
        
        print(f"\n找到 {len(tickets)} 张匹配的车票:")
        for ticket in tickets:
            print(f"{ticket.train_info.train_number} "
                  f"{ticket.train_info.departure_station} -> {ticket.train_info.arrival_station} "
                  f"{ticket.train_info.date}")
    
    def auto_booking_menu(self) -> None:
        """自动购票菜单"""
        while True:
            print("\n--- 自动购票 ---")
            print("1. 预登录")
            print("2. 立即购票")
            print("3. 查看状态")
            print("4. 返回主菜单")
            
            choice = input("请选择 (1-4): ").strip()
            
            if choice == "1":
                self.pre_login()
            elif choice == "2":
                self.book_ticket_now()
            elif choice == "3":
                self.show_booking_status()
            elif choice == "4":
                break
            else:
                print("无效选择")
    
    def pre_login(self) -> None:
        """预登录"""
        print("\n--- 预登录 ---")
        
        tickets = self.ticket_manager.get_tickets()
        if not tickets:
            print("请先创建车票信息")
            return
        
        print("选择用于预登录的车票:")
        for i, ticket in enumerate(tickets, 1):
            print(f"{i}. {ticket.train_info.train_number} "
                  f"{ticket.train_info.departure_station} -> {ticket.train_info.arrival_station} "
                  f"{ticket.train_info.date}")
        
        try:
            choice = int(input("请选择车票序号: ")) - 1
            if 0 <= choice < len(tickets):
                ticket = tickets[choice]
                print("开始预登录...")
                print("程序将打开浏览器，请完成登录后等待自动化操作...")
                
                success = self.auto_booking.open_browser_and_wait_for_login(
                    ticket.train_info.departure_station,
                    ticket.train_info.arrival_station,
                    ticket.train_info.date
                )
                
                if success:
                    print("预登录成功")
                else:
                    print("预登录失败")
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def book_ticket_now(self) -> None:
        """立即购票"""
        print("\n--- 立即购票 ---")
        
        tickets = self.ticket_manager.get_tickets()
        if not tickets:
            print("请先创建车票")
            return
        
        print("选择要预订的车票:")
        for i, ticket in enumerate(tickets, 1):
            print(f"{i}. {ticket.train_info.train_number} "
                  f"{ticket.train_info.departure_station} -> {ticket.train_info.arrival_station} "
                  f"{ticket.train_info.date}")
        
        try:
            choice = int(input("请选择车票序号: ")) - 1
            if 0 <= choice < len(tickets):
                ticket = tickets[choice]
                confirm = input(f"确认预订车票 '{ticket.train_info.train_number}'? (y/N): ").strip().lower()
                if confirm == 'y':
                    print("开始自动预订...")
                    print("程序将打开浏览器，请完成登录后等待自动化操作...")
                    success = self.auto_booking.auto_book_ticket(ticket)
                    
                    if success:
                        print("预订成功")
                    else:
                        print("预订失败")
                        print(f"错误信息: {self.auto_booking.error_message}")
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def show_booking_status(self) -> None:
        """显示购票状态"""
        status = self.auto_booking.get_status()
        print(f"\n当前状态: {status['status']}")
        if status['error_message']:
            print(f"错误信息: {status['error_message']}")
        print(f"是否运行中: {status['is_running']}")
    
    def timed_booking_menu(self) -> None:
        """定时购票菜单"""
        while True:
            print("\n--- 定时购票 ---")
            print("1. 添加定时任务")
            print("2. 查看任务列表")
            print("3. 启动调度器")
            print("4. 停止调度器")
            print("5. 返回主菜单")
            
            choice = input("请选择 (1-5): ").strip()
            
            if choice == "1":
                self.add_timed_task()
            elif choice == "2":
                self.show_timed_tasks()
            elif choice == "3":
                self.start_scheduler()
            elif choice == "4":
                self.stop_scheduler()
            elif choice == "5":
                break
            else:
                print("无效选择")
    
    def add_timed_task(self) -> None:
        """添加定时任务"""
        print("\n--- 添加定时任务 ---")
        
        tickets = self.ticket_manager.get_tickets()
        if not tickets:
            print("请先创建车票")
            return
        
        print("选择要预订的车票:")
        for i, ticket in enumerate(tickets, 1):
            print(f"{i}. {ticket.train_info.train_number} "
                  f"{ticket.train_info.departure_station} -> {ticket.train_info.arrival_station} "
                  f"{ticket.train_info.date}")
        
        try:
            choice = int(input("请选择车票序号: ")) - 1
            if 0 <= choice < len(tickets):
                ticket = tickets[choice]
                
                # 输入开始时间
                start_time_str = input("请输入开始时间 (YYYY-MM-DD HH:MM:SS): ").strip()
                try:
                    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                except:
                    print("时间格式错误")
                    return
                
                # 检查时间有效性
                if not self.timed_booking.validate_task_time(start_time):
                    print("任务时间无效")
                    return
                
                # 添加任务
                task_id = self.timed_booking.add_task(ticket, start_time)
                print(f"定时任务添加成功，任务ID: {task_id}")
                
                # 询问是否启动调度器
                start_now = input("是否立即启动调度器? (y/N): ").strip().lower()
                if start_now == 'y':
                    self.start_scheduler()
            else:
                print("无效序号")
        except:
            print("输入错误")
    
    def show_timed_tasks(self) -> None:
        """显示定时任务"""
        tasks = self.timed_booking.get_tasks()
        if not tasks:
            print("暂无定时任务")
            return
        
        print(f"\n共有 {len(tasks)} 个定时任务:")
        print("-" * 80)
        for task in tasks:
            print(f"任务: {task.ticket_info.train_info.train_number}")
            print(f"时间: {task.start_time}")
            print(f"状态: {task.status}")
            print(f"重试次数: {task.retry_count}/{task.max_retries}")
            print("-" * 40)
    
    def start_scheduler(self) -> None:
        """启动调度器"""
        print("启动调度器...")
        self.timed_booking.start_scheduler()
        print("调度器已启动")
    
    def stop_scheduler(self) -> None:
        """停止调度器"""
        print("停止调度器...")
        self.timed_booking.stop_scheduler()
        print("调度器已停止")
    
    def system_settings(self) -> None:
        """系统设置"""
        while True:
            print("\n--- 系统设置 ---")
            print("1. 账号设置")
            print("2. 重试设置")
            print("3. 浏览器设置")
            print("4. 数据备份")
            print("5. 返回主菜单")
            
            choice = input("请选择 (1-5): ").strip()
            
            if choice == "1":
                self.account_settings()
            elif choice == "2":
                self.retry_settings()
            elif choice == "3":
                self.browser_settings()
            elif choice == "4":
                self.data_backup()
            elif choice == "5":
                break
            else:
                print("无效选择")
    
    def account_settings(self) -> None:
        """账号设置"""
        print("\n--- 账号设置 ---")
        
        username = input(f"用户名 [{self.config.get('username', '')}]: ").strip()
        if username:
            self.config["username"] = username
        
        password = input(f"密码 [{ '*' * len(self.config.get('password', '')) if self.config.get('password') else ''}]: ").strip()
        if password:
            self.config["password"] = password
        
        self.save_config()
        print("账号设置保存成功")
    
    def retry_settings(self) -> None:
        """重试设置"""
        print("\n--- 重试设置 ---")
        
        try:
            max_retries = int(input(f"最大重试次数 [{self.config.get('max_retries', 3)}]: "))
            retry_delay = int(input(f"重试间隔秒数 [{self.config.get('retry_delay', 5)}]: "))
            
            self.config["max_retries"] = max_retries
            self.config["retry_delay"] = retry_delay
            
            self.error_handler.set_retry_config(max_retries, retry_delay)
            self.save_config()
            print("重试设置保存成功")
        except:
            print("输入错误")
    
    def browser_settings(self) -> None:
        """浏览器设置"""
        print("\n--- 浏览器设置 ---")
        
        headless = input(f"无头模式 [{self.config.get('headless', False)}] (y/N): ").strip().lower()
        self.config["headless"] = headless == 'y'
        
        self.save_config()
        print("浏览器设置保存成功")
    
    def data_backup(self) -> None:
        """数据备份"""
        print("\n--- 数据备份 ---")
        
        try:
            backup_dir = self.ticket_manager.backup_data()
            print(f"数据备份成功，备份目录: {backup_dir}")
        except Exception as e:
            print(f"备份失败: {e}")
    
    def show_statistics(self) -> None:
        """显示统计信息"""
        print("\n--- 统计信息 ---")
        
        # 票务统计
        ticket_stats = self.ticket_manager.get_statistics()
        print(f"乘客总数: {ticket_stats['total_passengers']}")
        print(f"车票总数: {ticket_stats['total_tickets']}")
        print(f"席次分布: {ticket_stats['seat_type_distribution']}")
        
        # 定时任务统计
        timed_stats = self.timed_booking.get_statistics()
        print(f"定时任务总数: {timed_stats['total_tasks']}")
        print(f"待处理任务: {timed_stats['pending_tasks']}")
        print(f"运行中任务: {timed_stats['running_tasks']}")
        print(f"已完成任务: {timed_stats['completed_tasks']}")
        print(f"失败任务: {timed_stats['failed_tasks']}")
        
        # 错误统计
        error_stats = self.error_handler.get_error_statistics()
        print(f"错误总数: {error_stats['total_errors']}")
        print(f"最近24小时错误: {error_stats['recent_errors_24h']}")
    
    def show_help(self) -> None:
        """显示帮助"""
        print("\n--- 帮助 ---")
        print("1. 乘客管理: 添加、编辑、删除和搜索乘客信息")
        print("2. 车票管理: 创建、编辑、删除和搜索车票信息")
        print("3. 自动购票: 预登录和立即购票功能")
        print("4. 定时购票: 添加和管理定时购票任务")
        print("5. 系统设置: 配置账号、重试参数等")
        print("6. 查看统计: 查看系统运行统计")
        print("7. 帮助: 显示本帮助信息")
        print("8. 退出: 退出系统")
        
        print("\n使用建议:")
        print("- 建议先添加乘客信息")
        print("- 创建车票时选择乘客")
        print("- 使用预登录功能提前登录")
        print("- 定时购票功能需要准确的开始时间")
        print("- 遇到问题时查看错误统计信息")
    
    def exit_app(self) -> None:
        """退出应用"""
        print("正在退出系统...")
        
        # 停止调度器
        self.timed_booking.stop_scheduler()
        
        # 关闭浏览器
        self.auto_booking.close()
        
        # 保存配置
        self.save_config()
        
        self.running = False
        print("系统已退出")
    
    def run(self) -> None:
        """运行应用"""
        try:
            self.show_main_menu()
        except KeyboardInterrupt:
            print("\n收到中断信号，正在退出...")
            self.exit_app()
        except Exception as e:
            print(f"系统异常: {e}")
            self.exit_app()


if __name__ == "__main__":
    app = MainApp()
    app.run()