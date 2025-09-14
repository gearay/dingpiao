import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from models import Passenger, TrainInfo, TicketInfo, SeatType, BunkType, TicketPassenger

class BookingStatus(Enum):
    PENDING = "待处理"
    WAITING_FOR_LOGIN = "等待登录"
    SEARCHING = "正在搜索"
    SELECTING_TRAIN = "选择车次"
    SELECTING_SEATS = "选择席次"
    SUBMITTING_ORDER = "提交订单"
    CONFIRMING_PAYMENT = "确认支付"
    SUCCESS = "成功"
    FAILED = "失败"
    CANCELLED = "已取消"

class AutoBooking:
    def __init__(self, ticket_manager=None, headless: bool = False):
        self.ticket_manager = ticket_manager
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.status = BookingStatus.PENDING
        self.error_message = ""
        self.logger = self._setup_logger()
        self.base_url = "https://www.12306.cn"
        self.ticket_url = "https://kyfw.12306.cn/otn/leftTicket/init"
        self.wait_timeout = 30
        self.poll_interval = 0.05  # 50ms for faster polling
        self.login_check_interval = 0.1  # 100ms for faster login checking
        self.max_login_wait_time = 300

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("AutoBooking")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            fh = logging.FileHandler("booking.log", encoding="utf-8")
            ch = logging.StreamHandler()
            fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh.setFormatter(fmt)
            ch.setFormatter(fmt)
            logger.addHandler(fh)
            logger.addHandler(ch)
        return logger

    def init_driver(self) -> bool:
        try:
            options = Options()
            if self.headless:
                options.add_argument("--headless=new")
            # 反自动化指纹
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-setuid-sandbox')
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.driver.set_page_load_timeout(60)
            self.logger.info("浏览器驱动初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"初始化浏览器驱动失败: {e}")
            self.error_message = str(e)
            return False

    def open_browser_and_wait_for_login(self, from_station: str = None, to_station: str = None, departure_date: str = None) -> bool:
        """打开浏览器并等待用户登录（移除车次查询功能）"""
        try:
            self.status = BookingStatus.WAITING_FOR_LOGIN
            if not self.driver and not self.init_driver():
                return False

            self.driver.get(self.base_url)
            time.sleep(0.05)  # 50ms for page load
            self.driver.get(self.ticket_url)
            time.sleep(0.05)  # 50ms for page load

            # 移除车次查询表单填充，只打开登录页面
            print("=" * 50)
            print("请在浏览器中完成登录，登录后本程序将继续。")
            print("=" * 50)

            if self._wait_for_login():
                self.logger.info("检测到用户已登录")
                return True
            else:
                self.logger.error("登录超时")
                return False
        except Exception as e:
            self.logger.error(f"打开浏览器失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def open_browser_for_login_only(self) -> bool:
        """仅打开浏览器进行登录（无任何车次查询）"""
        return self.open_browser_and_wait_for_login()

    def _fill_search_form(self, from_station: str, to_station: str, departure_date: str) -> None:
        try:
            wait = WebDriverWait(self.driver, self.wait_timeout)
            self.logger.info("开始填充搜索表单...")
            
            # 出发地
            from_input = wait.until(EC.element_to_be_clickable((By.ID, "fromStationText")))
            from_input.click()
            time.sleep(0.02)  # 20ms for click response
            
            # 确保清空输入框
            from_input.clear()
            time.sleep(0.01)  # 10ms for clear operation
            
            # 再次清空以确保完全清空
            current_value = from_input.get_attribute('value')
            if current_value:
                from_input.clear()
                time.sleep(0.01)  # 10ms for additional clear
                
            from_input.send_keys(from_station)
            time.sleep(0.02)  # 20ms for key input
            
            # 关闭下拉
            from_input.send_keys(Keys.ENTER)
            time.sleep(0.02)  # 20ms for dropdown close

            # 目的地
            to_input = wait.until(EC.element_to_be_clickable((By.ID, "toStationText")))
            to_input.click()
            time.sleep(0.02)  # 20ms for click response
            
            # 确保清空输入框
            to_input.clear()
            time.sleep(0.01)  # 10ms for clear operation
            
            # 再次清空以确保完全清空
            current_value = to_input.get_attribute('value')
            if current_value:
                to_input.clear()
                time.sleep(0.01)  # 10ms for additional clear
                
            to_input.send_keys(to_station)
            time.sleep(0.02)  # 20ms for key input
            to_input.send_keys(Keys.ENTER)
            time.sleep(0.02)  # 20ms for dropdown close

            # 日期
            date_input = wait.until(EC.element_to_be_clickable((By.ID, "train_date")))
            date_input.click()
            time.sleep(0.02)  # 20ms for click response
            
            # 确保清空输入框
            date_input.clear()
            time.sleep(0.01)  # 10ms for clear operation
            
            # 再次清空以确保完全清空
            current_value = date_input.get_attribute('value')
            if current_value:
                date_input.clear()
                time.sleep(0.01)  # 10ms for additional clear
                
            date_input.send_keys(departure_date)
            time.sleep(0.02)  # 20ms for key input
            
            self.logger.info("搜索表单填充完成")
        except Exception as e:
            self.logger.error(f"填充搜索表单失败: {e}")
            raise

    def _wait_for_login(self) -> bool:
        start = time.time()
        while time.time() - start < self.max_login_wait_time:
            try:
                # 检查登录状态
                if self._exists((By.XPATH, "//a[contains(text(),'退出')]")):
                    return True
                if self._exists((By.XPATH, "//*[contains(text(),'您好') and contains(text(),'|')]")):
                    return True
                time.sleep(self.login_check_interval)
            except Exception:
                time.sleep(self.login_check_interval)
        return False

    def search_tickets(self, max_retries: int = 3) -> bool:
        try:
            self.status = BookingStatus.SEARCHING
            wait = WebDriverWait(self.driver, self.wait_timeout)
            for attempt in range(max_retries):
                try:
                    # 在点击查询按钮之前，先检查并处理dhx_modal_cover
                    self._handle_dhx_modal_cover()
                    
                    query_button = wait.until(EC.element_to_be_clickable((By.ID, "query_ticket")))
                    query_button.click()
                    time.sleep(0.05)  # 50ms for search response
                    
                    # 点击查询按钮后，再次检查并处理可能出现的dhx_modal_cover
                    self._handle_dhx_modal_cover()
                    # 检查查询结果
                    rows = self.driver.find_elements(By.XPATH, "//tbody[@id='queryLeftTable']/tr[not(contains(@class,'tips'))]")
                    if rows:
                        self.logger.info("车票搜索成功")
                        return True
                    time.sleep(0.1)  # 100ms retry interval
                except Exception as e:
                    self.logger.warning(f"第 {attempt+1} 次搜索异常: {e}")
                    
                    # 如果是元素点击被拦截的错误，尝试处理dhx_modal_cover遮罩层
                    if "element click intercepted" in str(e).lower() and "dhx_modal_cover" in str(e):
                        self.logger.info("检测到dhx_modal_cover遮挡问题，尝试处理...")
                        self._handle_dhx_modal_cover()
                    
                    time.sleep(0.1)  # 100ms retry interval
            return False
        except Exception as e:
            self.logger.error(f"搜索车票失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    def select_train(self, train_number: str) -> bool:
        try:
            self.status = BookingStatus.SELECTING_TRAIN
            time.sleep(0.05)  # 50ms for page stabilization
            
            # 在选择车次之前，先检查并处理dhx_modal_cover
            self._handle_dhx_modal_cover()
            rows = self.driver.find_elements(By.XPATH, "//tbody[@id='queryLeftTable']/tr")
            for row in rows:
                try:
                    # 跳过无效行
                    cls = row.get_attribute("class") or ""
                    style = row.get_attribute("style") or ""
                    if "btm" in cls or "display: none" in style:
                        continue
                    
                    # 检查车次
                    train_text = ""
                    try:
                        train_td = row.find_element(By.XPATH, "./td[1]")
                        train_text = train_td.text.strip()
                    except Exception:
                        pass
                    
                    if not train_text or train_number not in train_text:
                        continue
                    
                    # 点击预订按钮
                    book = row.find_elements(By.XPATH, ".//a[contains(text(),'预订')]")
                    for b in book:
                        if b.is_displayed() and b.is_enabled():
                            self._safe_click(b)
                            if self._wait_for_order_page():
                                self.logger.info(f"已进入订单页（车次 {train_number}）")
                                return True
                    
                    # 兜底方案
                    try:
                        td13 = row.find_element(By.XPATH, "./td[13]")
                        links = td13.find_elements(By.TAG_NAME, "a")
                        for lk in links:
                            if lk.is_displayed() and lk.is_enabled():
                                self._safe_click(lk)
                                if self._wait_for_order_page():
                                    self.logger.info(f"已进入订单页（车次 {train_number}，td13 兜底）")
                                    return True
                    except Exception:
                        pass
                except Exception:
                    continue
            raise Exception(f"未找到可预订的目标车次 {train_number}")
        except Exception as e:
            self.logger.error(f"选择车次失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    def _wait_for_order_page(self) -> bool:
        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'乘客信息')]")),
                    EC.presence_of_element_located((By.XPATH, "//a[normalize-space(text())='提交订单']")),
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'选座喽') or contains(text(),'选铺喽')]"))
                )
            )
            time.sleep(0.05)  # 50ms for faster operation
            return True
        except TimeoutException:
            return False

    def select_passengers_and_seats(self, ticket_info: TicketInfo) -> bool:
        try:
            self.status = BookingStatus.SELECTING_SEATS
            wait = WebDriverWait(self.driver, self.wait_timeout)
            
            # 首先检查页面是否有需要处理的弹出框
            self._check_and_handle_any_dialog(wait)
            
            # 提取基础乘客列表用于选择
            passengers = ticket_info.passengers
            
            # 选择乘车人
            if not self._select_passengers_from_list(passengers, wait):
                self.logger.info("常用联系人列表未能选中，尝试搜索框选择...")
                if not self._select_passengers_by_search(passengers):
                    raise RuntimeError("未能选中任何乘车人")
            
            # 乘车人选择完成后，再次检查确认弹出框
            self._handle_passenger_selection_dialogs(wait)
            time.sleep(0.05)  # 50ms for faster operation
            
            # 设置席别/票种 - 传入完整的TicketInfo以获取席位信息
            if not self._assign_seat_and_ticket(ticket_info, wait):
                raise RuntimeError("设置席别/票种失败")
            
            # 席别设置后检查确认弹出框
            self._handle_confirmation_dialog(wait)
            time.sleep(0.03)  # 30ms for faster operation
            
            # 选座/选铺 - 使用TicketPassenger对象
            for ticket_passenger in ticket_info.ticket_passengers:
                self._pick_seat_position_for_passenger(ticket_passenger, wait)
                # 每次选座后检查确认弹出框
                self._handle_confirmation_dialog(wait)
                time.sleep(0.03)  # 30ms for faster operation
            
            # 最终检查是否还有未处理的确认弹出框
            self._handle_confirmation_dialog(wait)
            time.sleep(0.05)  # 50ms for faster operation
            
            self.logger.info("乘客与席别选择完成")
            return True
        except Exception as e:
            self.logger.error(f"选择乘客和席次失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    def submit_order(self) -> bool:
        try:
            self.status = BookingStatus.SUBMITTING_ORDER
            wait = WebDriverWait(self.driver, self.wait_timeout)
            
            # 在提交订单之前，先检查并处理dhx_modal_cover
            self._handle_dhx_modal_cover()
            
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space(text())='提交订单']")))
            self._safe_click(btn)
            time.sleep(0.1)  # 100ms for faster operation
            return True
        except Exception as e:
            self.logger.error(f"提交订单失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    def confirm_order(self) -> bool:
        try:
            self.status = BookingStatus.CONFIRMING_PAYMENT
            wait = WebDriverWait(self.driver, self.wait_timeout)
            
            # 在确认订单之前，先检查并处理dhx_modal_cover
            self._handle_dhx_modal_cover()
            
            btn = wait.until(EC.element_to_be_clickable((By.ID, "qr_submit_id")))
            self._safe_click(btn)
            time.sleep(0.1)  # 100ms for order confirmation
            self.status = BookingStatus.SUCCESS
            return True
        except Exception as e:
            self.logger.error(f"确认订单失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    def auto_book_ticket(self, ticket_info: TicketInfo) -> bool:
        try:
            self.logger.info(f"开始自动预订: {ticket_info.train_info.train_number}")
            # 1. 打开浏览器并等待登录（不填充搜索表单）
            if not self.open_browser_and_wait_for_login():
                return False
            
            # 2. 登录成功后，填充搜索表单
            self._fill_search_form(
                ticket_info.train_info.departure_station,
                ticket_info.train_info.arrival_station,
                ticket_info.train_info.date
            )
            
            # 3. 搜索车票
            if not self.search_tickets():
                return False
            if not self.select_train(ticket_info.train_info.train_number):
                return False
            if not self.select_passengers_and_seats(ticket_info):
                return False
            if not self.submit_order():
                return False
            if not self.confirm_order():
                return False
            self.logger.info("自动预订成功完成")
            return True
        except Exception as e:
            self.logger.error(f"自动预订失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False

    # ----------------- 辅助方法 ----------------
    def _exists(self, locator) -> bool:
        try:
            self.driver.find_element(*locator)
            return True
        except NoSuchElementException:
            return False

    def _safe_click(self, el):
        try:
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            el.click()

    def _scroll_into_view(self, el):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass

    def _normalize_seat_texts(self, seat: str) -> List[str]:
        s = (str(seat) or "").strip()
        mapping = {
            "二等": "二等座", "一等": "一等座", "商务": "商务座",
            "硬座": "硬座", "软座": "软座", "无": "无座",
            "硬卧": "硬卧", "软卧": "软卧", "动卧": "动卧",
            "高级软卧": "高级软卧", "一等卧": "一等卧", "二等卧": "二等卧"
        }
        base = mapping.get(s, s)
        alts = {base, s}
        if base.endswith("座") and base != "无座":
            alts.add(base.replace("座", ""))
        return [t for t in alts if t]

    def _normalize_ticket_texts(self, ticket_type: str) -> List[str]:
        t = (str(ticket_type) or "成人票").strip()
        alts = {t}
        if t.endswith("票"):
            alts.add(t[:-1])
        else:
            alts.add(t + "票")
        return list(alts)

    def _handle_confirmation_dialog(self, wait: WebDriverWait = None, timeout: int = 5) -> bool:
        """简化版12306确认弹窗处理 - 针对常见的确认按钮"""
        if wait is None:
            wait = WebDriverWait(self.driver, timeout)
        
        try:
            # 首先专门处理儿童购票确认弹窗
            if self._handle_children_ticket_dialog():
                return True
            
            # 12306最常用的确认按钮模式 - 按优先级排序
            confirm_button_patterns = [
                # 确认按钮
                "//button[normalize-space(text())='确认']",
                "//button[contains(normalize-space(text()),'确认')]",
                "//a[normalize-space(text())='确认']",
                "//a[contains(normalize-space(text()),'确认')]",
                
                # 确定按钮
                "//button[normalize-space(text())='确定']",
                "//button[contains(normalize-space(text()),'确定')]",
                "//a[normalize-space(text())='确定']",
                "//a[contains(normalize-space(text()),'确定')]",
                
                # 是按钮
                "//button[normalize-space(text())='是']",
                "//a[normalize-space(text())='是']",
                
                # 继续按钮
                "//button[normalize-space(text())='继续']",
                "//a[normalize-space(text())='继续']",
                
                # class选择器备用方案
                "//button[contains(@class,'confirm')]",
                "//button[contains(@class,'btn-primary')]",
                "//button[contains(@class,'btn-ok')]"
            ]
            
            # 尝试点击确认按钮
            for pattern in confirm_button_patterns:
                try:
                    elements = self.driver.find_elements(By.XPATH, pattern)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            try:
                                element.click()
                                self.logger.info(f"成功点击确认按钮: {pattern}")
                                time.sleep(0.05)  # 50ms for popup close
                                return True
                            except Exception as e:
                                self.logger.debug(f"点击按钮失败 {pattern}: {e}")
                                continue
                except Exception:
                    continue
            
            # 尝试处理JavaScript alert
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                self.logger.info(f"检测到JavaScript弹窗: {alert_text}")
                # 如果包含确认关键词，则接受
                if any(keyword in alert_text for keyword in ['确认', '确定', '是', '同意', '继续']):
                    alert.accept()
                    self.logger.info("成功确认JavaScript弹窗")
                    return True
            except Exception:
                pass
            
            # 尝试通过键盘确认
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ENTER)
                self.logger.info("尝试通过Enter键确认")
                time.sleep(0.05)  # 50ms for keyboard confirmation
                return True
            except Exception:
                pass
            
            self.logger.debug("未找到需要确认的弹窗")
            return True
            
        except Exception as e:
            self.logger.error(f"处理确认弹窗时发生异常: {e}")
            return False
    
    def _handle_children_ticket_dialog(self) -> bool:
        """专门处理儿童购票确认弹窗"""
        try:
            # 检查是否包含儿童购票确认的特定文本
            children_ticket_patterns = [
                "//div[contains(.,'儿童乘车，超过一名时，超过人数应购买儿童优惠票')]",
                "//div[contains(.,'未满6周岁且不单独占用席位的儿童乘车')]",
                "//div[contains(.,'是否确定要为儿童单独购买席位')]",
                "//div[contains(.,'免费乘车儿童可以在购票成功后添加')]",
                "//div[contains(.,'自2023年1月1日起')]"
            ]
            
            # 检查页面是否包含儿童购票弹窗
            for pattern in children_ticket_patterns:
                try:
                    elements = self.driver.find_elements(By.XPATH, pattern)
                    for element in elements:
                        if element.is_displayed():
                            self.logger.info("检测到儿童购票确认弹窗")
                            # 寻找确认按钮
                            confirm_patterns = [
                                "//button[normalize-space(text())='确认']",
                                "//button[contains(normalize-space(text()),'确认')]",
                                "//a[normalize-space(text())='确认']",
                                "//a[contains(normalize-space(text()),'确认')]",
                                "//button[normalize-space(text())='确定']"
                            ]
                            
                            for confirm_pattern in confirm_patterns:
                                try:
                                    confirm_buttons = self.driver.find_elements(By.XPATH, confirm_pattern)
                                    for button in confirm_buttons:
                                        if button.is_displayed() and button.is_enabled():
                                            button.click()
                                            self.logger.info("成功确认儿童购票弹窗")
                                            time.sleep(0.05)  # 50ms for popup close
                                            return True
                                except Exception:
                                    continue
                            
                            # 如果没有找到确认按钮，尝试键盘确认
                            try:
                                body = self.driver.find_element(By.TAG_NAME, "body")
                                body.send_keys(Keys.ENTER)
                                self.logger.info("通过Enter键确认儿童购票弹窗")
                                time.sleep(0.05)  # 50ms for keyboard confirmation
                                return True
                            except Exception:
                                pass
                            
                            return False
                except Exception:
                    continue
            
            return False
        except Exception as e:
            self.logger.debug(f"处理儿童购票弹窗异常: {e}")
            return False
    
    def _detect_system_dialog(self) -> dict:
        """检测12306系统提示框"""
        # 12306常用的系统提示框特征
        patterns = [
            # 带有特定class的弹窗
            "//div[contains(@class,'layer-') and contains(@class,'-page')]",
            "//div[contains(@class,'layui-layer')]",
            "//div[contains(@class,'el-message-box')]",
            "//div[@id='layer']",
            
            # 带有特定文本的弹窗
            "//div[contains(@class,'modal') and .//*[contains(text(),'提示')]]",
            "//div[contains(@class,'dialog') and .//*[contains(text(),'确认')]]",
            "//div[contains(@class,'popup') and .//*[contains(text(),'乘车人')]]",
            
            # 12306特有的弹窗结构
            "//div[@class='ui-dialog']",
            "//div[contains(@class,'ticket-')]",
            "//div[contains(@class,'order-')]"
        ]
        
        for pattern in patterns:
            try:
                elements = self.driver.find_elements(By.XPATH, pattern)
                for element in elements:
                    if element.is_displayed():
                        return {
                            'type': 'system_dialog',
                            'element': element,
                            'pattern': pattern
                        }
            except Exception:
                continue
        
        return None
    
    def _handle_dhx_modal_cover(self) -> bool:
        """处理dhtmlx modal cover遮罩层"""
        try:
            # 检查是否有dhx_modal_cover遮罩层
            modal_covers = self.driver.find_elements(By.XPATH, "//div[contains(@class,'dhx_modal_cover')]")
            for cover in modal_covers:
                if cover.is_displayed():
                    self.logger.info("检测到dhx_modal_cover遮罩层，尝试关闭...")
                    
                    # 尝试点击遮罩层关闭
                    try:
                        cover.click()
                        time.sleep(0.1)
                        self.logger.info("成功点击关闭dhx_modal_cover遮罩层")
                        return True
                    except:
                        pass
                    
                    # 尝试按ESC键关闭
                    try:
                        from selenium.webdriver.common.keys import Keys
                        cover.send_keys(Keys.ESCAPE)
                        time.sleep(0.1)
                        self.logger.info("成功通过ESC键关闭dhx_modal_cover遮罩层")
                        return True
                    except:
                        pass
                    
                    # 尝试执行JavaScript移除遮罩层
                    try:
                        self.driver.execute_script("arguments[0].remove();", cover)
                        time.sleep(0.1)
                        self.logger.info("成功通过JavaScript移除dhx_modal_cover遮罩层")
                        return True
                    except:
                        pass
                    
                    # 尝试隐藏遮罩层
                    try:
                        self.driver.execute_script("arguments[0].style.display='none';", cover)
                        time.sleep(0.1)
                        self.logger.info("成功通过JavaScript隐藏dhx_modal_cover遮罩层")
                        return True
                    except:
                        pass
            
            return False
        except Exception as e:
            self.logger.warning(f"处理dhx_modal_cover遮罩层失败: {e}")
            return False
    
    def _detect_overlay_dialog(self) -> dict:
        """检测遮罩层弹窗"""
        # 检查遮罩层
        overlay_patterns = [
            "//div[contains(@class,'layui-layer-shade')]",
            "//div[contains(@class,'el-overlay')]",
            "//div[contains(@class,'v-modal')]",
            "//div[contains(@class,'modal-backdrop')]",
            "//div[contains(@class,'ui-widget-overlay')]",
            "//div[contains(@class,'dhx_modal_cover')]"
        ]
        
        for pattern in overlay_patterns:
            try:
                overlays = self.driver.find_elements(By.XPATH, pattern)
                for overlay in overlays:
                    if overlay.is_displayed():
                        # 找到对应的弹窗
                        dialog_patterns = [
                            "//div[contains(@class,'layui-layer') and not(contains(@style,'display: none'))]",
                            "//div[contains(@class,'el-message-box')]",
                            "//div[@role='dialog']",
                            "//div[contains(@class,'modal')]"
                        ]
                        
                        for dialog_pattern in dialog_patterns:
                            try:
                                dialogs = self.driver.find_elements(By.XPATH, dialog_pattern)
                                for dialog in dialogs:
                                    if dialog.is_displayed():
                                        return {
                                            'type': 'overlay_dialog',
                                            'element': dialog,
                                            'overlay': overlay,
                                            'pattern': dialog_pattern
                                        }
                            except Exception:
                                continue
            except Exception:
                continue
        
        return None
    
    def _detect_framework_dialog(self) -> dict:
        """检测特定前端框架的弹窗"""
        framework_patterns = [
            # Element UI
            "//div[contains(@class,'el-message-box__wrapper')]",
            "//div[contains(@class,'el-dialog__wrapper')]",
            
            # Layui
            "//div[contains(@class,'layui-layer-wrap')]",
            
            # Bootstrap
            "//div[contains(@class,'modal') and contains(@class,'show')]",
            
            # jQuery UI
            "//div[contains(@class,'ui-dialog') and contains(@class,'ui-widget')]"
        ]
        
        for pattern in framework_patterns:
            try:
                elements = self.driver.find_elements(By.XPATH, pattern)
                for element in elements:
                    if element.is_displayed():
                        return {
                            'type': 'framework_dialog',
                            'element': element,
                            'framework': pattern.split("'")[1].split('-')[0],
                            'pattern': pattern
                        }
            except Exception:
                continue
        
        return None
    
    def _detect_javascript_dialog(self) -> dict:
        """检测JavaScript原生对话框"""
        # JavaScript alert/confirm/prompt无法直接通过DOM检测
        # 但可以通过检查页面状态来判断
        try:
            # 检查页面是否被阻塞（可能是由于JavaScript对话框）
            current_url = self.driver.current_url
            # 简单的页面活跃度检查
            body = self.driver.find_element(By.TAG_NAME, "body")
            body_text = body.text
            
            # 如果页面文本包含特定的确认信息
            if any(keyword in body_text for keyword in ['确认', '确定', '提示', '警告']):
                return {
                    'type': 'javascript_dialog',
                    'element': body,
                    'text': body_text
                }
        except Exception:
            pass
        
        return None
    
    def _confirm_by_text_buttons(self, dialog_info: dict, wait: WebDriverWait) -> bool:
        """通过文本按钮确认弹窗"""
        button_patterns = [
            # 主要确认按钮
            "//button[normalize-space(text())='确认']",
            "//button[contains(normalize-space(text()),'确认')]",
            "//a[normalize-space(text())='确认']",
            "//a[contains(normalize-space(text()),'确认')]",
            
            # 确定按钮
            "//button[normalize-space(text())='确定']",
            "//button[contains(normalize-space(text()),'确定')]",
            "//a[normalize-space(text())='确定']",
            "//a[contains(normalize-space(text()),'确定')]",
            
            # 是/同意按钮
            "//button[normalize-space(text())='是']",
            "//button[normalize-space(text())='同意']",
            "//a[normalize-space(text())='是']",
            "//a[normalize-space(text())='同意']",
            
            # OK/Yes按钮
            "//button[normalize-space(text())='OK']",
            "//button[normalize-space(text())='Yes']",
            "//a[normalize-space(text())='OK']",
            "//a[normalize-space(text())='Yes']",
            
            # 提交/继续按钮
            "//button[contains(normalize-space(text()),'提交')]",
            "//button[contains(normalize-space(text()),'继续')]",
            "//a[contains(normalize-space(text()),'提交')]",
            "//a[contains(normalize-space(text()),'继续')]"
        ]
        
        for pattern in button_patterns:
            try:
                buttons = self.driver.find_elements(By.XPATH, pattern)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        self._scroll_into_view(button)
                        self._safe_click(button)
                        return True
            except Exception:
                continue
        
        return False
    
    def _confirm_by_class_buttons(self, dialog_info: dict, wait: WebDriverWait) -> bool:
        """通过class属性确认弹窗"""
        class_patterns = [
            "//button[contains(@class,'confirm')]",
            "//button[contains(@class,'submit')]",
            "//button[contains(@class,'ok')]",
            "//button[contains(@class,'yes')]",
            "//a[contains(@class,'confirm')]",
            "//a[contains(@class,'submit')]",
            "//a[contains(@class,'ok')]",
            "//a[contains(@class,'yes')]"
        ]
        
        for pattern in class_patterns:
            try:
                buttons = self.driver.find_elements(By.XPATH, pattern)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        self._scroll_into_view(button)
                        self._safe_click(button)
                        return True
            except Exception:
                continue
        
        return False
    
    def _confirm_by_id_buttons(self, dialog_info: dict, wait: WebDriverWait) -> bool:
        """通过id属性确认弹窗"""
        id_patterns = [
            "//button[contains(@id,'confirm')]",
            "//button[contains(@id,'submit')]",
            "//button[contains(@id,'ok')]",
            "//button[contains(@id,'yes')]",
            "//a[contains(@id,'confirm')]",
            "//a[contains(@id,'submit')]",
            "//a[contains(@id,'ok')]",
            "//a[contains(@id,'yes')]"
        ]
        
        for pattern in id_patterns:
            try:
                buttons = self.driver.find_elements(By.XPATH, pattern)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        self._scroll_into_view(button)
                        self._safe_click(button)
                        return True
            except Exception:
                continue
        
        return False
    
    def _confirm_javascript_dialog(self, dialog_info: dict, wait: WebDriverWait) -> bool:
        """确认JavaScript原生对话框"""
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            self.logger.info(f"JavaScript对话框: {alert_text}")
            
            # 尝试接受对话框
            if any(keyword in alert_text for keyword in ['确认', '确定', '是', '同意', '继续']):
                alert.accept()
                return True
            else:
                # 如果不确定，先接受
                alert.accept()
                return True
        except Exception:
            return False
    
    def _confirm_by_keyboard(self, dialog_info: dict, wait: WebDriverWait) -> bool:
        """通过键盘快捷键确认弹窗"""
        try:
            from selenium.webdriver.common.keys import Keys
            
            # 尝试按Enter键确认
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ENTER)
            time.sleep(0.03)  # 30ms for faster operation
            return True
        except Exception:
            try:
                # 尝试按ESC键关闭
                from selenium.webdriver.common.keys import Keys
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ESCAPE)
                time.sleep(0.03)  # 30ms for faster operation
                return True
            except Exception:
                return False

    def _handle_12306_specific_dialogs(self, wait: WebDriverWait) -> bool:
        """处理12306特定的弹窗场景"""
        try:
            # 12306乘车人选择后的确认弹窗特征
            specific_patterns = [
                # 乘车人信息确认
                {
                    'name': '乘车人确认',
                    'patterns': [
                        "//div[contains(@class,'layer') and .//*[contains(text(),'乘车人')]]",
                        "//div[contains(@class,'modal') and .//*[contains(text(),'请确认乘车人信息')]]",
                        "//div[contains(@class,'dialog') and .//*[contains(text(),'您选择的乘车人')]]"
                    ],
                    'buttons': ["//button[normalize-space(text())='确认']", "//a[normalize-space(text())='确认']"]
                },
                
                # 席别确认
                {
                    'name': '席别确认',
                    'patterns': [
                        "//div[contains(@class,'layer') and .//*[contains(text(),'席别')]]",
                        "//div[contains(@class,'modal') and .//*[contains(text(),'请确认席别')]]",
                        "//div[contains(@class,'dialog') and .//*[contains(text(),'您选择的席别')]]"
                    ],
                    'buttons': ["//button[normalize-space(text())='确认']", "//a[normalize-space(text())='确认']"]
                },
                
                # 座位确认
                {
                    'name': '座位确认',
                    'patterns': [
                        "//div[contains(@class,'layer') and .//*[contains(text(),'座位')]]",
                        "//div[contains(@class,'modal') and .//*[contains(text(),'请确认座位')]]",
                        "//div[contains(@class,'dialog') and .//*[contains(text(),'您选择的座位')]]"
                    ],
                    'buttons': ["//button[normalize-space(text())='确认']", "//a[normalize-space(text())='确认']"]
                },
                
                # 12306通用确认
                {
                    'name': '通用确认',
                    'patterns': [
                        "//div[contains(@class,'layui-layer') and .//*[contains(text(),'确认')]]",
                        "//div[contains(@class,'el-message-box') and .//*[contains(text(),'确认')]]",
                        "//div[@class='ui-dialog' and .//*[contains(text(),'确认')]]"
                    ],
                    'buttons': [
                        "//button[normalize-space(text())='确认']",
                        "//a[normalize-space(text())='确认']",
                        "//button[normalize-space(text())='确定']",
                        "//a[normalize-space(text())='确定']"
                    ]
                }
            ]
            
            for dialog_type in specific_patterns:
                # 检查是否存在该类型的弹窗
                dialog_found = False
                dialog_element = None
                
                for pattern in dialog_type['patterns']:
                    try:
                        elements = self.driver.find_elements(By.XPATH, pattern)
                        for element in elements:
                            if element.is_displayed():
                                dialog_found = True
                                dialog_element = element
                                self.logger.info(f"发现12306特定弹窗: {dialog_type['name']}")
                                break
                        if dialog_found:
                            break
                    except Exception:
                        continue
                
                if dialog_found:
                    # 尝试点击对应的确认按钮
                    for button_pattern in dialog_type['buttons']:
                        try:
                            buttons = self.driver.find_elements(By.XPATH, button_pattern)
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    self._scroll_into_view(button)
                                    self._safe_click(button)
                                    self.logger.info(f"成功确认{dialog_type['name']}弹窗")
                                    time.sleep(0.08)  # 80ms for faster operation
                                    return True
                        except Exception:
                            continue
                    
                    # 如果按钮点击失败，尝试键盘确认
                    try:
                        from selenium.webdriver.common.keys import Keys
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        body.send_keys(Keys.ENTER)
                        time.sleep(0.05)  # 50ms for faster operation
                        return True
                    except Exception:
                        continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"处理12306特定弹窗失败: {e}")
            return False
    
    def _enhanced_dialog_detection(self, wait: WebDriverWait) -> bool:
        """增强的弹窗检测，针对12306的具体场景"""
        # 先尝试12306特定弹窗处理
        if self._handle_12306_specific_dialogs(wait):
            return True
        
        # 然后尝试通用弹窗处理
        return self._handle_confirmation_dialog(wait, timeout=6)

    def _handle_passenger_selection_dialogs(self, wait: WebDriverWait) -> None:
        """专门处理乘车人选择过程中的各种弹出框"""
        self.logger.debug("检查乘车人选择过程中的弹出框...")
        
        # 直接使用简化版确认弹窗处理
        if self._handle_confirmation_dialog(wait, timeout=3):
            self.logger.info("乘车人选择弹出框处理完成")
        else:
            self.logger.debug("未检测到需要处理的乘车人选择弹出框")

    def _check_and_handle_any_dialog(self, wait: WebDriverWait) -> bool:
        """检查并处理任何类型的弹出框"""
        # 直接使用简化版确认弹窗处理
        return self._handle_confirmation_dialog(wait, timeout=3)

    def _select_passengers_from_list(self, passengers: List[Passenger], wait: WebDriverWait) -> bool:
        selected_any = False
        
        # 首先检查是否有弹出框需要处理
        self._check_and_handle_any_dialog(wait)
        
        # 展开更多按钮
        try:
            more_btn = self.driver.find_element(By.XPATH, "//*[contains(normalize-space(text()),'更多')]")
            if more_btn.is_displayed():
                self._safe_click(more_btn)
                time.sleep(0.03)  # 30ms for faster operation
                # 点击后检查是否有弹出框
                self._check_and_handle_any_dialog(wait)
        except Exception:
            pass
        
        # 定位乘客列表
        containers = []
        for xp in ["//ul[@id='normal_passenger_id']", "//ul[@id='dj_passenger_id']"]:
            try:
                c = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                containers.append(c)
            except TimeoutException:
                continue
        
        if not containers:
            return False
        
        # 选择乘客
        for p in passengers:
            found = False
            for c in containers:
                lis = c.find_elements(By.XPATH, ".//li[.//input[@type='checkbox']]")
                for li in lis:
                    try:
                        text = li.text.strip()
                        if p.name and p.name in text:
                            checkbox = li.find_element(By.XPATH, ".//input[@type='checkbox']")
                            self._scroll_into_view(li)
                            if not checkbox.is_selected():
                                self._safe_click(checkbox)
                                time.sleep(0.02)  # 20ms for faster operation
                                # 点击复选框后检查是否有确认弹出框
                                self._handle_passenger_selection_dialogs(wait)
                            found = True
                            selected_any = True
                            break
                    except Exception:
                        continue
                if found:
                    break
            if not found:
                self.logger.warning(f"未在常用乘车人列表中找到: {p.name}")
        
        # 所有乘客选择完成后，检查是否有最终确认弹出框
        if selected_any:
            self._handle_passenger_selection_dialogs(wait)
            time.sleep(0.05)  # 50ms for faster operation
        
        return selected_any

    def _select_passengers_by_search(self, passengers: List[Passenger]) -> bool:
        try:
            wait = WebDriverWait(self.driver, 5)
            
            # 首先检查是否有弹出框需要处理
            self._check_and_handle_any_dialog(wait)
            
            search_box = wait.until(
                EC.presence_of_element_located((By.ID, "quickQueryPassenger_id"))
            )
            try:
                search_btn = self.driver.find_element(By.ID, "submit_quickQueryPassenger")
            except NoSuchElementException:
                search_btn = None
            
            selected_any = False
            for p in passengers:
                try:
                    search_box.click()
                    time.sleep(0.1)
                    search_box.clear()
                    time.sleep(0.1)
                    search_box.send_keys(p.name)
                    if search_btn:
                        self._safe_click(search_btn)
                        # 点击搜索按钮后检查弹出框
                        self._handle_passenger_selection_dialogs(wait)
                    time.sleep(0.08)  # 80ms for faster operation
                    
                    # 在搜索结果中勾选
                    patterns = [
                        "//tbody[@id='normal_passenger_id']//tr",
                        "//tbody[@id='dj_passenger_id']//tr",
                        "//ul[@id='normal_passenger_id']//li",
                        "//ul[@id='dj_passenger_id']//li",
                        "//table//tr[.//input[@type='checkbox']]",
                    ]
                    chosen = False
                    for xp in patterns:
                        rows = self.driver.find_elements(By.XPATH, xp)
                        for r in rows:
                            try:
                                if p.name in r.text:
                                    cb = r.find_element(By.XPATH, ".//input[@type='checkbox']")
                                    self._scroll_into_view(r)
                                    if not cb.is_selected():
                                        self._safe_click(cb)
                                        # 勾选乘客后检查确认弹出框
                                        self._handle_passenger_selection_dialogs(wait)
                                    chosen = True
                                    selected_any = True
                                    break
                            except Exception:
                                continue
                        if chosen:
                            break
                    
                    # 清空搜索框
                    search_box.click()
                    time.sleep(0.1)
                    search_box.clear()
                    time.sleep(0.1)
                except Exception:
                    continue
            
            # 所有乘客搜索选择完成后，检查是否有最终确认弹出框
            if selected_any:
                self._handle_passenger_selection_dialogs(wait)
                time.sleep(0.05)  # 50ms for faster operation
            
            return selected_any
        except TimeoutException:
            return False

    def _locate_passenger_table(self):
        # 识别包含表头的表格
        tables = self.driver.find_elements(By.XPATH, "//table[.//th]")
        for t in tables:
            header_text = t.text
            if all(k in header_text for k in ["席别", "票种", "姓名"]):
                return t
        
        # 兜底方案
        try:
            return self.driver.find_element(By.XPATH, "//table[.//th[contains(.,'姓名')]]")
        except Exception:
            return None

    def _assign_seat_and_ticket(self, ticket_info: TicketInfo, wait: WebDriverWait) -> bool:
        """基于per-ticket表格分配席别和票种 - 支持多乘客"""
        # 优先定位per-ticket表格
        table = None
        for _ in range(5):
            try:
                table = self.driver.find_element(By.XPATH, "//table[@class='per-ticket']//tbody[@id='ticketInfo_id']")
                if table:
                    self.logger.info("成功定位per-ticket乘客信息表格")
                    break
            except Exception:
                pass
            
            # 备选方案：原有表格定位方法
            table = self._locate_passenger_table()
            if table:
                break
            
            time.sleep(0.05)  # 50ms for faster operation
        
        if not table:
            self.logger.warning("未能定位乘客信息表格，尝试直接在整页内按姓名找行")
        
        success = True
        # 预先收集所有可用的乘客行，建立索引映射
        passenger_rows = self._collect_passenger_rows(table, ticket_info.passengers)
        
        for i, ticket_passenger in enumerate(ticket_info.ticket_passengers):
            # 在处理每个乘客前检查是否有弹出框
            self._check_and_handle_any_dialog(wait)
            
            # 使用索引映射来为每个乘客分配对应的行
            ok_row = self._set_for_passenger_row_with_index(ticket_passenger, wait, table, i, passenger_rows)
            if not ok_row:
                success = False
                self.logger.error(f"乘客{i+1} {ticket_passenger.passenger.name} 席位设置失败")
            else:
                # 每个乘客席别设置成功后检查确认弹出框
                self._handle_confirmation_dialog(wait)
                time.sleep(0.03)  # 30ms for faster operation
        
        return success

    def _collect_passenger_rows(self, table, passengers: List[Passenger]) -> List[Any]:
        """收集所有可用的乘客行，建立索引映射"""
        passenger_rows = []
        
        if table:
            try:
                # 获取表格中所有包含输入框的行
                all_rows = table.find_elements(By.XPATH, ".//tr")
                # 找到包含席次选择下拉框的行（乘客信息行）
                for row in all_rows:
                    # 检查行是否包含席次选择下拉框
                    seat_selects = row.find_elements(By.XPATH, ".//select[starts-with(@id,'seatType_')]")
                    if seat_selects:
                        passenger_rows.append(row)
                
                self.logger.info(f"收集到 {len(passenger_rows)} 个乘客行")
                
                # 如果收集到的行数少于乘客数，尝试其他方法
                if len(passenger_rows) < len(passengers):
                    # 备选：查找包含乘客姓名输入的行
                    for row in all_rows:
                        name_inputs = row.find_elements(By.XPATH, ".//input[@placeholder='姓名' or contains(@name,'name')]")
                        if name_inputs:
                            if row not in passenger_rows:
                                passenger_rows.append(row)
                
                self.logger.info(f"最终收集到 {len(passenger_rows)} 个可用乘客行")
                
            except Exception as e:
                self.logger.warning(f"收集乘客行失败: {e}")
        else:
            # 全局查找
            try:
                rows = self.driver.find_elements(By.XPATH, "//tr[.//select[starts-with(@id,'seatType_')]]")
                passenger_rows.extend(rows)
                self.logger.info(f"全局收集到 {len(passenger_rows)} 个乘客行")
            except Exception as e:
                self.logger.warning(f"全局收集乘客行失败: {e}")
        
        return passenger_rows

    def _set_for_passenger_row_with_index(self, ticket_passenger: TicketPassenger, wait: WebDriverWait, table, index: int, passenger_rows: List[Any]) -> bool:
        """使用索引为乘客分配对应的行并设置席次"""
        row = None
        
        # 策略1：尝试通过姓名精确匹配
        if table:
            try:
                name_rows = table.find_elements(By.XPATH, f".//tr[.//*[contains(text(), '{ticket_passenger.passenger.name}')]]")
                for r in name_rows:
                    if ticket_passenger.passenger.name in r.text:
                        row = r
                        self.logger.info(f"通过姓名精确匹配定位到乘客行: {ticket_passenger.passenger.name} (索引{index})")
                        break
            except Exception as e:
                self.logger.debug(f"通过姓名精确匹配失败: {e}")
        
        # 策略2：如果姓名匹配失败，使用索引映射
        if not row and passenger_rows and index < len(passenger_rows):
            row = passenger_rows[index]
            self.logger.info(f"通过索引映射分配乘客行: {ticket_passenger.passenger.name} -> 行{index+1}")
        
        # 策略3：全局查找作为最后备选
        if not row:
            try:
                global_rows = self.driver.find_elements(By.XPATH, f"//tr[.//*[contains(text(), '{ticket_passenger.passenger.name}')]]")
                for r in global_rows:
                    if ticket_passenger.passenger.name in r.text:
                        row = r
                        self.logger.info(f"全局定位到乘客行: {ticket_passenger.passenger.name} (索引{index})")
                        break
            except Exception as e:
                self.logger.debug(f"全局定位失败: {e}")
        
        if not row:
            self.logger.error(f"无法为乘客 {ticket_passenger.passenger.name} (索引{index}) 分配对应的行")
            return False
        
        # 验证行是否包含必需的席次选择下拉框
        try:
            seat_select = row.find_element(By.XPATH, ".//select[starts-with(@id,'seatType_')]")
            self.logger.debug(f"验证乘客行 {ticket_passenger.passenger.name} 包含席次选择下拉框: {seat_select.get_attribute('id')}")
        except Exception as e:
            self.logger.warning(f"乘客行 {ticket_passenger.passenger.name} 缺少席次选择下拉框: {e}")
            # 尝试查找其他类型的下拉框
            try:
                selects = row.find_elements(By.XPATH, ".//select")
                if selects:
                    self.logger.info(f"乘客行 {ticket_passenger.passenger.name} 找到 {len(selects)} 个下拉框，将尝试使用")
                else:
                    self.logger.error(f"乘客行 {ticket_passenger.passenger.name} 没有找到任何下拉框")
                    return False
            except Exception:
                self.logger.error(f"乘客行 {ticket_passenger.passenger.name} 下拉框检查失败")
                return False
        
        self._scroll_into_view(row)
        time.sleep(0.03)  # 30ms for faster operation
        
        # 设置票种和席别 - 使用TicketPassenger对象的信息
        ticket_ok = True
        if hasattr(ticket_passenger, "ticket_type") and ticket_passenger.ticket_type:
            ticket_ok = self._set_ticket_type_in_row(row, ticket_passenger, wait)
            if not ticket_ok:
                self.logger.warning(f"设置票种失败: {ticket_passenger.passenger.name} -> {ticket_passenger.ticket_type}")
        
        seat_ok = True
        if hasattr(ticket_passenger, "seat_type") and ticket_passenger.seat_type:
            seat_ok = self._set_seat_type_in_row(row, ticket_passenger, wait)
            if not seat_ok:
                self.logger.warning(f"设置席别失败: {ticket_passenger.passenger.name} -> {ticket_passenger.seat_type.value}")
        
        return ticket_ok and seat_ok

    def _set_for_passenger_row(self, ticket_passenger: TicketPassenger, wait: WebDriverWait, table) -> bool:
        """在per-ticket表格中定位乘客行并设置席次"""
        # 定位乘客行 - 基于表格结构
        row = None
        
        if table:
            # 在per-ticket表格内查找乘客行
            try:
                # 方法1: 通过乘客姓名查找行
                name_rows = table.find_elements(By.XPATH, f".//tr[.//*[contains(text(), '{ticket_passenger.passenger.name}')]]")
                for r in name_rows:
                    if ticket_passenger.passenger.name in r.text:
                        row = r
                        self.logger.info(f"通过姓名定位到乘客行: {ticket_passenger.passenger.name}")
                        break
            except Exception as e:
                self.logger.debug(f"通过姓名定位乘客行失败: {e}")
            
            # 方法2: 如果有表格，按行索引查找（假设按添加顺序）
            if not row:
                try:
                    all_rows = table.find_elements(By.XPATH, ".//tr")
                    # 找到包含输入框的行（乘客信息行）
                    passenger_rows = [r for r in all_rows if r.find_elements(By.XPATH, ".//input")]
                    if passenger_rows:
                        # 简单策略：使用第一个可用行或按某种逻辑选择
                        row = passenger_rows[0]
                        self.logger.info(f"通过表格结构定位到乘客行: {ticket_passenger.passenger.name}")
                except Exception as e:
                    self.logger.debug(f"通过表格结构定位乘客行失败: {e}")
        else:
            # 全局查找 - 备选方案
            try:
                rows = self.driver.find_elements(By.XPATH, f"//tr[.//*[contains(text(), '{ticket_passenger.passenger.name}')]]")
                for r in rows:
                    if ticket_passenger.passenger.name in r.text:
                        row = r
                        self.logger.info(f"全局定位到乘客行: {ticket_passenger.passenger.name}")
                        break
            except Exception as e:
                self.logger.debug(f"全局定位乘客行失败: {e}")
        
        if not row:
            self.logger.warning(f"未找到乘客行: {ticket_passenger.passenger.name}")
            return False
        
        self._scroll_into_view(row)
        time.sleep(0.03)  # 30ms for faster operation
        
        # 设置票种和席别
        ticket_ok = True
        if getattr(ticket_passenger, "ticket_type", None):
            ticket_ok = self._set_ticket_type_in_row(row, ticket_passenger, wait)
            if not ticket_ok:
                self.logger.warning(f"设置票种失败: {ticket_passenger.passenger.name} -> {ticket_passenger.ticket_type}")
        
        seat_ok = True
        if getattr(ticket_passenger, "seat_type", None):
            seat_ok = self._set_seat_type_in_row(row, ticket_passenger, wait)
            if not seat_ok:
                self.logger.warning(f"设置席别失败: {ticket_passenger.passenger.name} -> {ticket_passenger.seat_type.value}")
        
        return ticket_ok and seat_ok

    def _set_seat_type_in_row(self, row, ticket_passenger: TicketPassenger, wait: WebDriverWait) -> bool:
        """基于per-ticket表格的席次选择 - 增强版本"""
        # 目标席别文本
        if hasattr(ticket_passenger.seat_type, "value"):
            seat_value = ticket_passenger.seat_type.value
        else:
            seat_value = str(ticket_passenger.seat_type or "")
        seat_texts = self._normalize_seat_texts(seat_value)
        
        # 根据HTML分析，优先在per-ticket表格内通过ID定位席次选择下拉框
        # 格式: seatType_1, seatType_2, seatType_3 等
        try:
            # 在当前行内查找席次选择下拉框，优先使用ID定位
            seat_select = row.find_element(By.XPATH, ".//select[starts-with(@id,'seatType_')]")
            opts = seat_select.find_elements(By.TAG_NAME, "option")
            
            # 记录可用选项用于调试
            available_options = [opt.text.strip() for opt in opts]
            self.logger.debug(f"席次选择下拉框选项: {available_options}")
            
            for t in seat_texts:
                match = None
                for o in opts:
                    tx = o.text.strip()
                    # 精确匹配或包含匹配
                    if tx == t or (t and t in tx):
                        match = tx
                        break
                
                if match:
                    try:
                        Select(seat_select).select_by_visible_text(match)
                        self.logger.info(f"席次选择成功(表格内): {ticket_passenger.passenger.name} -> {match}")
                        time.sleep(0.03)  # 30ms for faster operation
                        return True
                    except Exception as select_e:
                        self.logger.warning(f"席次选择操作失败: {select_e}")
                        continue
            else:
                self.logger.warning(f"在席次下拉框中未找到匹配项: {seat_texts}, 可用选项: {available_options}")
        except Exception as e:
            self.logger.debug(f"通过ID定位席次下拉框失败: {e}")
        
        # 备选方案1：在行内查找所有select元素并智能识别
        try:
            selects = row.find_elements(By.XPATH, ".//select")
            for i, sel in enumerate(selects):
                opts = sel.find_elements(By.TAG_NAME, "option")
                opt_texts = [o.text.strip() for o in opts]
                
                # 检查是否是席次选择框（包含席次相关选项）
                if any(any(seat in opt for seat in ["座", "卧", "商务", "一等", "二等", "硬", "软"]) for opt in opt_texts):
                    self.logger.debug(f"发现备选席次选择框{i+1}，选项: {opt_texts}")
                    
                    for t in seat_texts:
                        match = None
                        for o in opts:
                            tx = o.text.strip()
                            if tx == t or (t and t in tx):
                                match = tx
                                break
                        if match:
                            try:
                                Select(sel).select_by_visible_text(match)
                                self.logger.info(f"席次选择成功(备选框{i+1}): {ticket_passenger.passenger.name} -> {match}")
                                time.sleep(0.03)  # 30ms for faster operation
                                return True
                            except Exception as select_e:
                                self.logger.warning(f"备选席次选择操作失败: {select_e}")
                                continue
        except Exception as e:
            self.logger.debug(f"备选席次选择框查找失败: {e}")
        
        # 备选方案2：在整个per-ticket表格内查找席次选择
        try:
            if hasattr(row, 'find_element'):
                # 向上查找per-ticket表格
                per_ticket_table = row.find_element(By.XPATH, "./ancestor::table[@class='per-ticket']")
                seat_selects = per_ticket_table.find_elements(By.XPATH, ".//select[starts-with(@id,'seatType_')]")
                
                for sel in seat_selects:
                    opts = sel.find_elements(By.TAG_NAME, "option")
                    opt_texts = [o.text.strip() for o in opts]
                    
                    for t in seat_texts:
                        match = None
                        for o in opts:
                            tx = o.text.strip()
                            if tx == t or (t and t in tx):
                                match = tx
                                break
                        if match:
                            try:
                                Select(sel).select_by_visible_text(match)
                                self.logger.info(f"席次选择成功(表格范围): {ticket_passenger.passenger.name} -> {match}")
                                time.sleep(0.03)  # 30ms for faster operation
                                return True
                            except Exception as select_e:
                                self.logger.warning(f"表格范围席次选择失败: {select_e}")
                                continue
        except Exception as e:
            self.logger.debug(f"表格范围席次查找失败: {e}")
        
        # 备选方案3：尝试原有的"选座喽"弹窗方案
        try:
            # 检查是否存在选座弹窗
            seat_widgets = self.driver.find_elements(By.XPATH, "//*[contains(normalize-space(),'选座喽') or contains(normalize-space(),'席别选择')]")
            if seat_widgets:
                self.logger.info("发现选座弹窗，尝试弹窗选择方案")
                return self._original_seat_selection_method(ticket_passenger, wait)
        except Exception as e:
            self.logger.debug(f"弹窗选择方案检查失败: {e}")
        
        self.logger.error(f"席次选择失败，所有方案都尝试过了: {ticket_passenger.passenger.name} -> {seat_texts}")
        return False

    def _original_seat_selection_method(self, ticket_passenger: TicketPassenger, wait: WebDriverWait) -> bool:
        """原有的选座弹窗方法 - 作为备用方案"""
        try:
            # 查找选座弹窗
            widget = self.driver.find_element(By.XPATH, "//*[contains(normalize-space(),'选座喽')]")
            self._scroll_into_view(widget)
            
            # 目标席别文本
            if hasattr(ticket_passenger.seat_type, "value"):
                seat_value = ticket_passenger.seat_type.value
            else:
                seat_value = str(ticket_passenger.seat_type or "")
            seat_texts = self._normalize_seat_texts(seat_value)
            
            # 尝试点击匹配的席别按钮
            for t in seat_texts:
                try:
                    btn = widget.find_element(By.XPATH, f".//*[normalize-space(text())='{t}']")
                    if btn.is_displayed() and btn.is_enabled():
                        self._safe_click(btn)
                        self.logger.info(f"席次选择成功(弹窗): {ticket_passenger.passenger.name} -> {t}")
                        time.sleep(0.03)  # 30ms for faster operation
                        
                        # 如果需要铺位选择
                        if hasattr(ticket_passenger, "bunk_type") and ticket_passenger.bunk_type:
                            return self._original_bunk_selection_method(ticket_passenger, wait)
                        
                        return True
                except Exception:
                    continue
            
            return False
        except Exception as e:
            self.logger.debug(f"原有选座方法失败: {e}")
            return False

    def _original_bunk_selection_method(self, ticket_passenger: TicketPassenger, wait: WebDriverWait) -> bool:
        """原有的铺位选择方法 - 作为备用方案"""
        try:
            pos = ticket_passenger.bunk_type.value if hasattr(ticket_passenger, "bunk_type") and ticket_passenger.bunk_type else None
            if not pos:
                return False
            
            # 查找铺位选择弹窗
            widget = self.driver.find_element(By.XPATH, "//*[contains(normalize-space(),'选铺喽')]")
            self._scroll_into_view(widget)
            
            # 尝试点击匹配的铺位按钮
            candidates = []
            if pos in ("下铺", "中铺", "上铺"):
                candidates = [pos]
            
            for candidate in candidates:
                try:
                    btn = widget.find_element(By.XPATH, f".//*[normalize-space(text())='{candidate}']")
                    if btn.is_displayed() and btn.is_enabled():
                        self._safe_click(btn)
                        self.logger.info(f"铺位选择成功(弹窗): {ticket_passenger.passenger.name} -> {candidate}")
                        time.sleep(0.03)  # 30ms for faster operation
                        return True
                except Exception:
                    continue
            
            return False
        except Exception as e:
            self.logger.debug(f"原有铺位选择方法失败: {e}")
            return False

    def _set_ticket_type_in_row(self, row, ticket_passenger: TicketPassenger, wait: WebDriverWait) -> bool:
        """设置票种 - 智能检查12306默认值，只在冲突时修改"""
        expected_ticket_type = getattr(ticket_passenger, "ticket_type", "成人票")
        t_texts = self._normalize_ticket_texts(expected_ticket_type)
        
        # 1) 原生 select - 智能处理默认值
        selects = row.find_elements(By.XPATH, ".//select")
        for sel in selects:
            try:
                opts = sel.find_elements(By.TAG_NAME, "option")
                if not any(("票" in (o.text or "")) or (o.text or "").strip() in ("成人", "儿童", "学生", "残军") for o in opts):
                    continue
                
                # 检查12306的默认值
                default_value = None
                available_options = []
                
                for opt in opts:
                    opt_text = (opt.text or "").strip()
                    available_options.append(opt_text)
                    # 检查是否是默认选中的选项
                    if opt.get_attribute("selected") == "selected" or opt.get_attribute("selected") == True:
                        default_value = opt_text
                
                self.logger.debug(f"乘客 {ticket_passenger.passenger.name}: 12306默认票种={default_value}, 期望票种={expected_ticket_type}, 可选选项={available_options}")
                
                # 如果没有默认值，设置我们的期望值
                if not default_value:
                    self.logger.info(f"乘客 {ticket_passenger.passenger.name}: 未检测到默认票种，设置为 {expected_ticket_type}")
                    return self._select_ticket_option(sel, t_texts)
                
                # 检查默认值是否与期望值匹配
                if self._is_ticket_type_match(default_value, expected_ticket_type):
                    self.logger.info(f"乘客 {ticket_passenger.passenger.name}: 12306默认票种 {default_value} 与期望值 {expected_ticket_type} 匹配，保持默认")
                    return True
                
                # 默认值与期望值不匹配，需要修改
                self.logger.warning(f"乘客 {ticket_passenger.passenger.name}: 12306默认票种 {default_value} 与期望值 {expected_ticket_type} 不匹配，进行修改")
                return self._select_ticket_option(sel, t_texts)
                
            except Exception as e:
                self.logger.debug(f"原生select票种选择异常: {e}")
                continue
        
        # 2) el-select - 智能处理默认值
        try:
            trigger = row.find_element(By.XPATH, ".//*[contains(@class,'el-select')]")
            
            # 检查当前显示的值（默认值）
            try:
                current_value_element = trigger.find_element(By.XPATH, ".//span[contains(@class,'el-select__selection')]")
                current_value = (current_value_element.text or "").strip()
                self.logger.debug(f"乘客 {ticket_passenger.passenger.name}: el-select当前票种={current_value}, 期望票种={expected_ticket_type}")
                
                # 检查当前值是否与期望值匹配
                if self._is_ticket_type_match(current_value, expected_ticket_type):
                    self.logger.info(f"乘客 {ticket_passenger.passenger.name}: el-select当前票种 {current_value} 与期望值 {expected_ticket_type} 匹配，保持默认")
                    return True
                
                # 不匹配，需要修改
                self.logger.warning(f"乘客 {ticket_passenger.passenger.name}: el-select当前票种 {current_value} 与期望值 {expected_ticket_type} 不匹配，进行修改")
                
            except Exception:
                self.logger.debug("无法读取el-select当前值，尝试设置期望值")
            
            # 点击展开选项
            self._safe_click(trigger)
            panel = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//div[contains(@class,'el-select-dropdown') and not(contains(@style,'display: none'))]")
            ))
            
            for t in t_texts:
                try:
                    opt = panel.find_element(By.XPATH, f".//li//*[normalize-space(text())='{t}']")
                    self._safe_click(opt)
                    time.sleep(0.02)  # 20ms for faster operation
                    self.logger.info(f"乘客 {ticket_passenger.passenger.name}: el-select票种设置为 {t}")
                    return True
                except NoSuchElementException:
                    t_alt = t[:-1] if t.endswith("票") else t + "票"
                    try:
                        opt = panel.find_element(By.XPATH, f".//li//*[normalize-space(text())='{t_alt}']")
                        self._safe_click(opt)
                        time.sleep(0.02)  # 20ms for faster operation
                        self.logger.info(f"乘客 {ticket_passenger.passenger.name}: el-select票种设置为 {t_alt}")
                        return True
                    except NoSuchElementException:
                        continue
        except Exception as e:
            self.logger.debug(f"el-select票种选择异常: {e}")
        
        self.logger.error(f"乘客 {ticket_passenger.passenger.name}: 票种设置失败，期望值: {expected_ticket_type}")
        return False

    def _select_ticket_option(self, select_element, t_texts: List[str]) -> bool:
        """在select元素中选择票种选项"""
        try:
            opts = select_element.find_elements(By.TAG_NAME, "option")
            all_opts = [o.text.strip() for o in opts]
            
            for t in t_texts:
                if t in all_opts:
                    Select(select_element).select_by_visible_text(t)
                    time.sleep(0.02)  # 20ms for faster operation
                    return True
                # 兼容不带"票"的文本
                t_alt = t[:-1] if t.endswith("票") else t + "票"
                if t_alt in all_opts:
                    Select(select_element).select_by_visible_text(t_alt)
                    time.sleep(0.02)  # 20ms for faster operation
                    return True
        except Exception as e:
            self.logger.debug(f"选择票种选项失败: {e}")
        return False

    def _is_ticket_type_match(self, actual: str, expected: str) -> bool:
        """检查票种是否匹配（兼容不同的格式）"""
        if not actual or not expected:
            return False
        
        # 标准化比较
        actual_clean = actual.strip().replace("票", "")
        expected_clean = expected.strip().replace("票", "")
        
        # 直接匹配
        if actual_clean == expected_clean:
            return True
        
        # 特殊映射
        ticket_type_mapping = {
            "成人": ["1", "成人"],
            "儿童": ["2", "儿童"], 
            "学生": ["3", "学生"],
            "残军": ["4", "残军"]
        }
        
        # 检查映射关系
        for key, values in ticket_type_mapping.items():
            if actual_clean in values and expected_clean in values:
                return True
        
        return False

    def _pick_seat_position_for_passenger(self, ticket_passenger: TicketPassenger, wait: WebDriverWait) -> bool:
        """铺位/座位位置选择 - 基于per-ticket表格的增强实现"""
        try:
            pos = None
            if hasattr(ticket_passenger, "bunk_type") and getattr(ticket_passenger, "bunk_type", None) and hasattr(ticket_passenger.bunk_type, "value"):
                pos = ticket_passenger.bunk_type.value
            elif hasattr(ticket_passenger, "seat_pos") and getattr(ticket_passenger, "seat_pos", None):
                pos = str(ticket_passenger.seat_pos)
            if not pos:
                return False
            
            pos = pos.strip()
            self.logger.debug(f"开始铺位选择: {ticket_passenger.passenger.name} -> {pos}")
            
            # 方案1：在per-ticket表格内通过ID定位铺位选择下拉框
            # 根据HTML分析，铺位选择可能通过ticketype_X下拉框实现
            try:
                # 优先在per-ticket表格内查找铺位选择下拉框
                per_ticket_tables = self.driver.find_elements(By.XPATH, "//table[@class='per-ticket']")
                
                for table in per_ticket_tables:
                    bunk_selects = table.find_elements(By.XPATH, ".//select[starts-with(@id,'ticketype_')]")
                    
                    for sel in bunk_selects:
                        opts = sel.find_elements(By.TAG_NAME, "option")
                        opt_texts = [o.text.strip() for o in opts]
                        
                        self.logger.debug(f"发现铺位选择下拉框，选项: {opt_texts}")
                        
                        # 检查是否包含铺位选项
                        if any("铺" in opt for opt in opt_texts):
                            # 根据铺位偏好进行选择
                            if pos == "下铺" and any("下铺" in opt for opt in opt_texts):
                                try:
                                    Select(sel).select_by_visible_text("下铺")
                                    self.logger.info(f"铺位选择成功(表格内): {ticket_passenger.passenger.name} -> 下铺")
                                    return True
                                except Exception as select_e:
                                    self.logger.warning(f"下铺选择失败: {select_e}")
                            elif pos == "中铺" and any("中铺" in opt for opt in opt_texts):
                                try:
                                    Select(sel).select_by_visible_text("中铺")
                                    self.logger.info(f"铺位选择成功(表格内): {ticket_passenger.passenger.name} -> 中铺")
                                    return True
                                except Exception as select_e:
                                    self.logger.warning(f"中铺选择失败: {select_e}")
                            elif pos == "上铺" and any("上铺" in opt for opt in opt_texts):
                                try:
                                    Select(sel).select_by_visible_text("上铺")
                                    self.logger.info(f"铺位选择成功(表格内): {ticket_passenger.passenger.name} -> 上铺")
                                    return True
                                except Exception as select_e:
                                    self.logger.warning(f"上铺选择失败: {select_e}")
                            else:
                                # 默认选择"不限"
                                if any("不限" in opt for opt in opt_texts):
                                    try:
                                        Select(sel).select_by_visible_text("不限")
                                        self.logger.info(f"铺位选择默认(表格内): {ticket_passenger.passenger.name} -> 不限")
                                        return True
                                    except Exception as select_e:
                                        self.logger.warning(f"默认铺位选择失败: {select_e}")
            except Exception as e:
                self.logger.debug(f"表格内铺位下拉框选择失败: {e}")
            
            # 方案2：全局查找铺位选择下拉框
            try:
                bunk_selects = self.driver.find_elements(By.XPATH, "//select[starts-with(@id,'ticketype_')]")
                
                for sel in bunk_selects:
                    opts = sel.find_elements(By.TAG_NAME, "option")
                    opt_texts = [o.text.strip() for o in opts]
                    
                    if any("铺" in opt for opt in opt_texts):
                        if pos == "下铺" and any("下铺" in opt for opt in opt_texts):
                            try:
                                Select(sel).select_by_visible_text("下铺")
                                self.logger.info(f"铺位选择成功(全局): {ticket_passenger.passenger.name} -> 下铺")
                                return True
                            except Exception as select_e:
                                self.logger.warning(f"全局下铺选择失败: {select_e}")
                        elif pos == "中铺" and any("中铺" in opt for opt in opt_texts):
                            try:
                                Select(sel).select_by_visible_text("中铺")
                                self.logger.info(f"铺位选择成功(全局): {ticket_passenger.passenger.name} -> 中铺")
                                return True
                            except Exception as select_e:
                                self.logger.warning(f"全局中铺选择失败: {select_e}")
                        elif pos == "上铺" and any("上铺" in opt for opt in opt_texts):
                            try:
                                Select(sel).select_by_visible_text("上铺")
                                self.logger.info(f"铺位选择成功(全局): {ticket_passenger.passenger.name} -> 上铺")
                                return True
                            except Exception as select_e:
                                self.logger.warning(f"全局上铺选择失败: {select_e}")
                        else:
                            if any("不限" in opt for opt in opt_texts):
                                try:
                                    Select(sel).select_by_visible_text("不限")
                                    self.logger.info(f"铺位选择默认(全局): {ticket_passenger.passenger.name} -> 不限")
                                    return True
                                except Exception as select_e:
                                    self.logger.warning(f"全局默认铺位选择失败: {select_e}")
            except Exception as e:
                self.logger.debug(f"全局铺位下拉框选择失败: {e}")
            
            # 备选方案：查找"选座喽"或"选铺喽"小部件
            try:
                widget = self.driver.find_element(By.XPATH, "//*[contains(normalize-space(),'选座喽') or contains(normalize-space(),'选铺喽')]")
                self._scroll_into_view(widget)
                
                candidates = []
                if pos in ("A", "B", "C", "D", "F"):
                    candidates = [pos]
                elif pos in ("靠窗", "窗"):
                    candidates = ["A", "F"]
                elif pos in ("过道", "走道"):
                    candidates = ["C", "D"]
                elif pos in ("下铺", "中铺", "上铺"):
                    candidates = [pos]
                
                for t in candidates:
                    try:
                        btn = widget.find_element(By.XPATH, f".//*[normalize-space(text())='{t}']")
                        self._safe_click(btn)
                        time.sleep(0.1)
                        self.logger.info(f"位置选择成功(弹窗): {p.name} -> {t}")
                        return True
                    except NoSuchElementException:
                        continue
            except Exception as e:
                self.logger.debug(f"弹窗位置选择失败: {e}")
            
            # 最后尝试：在全局范围内查找铺位选项
            try:
                bunk_options = {
                    "下铺": ["下铺", "下"],
                    "中铺": ["中铺", "中"], 
                    "上铺": ["上铺", "上"],
                    "靠窗": ["A", "F", "窗", "靠窗"],
                    "过道": ["C", "D", "过道", "走道"]
                }
                
                if pos in bunk_options:
                    for option in bunk_options[pos]:
                        try:
                            elements = self.driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{option}']")
                            for el in elements:
                                if el.is_displayed() and el.is_enabled():
                                    self._safe_click(el)
                                    time.sleep(0.1)
                                    self.logger.info(f"铺位选择成功(全局): {ticket_passenger.passenger.name} -> {option}")
                                    return True
                        except Exception:
                            continue
            except Exception as e:
                self.logger.debug(f"全局铺位选择失败: {e}")
            
            self.logger.warning(f"铺位选择失败: {ticket_passenger.passenger.name} -> {pos}")
            return False
            
        except Exception as e:
            self.logger.error(f"铺位选择异常: {e}")
            return False

    def take_screenshot(self, filename: str) -> bool:
        try:
            if self.driver:
                self.driver.save_screenshot(filename)
                self.logger.info(f"截图保存到: {filename}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"截图失败: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "error_message": self.error_message,
            "is_running": self.status in [
                BookingStatus.SEARCHING,
                BookingStatus.SELECTING_TRAIN,
                BookingStatus.SELECTING_SEATS,
                BookingStatus.SUBMITTING_ORDER,
                BookingStatus.CONFIRMING_PAYMENT,
            ]
        }

    def cancel_booking(self) -> None:
        self.status = BookingStatus.CANCELLED
        self.logger.info("预订已取消")

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器失败: {e}")
            finally:
                self.driver = None