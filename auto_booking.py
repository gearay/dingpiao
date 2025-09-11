import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

from models import Passenger, TrainInfo, TicketInfo, SeatType, BunkType
from ticket_manager import TicketManager
from enum import Enum


class BookingStatus(Enum):
    """购票状态枚举"""
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
    """自动购票模块 - 打开浏览器等待人工登录，然后自动化购票流程"""
    
    def __init__(self, ticket_manager: TicketManager, headless: bool = False):
        self.ticket_manager = ticket_manager
        self.headless = headless
        self.driver = None
        self.status = BookingStatus.PENDING
        self.error_message = ""
        self.logger = self._setup_logger()
        
        # 12306相关URL
        self.base_url = "https://www.12306.cn"
        self.ticket_url = "https://kyfw.12306.cn/otn/leftTicket/init"
        
        # 配置等待时间
        self.wait_timeout = 30
        self.poll_interval = 1
        
        # 登录状态检查
        self.login_check_interval = 2
        self.max_login_wait_time = 300  # 5分钟登录时间
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("AutoBooking")
        logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler("booking.log", encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def init_driver(self) -> bool:
        """初始化浏览器驱动"""
        try:
            # 检查Chrome是否安装
            import subprocess
            try:
                result = subprocess.run(['google-chrome', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    raise Exception("Chrome browser not found")
                self.logger.info(f"Chrome版本: {result.stdout.strip()}")
            except Exception as e:
                self.logger.error("Chrome browser is not installed. Please install Chrome browser first.")
                self.error_message = "Chrome浏览器未安装，请先安装Chrome浏览器"
                return False
            
            self.options = Options()
            if self.headless:
                self.options.add_argument("--headless")
            
            # 避免被检测为自动化工具
            self.options.add_experimental_option('excludeSwitches', ['enable-automation'])
            self.options.add_argument('--disable-blink-features=AutomationControlled')
            self.options.add_argument('--disable-infobars')
            
            # WSL环境下需要的参数
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-setuid-sandbox')
            
            # 使用与您参考代码相同的方式初始化
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.maximize_window()
            
            self.driver.set_page_load_timeout(30)
            self.logger.info("浏览器驱动初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化浏览器驱动失败: {e}")
            self.error_message = str(e)
            return False
    
    def open_browser_and_wait_for_login(self, from_station: str, to_station: str, 
                                      departure_date: str) -> bool:
        """打开浏览器并等待人工登录"""
        try:
            self.status = BookingStatus.WAITING_FOR_LOGIN
            self.logger.info("打开浏览器，等待人工登录...")
            
            if not self.driver:
                if not self.init_driver():
                    return False
            
            # 访问12306网站
            self.driver.get(self.base_url)
            time.sleep(2)
            
            # 访问购票页面
            self.driver.get(self.ticket_url)
            time.sleep(2)
            
            # 填充查询信息
            self._fill_search_form(from_station, to_station, departure_date)
            
            print("=" * 50)
            print("请在浏览器中完成登录操作")
            print("登录完成后，程序将自动进行后续购票步骤")
            print("=" * 50)
            
            # 等待用户登录
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
    
    def _fill_search_form(self, from_station: str, to_station: str, departure_date: str) -> None:
        """填充搜索表单"""
        try:
            # 等待页面加载
            time.sleep(2)
            
            # 定位出发地输入框，并输入站点名
            from_input = self.driver.find_element(By.XPATH, '//input[@id="fromStationText"]')
            from_input.click()
            time.sleep(0.5)
            from_input.send_keys(from_station)
            time.sleep(0.5)
            
            # 点击确定按钮（如果有）
            try:
                confirm_btn = self.driver.find_element(By.XPATH, '//span[@class="ralign"]')
                confirm_btn.click()
            except:
                pass
            time.sleep(0.5)
            
            # 定位目的地输入框，并输入站点名
            to_input = self.driver.find_element(By.XPATH, '//input[@id="toStationText"]')
            to_input.click()
            time.sleep(0.5)
            to_input.send_keys(to_station)
            time.sleep(0.5)
            
            # 点击确定按钮（如果有）
            try:
                confirm_btn = self.driver.find_element(By.XPATH, '//span[@class="ralign"]')
                confirm_btn.click()
            except:
                pass
            time.sleep(0.5)
            
            # 定位日期输入框，并输入对应的日期
            date_input = self.driver.find_element(By.XPATH, '//input[@id="train_date"]')
            date_input.clear()
            date_input.send_keys(departure_date)
            time.sleep(0.5)
            
            self.logger.info("搜索表单填充完成")
            
        except Exception as e:
            self.logger.error(f"填充搜索表单失败: {e}")
            raise
    
    def _wait_for_login(self) -> bool:
        """等待用户登录"""
        start_time = time.time()
        
        while time.time() - start_time < self.max_login_wait_time:
            try:
                # 检查是否存在登录后的元素
                # 1. 检查是否有欢迎信息
                try:
                    welcome_element = self.driver.find_element(By.CLASS_NAME, "welcome-name")
                    if welcome_element.is_displayed():
                        return True
                except:
                    pass
                
                # 2. 检查是否有用户名显示
                try:
                    username_element = self.driver.find_element(By.XPATH, '//a[contains(@class, "username")]')
                    if username_element.is_displayed():
                        return True
                except:
                    pass
                
                # 3. 检查是否有退出登录按钮
                try:
                    logout_element = self.driver.find_element(By.XPATH, '//a[text()="退出"]')
                    if logout_element.is_displayed():
                        return True
                except:
                    pass
                
                # 4. 检查是否还在登录页面
                try:
                    login_page = self.driver.find_element(By.ID, "J-login")
                    if login_page.is_displayed():
                        print(f"等待登录中... (已等待 {int(time.time() - start_time)} 秒)")
                        time.sleep(self.login_check_interval)
                except:
                    # 如果找不到登录页面元素，可能已经登录
                    return True
                
            except Exception as e:
                self.logger.debug(f"登录检查异常: {e}")
                time.sleep(self.login_check_interval)
        
        return False
    
    def search_tickets(self, max_retries: int = 3) -> bool:
        """搜索车票"""
        try:
            self.status = BookingStatus.SEARCHING
            self.logger.info("开始搜索车票...")
            
            for attempt in range(max_retries):
                try:
                    # 点击查询按钮
                    query_button = self.driver.find_element(By.XPATH, '//a[@id="query_ticket"]')
                    query_button.click()
                    time.sleep(0.5)
                    
                    # 等待查询结果
                    time.sleep(2)
                    
                    # 检查是否有结果
                    try:
                        result_rows = self.driver.find_elements(By.XPATH, "//tbody[@id='queryLeftTable']/tr")
                        if result_rows:
                            self.logger.info("车票搜索成功")
                            return True
                        else:
                            self.logger.warning("未找到车票信息")
                            return False
                    except:
                        self.logger.warning("查询结果页面加载异常")
                        return False
                    
                except Exception as e:
                    self.logger.warning(f"第 {attempt + 1} 次搜索失败: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2)
            
            return False
            
        except Exception as e:
            self.logger.error(f"搜索车票失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def select_train(self, train_number: str) -> bool:
        """选择特定车次"""
        try:
            self.status = BookingStatus.SELECTING_TRAIN
            self.logger.info(f"选择车次: {train_number}")
            
            # 等待车次列表加载
            time.sleep(2)
            
            # 查找目标车次 - 基于实际12306页面结构
            train_rows = self.driver.find_elements(By.XPATH, "//tbody[@id='queryLeftTable']/tr")
            self.logger.info(f"找到 {len(train_rows)} 个车次行")
            
            for row in train_rows:
                try:
                    # 跳过没有车次信息的行
                    if 'btm' in row.get_attribute('class') or row.get_attribute('style'):
                        continue
                    
                    # 方法1: 通过车次名称精确匹配
                    try:
                        # 尝试多种XPath定位器找到车次名称
                        train_name_element = None
                        train_text = ""
                        
                        # 策略1: 尝试直接从td[1]获取
                        try:
                            td1 = row.find_element(By.XPATH, "./td[1]")
                            train_text = td1.text.strip()
                            self.logger.info(f"策略1 - td1文本: '{train_text}'")
                            if train_number.strip() in train_text:
                                train_name_element = td1
                        except Exception as e:
                            self.logger.debug(f"策略1失败: {e}")
                        
                        # 策略2: 尝试从td[1]内的链接获取
                        if not train_name_element:
                            try:
                                train_name_element = row.find_element(By.XPATH, "./td[1]//a")
                                train_text = train_name_element.text.strip()
                                self.logger.info(f"策略2 - td1//a文本: '{train_text}'")
                            except Exception as e:
                                self.logger.debug(f"策略2失败: {e}")
                        
                        # 策略3: 尝试从第一个td获取
                        if not train_text:
                            try:
                                first_td = row.find_element(By.XPATH, "./td[1]")
                                train_text = first_td.text.strip()
                                self.logger.info(f"策略3 - 第一个td文本: '{train_text}'")
                            except Exception as e:
                                self.logger.debug(f"策略3失败: {e}")
                        
                        if not train_text:
                            self.logger.debug("未找到车次文本")
                            continue
                            
                        self.logger.info(f"检查车次: 目标='{train_number}', 实际='{train_text}'")
                        if train_number.strip() in train_text:
                            self.logger.info(f"找到目标车次 {train_number} (实际显示: {train_text})，尝试点击预订按钮...")
                            
                            # 详细调试该行的HTML结构
                            try:
                                row_html = row.get_attribute('outerHTML')
                                self.logger.debug(f"车次 {train_number} 所在行的HTML结构: {row_html[:200]}...")
                            except:
                                pass
                            
                            # 策略1: 查找所有可能的预订按钮
                            try:
                                book_buttons = row.find_elements(By.XPATH, ".//a[contains(text(), '预订')]")
                                self.logger.info(f"在车次 {train_number} 行找到 {len(book_buttons)} 个预订按钮")
                                
                                for i, button in enumerate(book_buttons):
                                    try:
                                        if button.is_displayed() and button.is_enabled():
                                            button.click()
                                            self.logger.info(f"车次 {train_number} 选择成功 (策略1-按钮{i+1})")
                                            return True
                                    except Exception as e:
                                        self.logger.debug(f"按钮{i+1}点击失败: {e}")
                                        continue
                            except Exception as e:
                                self.logger.debug(f"策略1失败: {e}")
                            
                            # 策略2: 查找第13个td中的链接
                            try:
                                td13 = row.find_element(By.XPATH, "./td[13]")
                                links = td13.find_elements(By.TAG_NAME, "a")
                                self.logger.info(f"在td[13]找到 {len(links)} 个链接")
                                
                                for i, link in enumerate(links):
                                    try:
                                        if link.is_displayed() and link.is_enabled():
                                            link_text = link.text
                                            self.logger.info(f"点击链接: '{link_text}'")
                                            link.click()
                                            self.logger.info(f"车次 {train_number} 选择成功 (策略2-链接{i+1})")
                                            return True
                                    except Exception as e:
                                        self.logger.debug(f"链接{i+1}点击失败: {e}")
                                        continue
                            except Exception as e:
                                self.logger.debug(f"策略2失败: {e}")
                            
                            # 策略3: 查找所有可点击的链接元素
                            try:
                                all_links = row.find_elements(By.TAG_NAME, "a")
                                self.logger.info(f"在车次行找到 {len(all_links)} 个链接")
                                
                                for i, link in enumerate(all_links):
                                    try:
                                        if link.is_displayed() and link.is_enabled():
                                            link_text = link.text.strip()
                                            if link_text in ['预订', '']:
                                                link.click()
                                                self.logger.info(f"车次 {train_number} 选择成功 (策略3-链接{i+1})")
                                                return True
                                    except Exception as e:
                                        self.logger.debug(f"链接{i+1}点击失败: {e}")
                                        continue
                            except Exception as e:
                                self.logger.debug(f"策略3失败: {e}")
                            
                            # 策略4: 使用JavaScript点击
                            try:
                                book_buttons = row.find_elements(By.XPATH, ".//a[contains(text(), '预订')]")
                                for i, button in enumerate(book_buttons):
                                    try:
                                        self.driver.execute_script("arguments[0].click();", button)
                                        self.logger.info(f"车次 {train_number} 选择成功 (策略4-JS点击{i+1})")
                                        return True
                                    except Exception as e:
                                        self.logger.debug(f"JS点击{i+1}失败: {e}")
                                        continue
                            except Exception as e:
                                self.logger.debug(f"策略4失败: {e}")
                    except Exception as e:
                        self.logger.debug(f"方法1失败: {e}")
                        continue
                    
                    # 方法5: 通过行文本内容模糊匹配
                    try:
                        row_text = row.text
                        self.logger.info(f"检查行文本匹配: 目标='{train_number}', 行文本='{row_text[:100]}...'")
                        if train_number in row_text:
                            self.logger.info(f"通过文本内容找到车次 {train_number}，尝试各种点击方式...")
                            
                            # 复用上面的点击策略
                            click_strategies = [
                                lambda: self._click_book_buttons(row, train_number),
                                lambda: self._click_td13_links(row, train_number),
                                lambda: self._click_any_link(row, train_number),
                                lambda: self._js_click_book_buttons(row, train_number)
                            ]
                            
                            for i, strategy in enumerate(click_strategies):
                                try:
                                    if strategy():
                                        self.logger.info(f"车次 {train_number} 选择成功 (方法5-策略{i+1})")
                                        return True
                                except Exception as e:
                                    self.logger.debug(f"方法5-策略{i+1}失败: {e}")
                                    continue
                    except Exception as e:
                        self.logger.debug(f"方法5失败: {e}")
                        continue
                        
                except Exception as e:
                    self.logger.debug(f"处理车次行失败: {e}")
                    continue
            
            # 如果还是没找到，打印当前页面的车次信息用于调试
            try:
                self.logger.info("当前页面的车次信息:")
                all_trains = self.driver.find_elements(By.XPATH, "//tbody[@id='queryLeftTable']/tr")
                for i, train in enumerate(all_trains[:5]):  # 只打印前5个车次
                    try:
                        train_info = train.text
                        self.logger.info(f"车次 {i+1}: {train_info[:100]}...")
                        
                        # 打印该行的预订按钮信息
                        try:
                            book_buttons = train.find_elements(By.XPATH, ".//a[contains(text(), '预订')]")
                            self.logger.info(f"  - 预订按钮数量: {len(book_buttons)}")
                            for j, btn in enumerate(book_buttons):
                                self.logger.info(f"    按钮{j+1}: 显示={btn.is_displayed()}, 可用={btn.is_enabled()}, 文本='{btn.text}'")
                        except:
                            pass
                    except:
                        self.logger.info(f"车次 {i+1}: 无法获取车次信息")
            except:
                pass
            
            raise Exception(f"未找到车次 {train_number} 或该车次不可预订")
            
        except Exception as e:
            self.logger.error(f"选择车次失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def _click_book_buttons(self, row, train_number):
        """点击预订按钮策略"""
        book_buttons = row.find_elements(By.XPATH, ".//a[contains(text(), '预订')]")
        for button in book_buttons:
            if button.is_displayed() and button.is_enabled():
                button.click()
                return True
        return False
    
    def _click_td13_links(self, row, train_number):
        """点击td[13]中的链接策略"""
        td13 = row.find_element(By.XPATH, "./td[13]")
        links = td13.find_elements(By.TAG_NAME, "a")
        for link in links:
            if link.is_displayed() and link.is_enabled():
                link.click()
                return True
        return False
    
    def _click_any_link(self, row, train_number):
        """点击任何链接策略"""
        all_links = row.find_elements(By.TAG_NAME, "a")
        for link in all_links:
            if link.is_displayed() and link.is_enabled():
                link_text = link.text.strip()
                if link_text in ['预订', '']:
                    link.click()
                    return True
        return False
    
    def _js_click_book_buttons(self, row, train_number):
        """使用JavaScript点击预订按钮策略"""
        book_buttons = row.find_elements(By.XPATH, ".//a[contains(text(), '预订')]")
        for button in book_buttons:
            self.driver.execute_script("arguments[0].click();", button)
            return True
        return False
    
    def select_passengers_and_seats(self, passengers: List[Passenger]) -> bool:
        """选择乘客和席次"""
        try:
            self.status = BookingStatus.SELECTING_SEATS
            self.logger.info("选择乘客和席次...")
            
            # 等待页面加载完成
            time.sleep(2)
            
            # 尝试切换到可能包含乘客信息的frame
            frame_switched = False
            try:
                # 策略1: 查找所有iframe并尝试切换
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                self.logger.info(f"找到 {len(iframes)} 个iframe")
                
                for i, iframe in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(iframe)
                        self.logger.info(f"切换到iframe {i+1}")
                        
                        # 检查frame中是否有乘客相关内容
                        try:
                            passenger_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '乘车人') or contains(text(), 'passenger')]")
                            if passenger_elements:
                                self.logger.info(f"iframe {i+1} 中找到乘客相关元素")
                                frame_switched = True
                                break
                            else:
                                self.logger.debug(f"iframe {i+1} 中未找到乘客相关元素")
                        except:
                            self.logger.debug(f"iframe {i+1} 检查失败")
                        
                        # 如果没有找到，切换回主文档
                        self.driver.switch_to.default_content()
                    except Exception as e:
                        self.logger.debug(f"切换iframe {i+1} 失败: {e}")
                        try:
                            self.driver.switch_to.default_content()
                        except:
                            pass
            except Exception as e:
                self.logger.debug(f"iframe切换过程失败: {e}")
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
            
            # 如果没有成功切换到frame，在主文档中查找
            if not frame_switched:
                self.logger.info("在主文档中查找乘客信息")
                self.driver.switch_to.default_content()
            
            # 使用搜索框策略选择乘客
            return self._select_passengers_by_search(passengers)
            
        except Exception as e:
            self.logger.error(f"选择乘客和席次失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def _select_passengers_by_search(self, passengers: List[Passenger]) -> bool:
        """使用搜索框选择乘客"""
        try:
            self.logger.info("开始使用搜索框选择乘客...")
            self.logger.info(f"需要选择的乘客列表: {[p.name for p in passengers]}")
            
            # 等待搜索框加载
            search_box = None
            search_button = None
            try:
                search_box = WebDriverWait(self.driver, self.wait_timeout).until(
                    EC.presence_of_element_located((By.ID, "quickQueryPassenger_id"))
                )
                self.logger.info("✓ 找到乘客搜索框 (ID: quickQueryPassenger_id)")
                
                # 查找搜索按钮
                search_button = self.driver.find_element(By.ID, "submit_quickQueryPassenger")
                self.logger.info("✓ 找到搜索按钮 (ID: submit_quickQueryPassenger)")
                
                # 调试搜索框属性
                try:
                    self.logger.debug(f"搜索框属性: tag={search_box.tag_name}, type={search_box.get_attribute('type')}, value='{search_box.get_attribute('value')}'")
                except:
                    pass
                    
            except Exception as e:
                self.logger.warning(f"✗ 未找到乘客搜索框: {e}")
                self.logger.info("回退到备用选择方法...")
                # 回退到原来的选择方法
                return self._select_passengers_fallback(passengers)
            
            # 清空搜索框
            try:
                search_box.clear()
                self.logger.info("✓ 清空搜索框")
            except Exception as e:
                self.logger.debug(f"清空搜索框失败: {e}")
            
            # 记录页面上的所有复选框状态
            try:
                all_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                self.logger.debug(f"搜索前页面上有 {len(all_checkboxes)} 个复选框")
                for i, cb in enumerate(all_checkboxes[:5]):  # 只显示前5个
                    try:
                        self.logger.debug(f"  复选框{i+1}: 显示={cb.is_displayed()}, 选中={cb.is_selected()}, title={cb.get_attribute('title')}")
                    except:
                        pass
            except:
                pass
            
            for passenger in passengers:
                try:
                    self.logger.info(f"🔍 开始搜索乘客: {passenger.name}")
                    
                    # 先清空搜索框显示所有乘客
                    search_box.clear()
                    self.logger.debug("✓ 清空搜索框，准备显示所有乘客")
                    
                    # 等待所有乘客加载
                    time.sleep(0.5)
                    
                    # 尝试通过拼音搜索（如果适用）
                    if len(passenger.name) >= 2:
                        # 尝试拼音首字母搜索（如"鞠放" -> "jf"）
                        pinyin_search = passenger.name[0] + passenger.name[1]
                        self.logger.info(f"尝试拼音首字母搜索: '{pinyin_search}'")
                        
                        search_box.send_keys(pinyin_search)
                        # 点击搜索按钮
                        if search_button:
                            search_button.click()
                            self.logger.info("✓ 点击搜索按钮")
                        time.sleep(1)
                        
                        # 检查是否能找到乘客
                        if self._try_select_passenger_by_search(passenger, pinyin_search):
                            self.logger.info(f"✅ 通过拼音搜索成功选中乘客 {passenger.name}")
                            passenger_selected = True
                        else:
                            self.logger.info(f"拼音搜索未找到 {passenger.name}，尝试其他方式")
                    
                    # 如果拼音搜索失败，尝试直接搜索
                    if not passenger_selected:
                        search_box.clear()
                        search_box.send_keys(passenger.name)
                        self.logger.info(f"✓ 在搜索框中输入完整姓名: '{passenger.name}'")
                        
                        # 点击搜索按钮
                        if search_button:
                            search_button.click()
                            self.logger.info("✓ 点击搜索按钮")
                        
                        # 等待搜索结果
                        self.logger.debug("等待搜索结果加载...")
                        time.sleep(1)
                    
                    # 记录搜索后的复选框状态
                    try:
                        search_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                        self.logger.debug(f"搜索后页面上有 {len(search_checkboxes)} 个复选框")
                        for i, cb in enumerate(search_checkboxes[:5]):  # 只显示前5个
                            try:
                                self.logger.debug(f"  搜索后复选框{i+1}: 显示={cb.is_displayed()}, 选中={cb.is_selected()}, title={cb.get_attribute('title')}")
                            except:
                                pass
                    except:
                        pass
                    
                    # 尝试多种方式选择搜索到的乘客
                    passenger_selected = False
                    
                    # 尝试选择乘客
                    if self._try_select_passenger_by_search(passenger, passenger.name):
                        self.logger.info(f"✅ 通过搜索成功选中乘客 {passenger.name}")
                        passenger_selected = True
                    else:
                        self.logger.info(f"搜索未找到 {passenger.name}，尝试在完整列表中查找")
                        
                        # 清空搜索框显示所有乘客
                        search_box.clear()
                        if search_button:
                            search_button.click()
                        time.sleep(1)
                        
                        # 在完整列表中查找
                        if self._try_select_passenger_in_full_list(passenger):
                            self.logger.info(f"✅ 在完整列表中成功选中乘客 {passenger.name}")
                            passenger_selected = True
                    
                    passenger_selected = False  # 这个变量已在上面定义
                    
                    if not passenger_selected:
                        self.logger.warning(f"❌ 无法通过搜索选中乘客 {passenger.name}")
                        # 记录当前页面状态用于调试
                        try:
                            page_source = self.driver.page_source
                            if passenger.name in page_source:
                                self.logger.info(f"  页面中包含乘客姓名 '{passenger.name}'，但可能结构不匹配")
                            else:
                                self.logger.warning(f"  页面中未找到乘客姓名 '{passenger.name}'")
                        except:
                            pass
                    else:
                        self.logger.info(f"✅ 乘客 {passenger.name} 选择成功")
                    
                    # 清空搜索框为下一个乘客做准备
                    try:
                        search_box.clear()
                        self.logger.debug(f"✅ 清空搜索框为下一个乘客做准备")
                    except Exception as e:
                        self.logger.debug(f"清空搜索框失败: {e}")
                        
                except Exception as e:
                    self.logger.error(f"❌ 选择乘客 {passenger.name} 失败: {e}")
                    # 记录异常时的页面状态
                    try:
                        self.logger.debug("失败时的页面状态:")
                        all_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                        self.logger.debug(f"  当前页面上有 {len(all_checkboxes)} 个复选框")
                    except:
                        pass
                    continue
            
            self.logger.info("🎉 乘客搜索选择完成")
            return True
            
        except Exception as e:
            self.logger.error(f"搜索选择乘客失败: {e}")
            return self._select_passengers_fallback(passengers)
    
    def _try_select_passenger_by_search(self, passenger: Passenger, search_term: str) -> bool:
        """在搜索结果中尝试选择乘客"""
        try:
            self.logger.debug(f"尝试在搜索结果中选择乘客: {passenger.name}, 搜索词: {search_term}")
            
            # 策略1: 通过title属性匹配乘客
            checkbox_patterns = [
                f"//input[@title='设置为乘车人，按空格键进行操作' and contains(@*, '{passenger.name}')]",
                f"//input[@title='乘车人' and contains(@*, '{passenger.name}')]",
                f"//input[@type='checkbox' and contains(@*, '{passenger.name}')]"
            ]
            
            for i, pattern in enumerate(checkbox_patterns):
                try:
                    self.logger.debug(f"  模式{i+1}: {pattern}")
                    checkboxes = self.driver.find_elements(By.XPATH, pattern)
                    self.logger.debug(f"  模式{i+1}找到 {len(checkboxes)} 个匹配的复选框")
                    
                    for j, checkbox in enumerate(checkboxes):
                        try:
                            is_displayed = checkbox.is_displayed()
                            is_selected = checkbox.is_selected()
                            title = checkbox.get_attribute('title')
                            self.logger.debug(f"    复选框{j+1}: 显示={is_displayed}, 选中={is_selected}, title='{title}'")
                            
                            if is_displayed and not is_selected:
                                checkbox.click()
                                self.logger.info(f"✅ 通过复选框选中乘客 {passenger.name} (模式{i+1}-复选框{j+1})")
                                return True
                            elif is_displayed and is_selected:
                                self.logger.info(f"✅ 乘客 {passenger.name} 已被选中 (模式{i+1}-复选框{j+1})")
                                return True
                        except Exception as e:
                            self.logger.debug(f"    点击复选框{j+1}失败: {e}")
                            continue
                    
                except Exception as e:
                    self.logger.debug(f"  模式{i+1}搜索失败: {e}")
            
            # 策略2: 在搜索结果中查找包含乘客姓名的行
            passenger_rows = self.driver.find_elements(By.XPATH, 
                "//tbody[@id='normal_passenger_id']/tr | //tbody[@id='dj_passenger_id']/tr | //table//tr[.//input[@type='checkbox']]")
            
            for i, row in enumerate(passenger_rows):
                try:
                    row_text = row.text
                    if passenger.name in row_text:
                        self.logger.debug(f"  在行{i+1}中找到乘客 {passenger.name}: '{row_text[:50]}...'")
                        
                        # 尝试点击该行的复选框
                        checkbox = row.find_element(By.XPATH, ".//input[@type='checkbox']")
                        if checkbox.is_displayed() and not checkbox.is_selected():
                            checkbox.click()
                            self.logger.info(f"✅ 通过行匹配选中乘客 {passenger.name} (行{i+1})")
                            return True
                        elif checkbox.is_displayed() and checkbox.is_selected():
                            self.logger.info(f"✅ 乘客 {passenger.name} 已被选中 (行{i+1})")
                            return True
                except Exception as e:
                    self.logger.debug(f"    处理行{i+1}失败: {e}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"搜索选择乘客失败: {e}")
            return False
    
    def _try_select_passenger_in_full_list(self, passenger: Passenger) -> bool:
        """在完整乘客列表中选择乘客"""
        try:
            self.logger.debug(f"尝试在完整乘客列表中选择: {passenger.name}")
            
            # 查找所有显示的乘客列表
            try:
                # 查找乘车人列表
                normal_passengers = self.driver.find_elements(By.XPATH, "//ul[@id='normal_passenger_id']//li")
                dj_passengers = self.driver.find_elements(By.XPATH, "//ul[@id='dj_passenger_id']//li")
                
                self.logger.debug(f"找到 {len(normal_passengers)} 个乘车人，{len(dj_passengers)} 个受让人")
                
                # 检查乘车人列表
                for i, li in enumerate(normal_passengers):
                    try:
                        if passenger.name in li.text:
                            self.logger.debug(f"  在乘车人列表{i+1}中找到: '{li.text[:50]}...'")
                            
                            # 查找该li元素中的复选框
                            checkbox = li.find_element(By.XPATH, ".//input[@type='checkbox']")
                            if checkbox.is_displayed() and not checkbox.is_selected():
                                checkbox.click()
                                self.logger.info(f"✅ 在乘车人列表中选中 {passenger.name} (列表项{i+1})")
                                return True
                            elif checkbox.is_displayed() and checkbox.is_selected():
                                self.logger.info(f"✅ 乘客 {passenger.name} 已被选中 (乘车人列表项{i+1})")
                                return True
                    except Exception as e:
                        self.logger.debug(f"    处理乘车人列表项{i+1}失败: {e}")
                        continue
                
                # 检查受让人列表
                for i, li in enumerate(dj_passengers):
                    try:
                        if passenger.name in li.text:
                            self.logger.debug(f"  在受让人列表{i+1}中找到: '{li.text[:50]}...'")
                            
                            # 查找该li元素中的复选框
                            checkbox = li.find_element(By.XPATH, ".//input[@type='checkbox']")
                            if checkbox.is_displayed() and not checkbox.is_selected():
                                checkbox.click()
                                self.logger.info(f"✅ 在受让人列表中选中 {passenger.name} (列表项{i+1})")
                                return True
                            elif checkbox.is_displayed() and checkbox.is_selected():
                                self.logger.info(f"✅ 乘客 {passenger.name} 已被选中 (受让人列表项{i+1})")
                                return True
                    except Exception as e:
                        self.logger.debug(f"    处理受让人列表项{i+1}失败: {e}")
                        continue
                        
            except Exception as e:
                self.logger.debug(f"查找乘客列表失败: {e}")
            
            # 策略3: 通过JavaScript在完整列表中查找
            js_script = f"""
                var allLis = document.querySelectorAll('#normal_passenger_id li, #dj_passenger_id li');
                for (var i = 0; i < allLis.length; i++) {{
                    var li = allLis[i];
                    if (li.textContent && li.textContent.includes('{passenger.name}')) {{
                        console.log('在列表项中找到乘客:', i, li.textContent.substring(0, 50));
                        var checkbox = li.querySelector('input[type="checkbox"]');
                        if (checkbox && !checkbox.checked) {{
                            checkbox.click();
                            console.log('已点击复选框');
                        }}
                        return true;
                    }}
                }}
                console.log('在完整列表中未找到乘客');
                return false;
            """
            
            result = self.driver.execute_script(js_script)
            if result:
                self.logger.info(f"✅ 通过JavaScript在完整列表中选中乘客 {passenger.name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"在完整列表中选择乘客失败: {e}")
            return False
    
    def _select_passengers_fallback(self, passengers: List[Passenger]) -> bool:
        """备用乘客选择方法"""
        try:
            self.logger.info("使用备用方法选择乘客...")
            
            # 尝试多种方式定位乘客区域
            passenger_found = False
            location_strategies = [
                # 策略1: 通过ID
                lambda: self.driver.find_element(By.ID, "normal_passenger_id"),
                # 策略2: 通过包含"乘车人"文本的元素
                lambda: self.driver.find_element(By.XPATH, "//*[contains(text(), '乘车人')]"),
                # 策略3: 通过title属性
                lambda: self.driver.find_element(By.XPATH, '//input[@title="乘车人"]'),
                # 策略4: 通过复选框
                lambda: self.driver.find_element(By.XPATH, '//input[@type="checkbox"]'),
            ]
            
            passenger_container = None
            for i, strategy in enumerate(location_strategies):
                try:
                    passenger_container = strategy()
                    self.logger.info(f"备用策略{i+1}成功找到乘客容器")
                    passenger_found = True
                    break
                except Exception as e:
                    self.logger.debug(f"备用策略{i+1}失败: {e}")
            
            if not passenger_found:
                self.logger.error("备用方法也未找到乘客选择区域")
                return False
            
            # 查找乘客行并选择
            passenger_rows = []
            try:
                passenger_rows = self.driver.find_elements(By.XPATH, "//tbody[@id='normal_passenger_id']/tr")
                self.logger.info(f"通过normal_passenger_id找到 {len(passenger_rows)} 个乘客行")
            except:
                self.logger.debug("normal_passenger_id定位失败")
            
            if not passenger_rows:
                try:
                    passenger_rows = self.driver.find_elements(By.XPATH, "//table//tr[.//input[@type='checkbox']]")
                    self.logger.info(f"通过复选框找到 {len(passenger_rows)} 个乘客行")
                except:
                    pass
            
            for passenger in passengers:
                passenger_found = False
                for row in passenger_rows:
                    try:
                        row_text = row.text
                        if passenger.name in row_text:
                            # 尝试选择乘客
                            checkbox = row.find_element(By.XPATH, ".//input[@type='checkbox']")
                            if not checkbox.is_selected():
                                checkbox.click()
                                self.logger.info(f"备用方法选中乘客 {passenger.name}")
                            passenger_found = True
                            break
                    except:
                        continue
                
                if not passenger_found:
                    self.logger.warning(f"备用方法未找到乘客 {passenger.name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"备用乘客选择失败: {e}")
            return False
    
    def submit_order(self) -> bool:
        """提交订单"""
        try:
            self.status = BookingStatus.SUBMITTING_ORDER
            self.logger.info("提交订单...")
            
            # 点击提交订单按钮
            submit_button = self.driver.find_element(By.XPATH, '//a[text()="提交订单"]')
            submit_button.click()
            time.sleep(0.5)
            
            # 等待订单确认页面
            time.sleep(2)
            
            self.logger.info("订单提交成功")
            return True
            
        except Exception as e:
            self.logger.error(f"提交订单失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def confirm_order(self) -> bool:
        """确认订单"""
        try:
            self.status = BookingStatus.CONFIRMING_PAYMENT
            self.logger.info("确认订单...")
            
            # 确认订单
            confirm_button = self.driver.find_element(By.ID, 'qr_submit_id')
            confirm_button.click()
            time.sleep(3)
            
            self.logger.info("订单确认成功")
            self.status = BookingStatus.SUCCESS
            return True
            
        except Exception as e:
            self.logger.error(f"确认订单失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def auto_book_ticket(self, ticket_info: TicketInfo) -> bool:
        """自动预订车票（主要接口）"""
        try:
            self.logger.info(f"开始自动预订: {ticket_info.train_info.train_number}")
            
            # 1. 打开浏览器并等待登录
            if not self.open_browser_and_wait_for_login(
                ticket_info.train_info.departure_station,
                ticket_info.train_info.arrival_station,
                ticket_info.train_info.date
            ):
                return False
            
            # 2. 搜索车票
            if not self.search_tickets():
                return False
            
            # 3. 选择车次
            if not self.select_train(ticket_info.train_info.train_number):
                return False
            
            # 4. 选择乘客和席次
            if not self.select_passengers_and_seats(ticket_info.passengers):
                return False
            
            # 5. 提交订单
            if not self.submit_order():
                return False
            
            # 6. 确认订单
            if not self.confirm_order():
                return False
            
            self.logger.info("自动预订成功完成")
            return True
            
        except Exception as e:
            self.logger.error(f"自动预订失败: {e}")
            self.error_message = str(e)
            self.status = BookingStatus.FAILED
            return False
    
    def take_screenshot(self, filename: str) -> bool:
        """截图"""
        try:
            if self.driver:
                self.driver.save_screenshot(filename)
                self.logger.info(f"截图保存到: {filename}")
                return True
        except Exception as e:
            self.logger.error(f"截图失败: {e}")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "status": self.status.value,
            "error_message": self.error_message,
            "is_running": self.status in [BookingStatus.SEARCHING, BookingStatus.SELECTING_TRAIN, 
                                         BookingStatus.SELECTING_SEATS, BookingStatus.SUBMITTING_ORDER,
                                         BookingStatus.CONFIRMING_PAYMENT]
        }
    
    def cancel_booking(self) -> None:
        """取消预订"""
        self.status = BookingStatus.CANCELLED
        self.logger.info("预订已取消")
    
    def close(self) -> None:
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器失败: {e}")
            finally:
                self.driver = None