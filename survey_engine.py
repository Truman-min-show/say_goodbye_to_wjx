# survey_engine.py (完整版)

import logging
import random
import re
import threading
import time
from threading import Thread
from typing import List, Dict, Any

import numpy
import requests
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class SurveyRunner:
    """
    问卷星自动化填写的核心引擎。
    这个类封装了所有的配置、浏览器操作和执行逻辑。
    """

    def __init__(self, config: Dict[str, Any], output_callback=None):
        """
        初始化引擎。
        :param config: 一个包含所有配置的字典。
        :param output_callback: 一个用于处理输出信息的回调函数 (用于GUI日志)。
        """
        self.config = config
        self.output_callback = output_callback

        # 从配置中解包参数
        self.url = self.config.get("url", "")
        self.target_num = self.config.get("target_num", 1)
        self.num_threads = self.config.get("num_threads", 1)
        self.use_ip = self.config.get("use_ip", False)
        self.ip_api_url = self.config.get("ip_api_url", "")
        self.fail_threshold = max(5, self.target_num // 2 + 1)

        # 内部状态变量
        self.cur_num = 0
        self.cur_fail = 0
        self.lock = threading.Lock()
        self.stop_flag = False

        # 处理并归一化概率
        self._normalize_probabilities()
        self.log("引擎初始化完成。")

    def log(self, message: str):
        """记录日志，如果设置了回调函数，则通过回调函数输出，否则打印到控制台。"""
        if self.output_callback:
            self.output_callback(message)
        else:
            print(message)

    def _normalize_probabilities(self):
        """将原始的概率字典处理成可直接使用的列表。"""
        prob_configs = {
            "single_prob": self.config.get("single_prob", {}),
            "droplist_prob": self.config.get("droplist_prob", {}),
            "matrix_prob": self.config.get("matrix_prob", {}),
            "scale_prob": self.config.get("scale_prob", {}),
            "texts_prob": self.config.get("texts_prob", {}),
        }

        for name, prob_dict in prob_configs.items():
            normalized_list = []
            for key in sorted(prob_dict.keys()):
                value = prob_dict[key]
                if isinstance(value, list):
                    prob_sum = sum(value)
                    if prob_sum == 0 and len(value) > 0:
                        normalized_list.append([1 / len(value)] * len(value))
                    elif prob_sum > 0:
                        normalized_list.append([x / prob_sum for x in value])
                    else:
                        normalized_list.append([])
                else:
                    normalized_list.append(value)
            setattr(self, name, normalized_list)

        self.multiple_prob = list(self.config.get("multiple_prob", {}).values())
        self.texts = list(self.config.get("texts", {}).values())
        self._normalize_reorder_prob()

    def _normalize_reorder_prob(self):
        """归一化排序题的概率"""
        reorder_prob_dict = self.config.get("reorder_prob", {})
        normalized_reorder_prob = []
        for key_r in sorted(reorder_prob_dict.keys()):
            params_r = reorder_prob_dict[key_r]
            normalized_params_r = {'num_to_select': params_r.get('num_to_select', 0)}

            options_dict = params_r.get('options_weights', {})
            option_keys_sorted = sorted(options_dict.keys())
            options_weights_list = [options_dict.get(k, 0) for k in option_keys_sorted]
            prob_sum_options = sum(options_weights_list)
            if prob_sum_options > 0:
                normalized_params_r['options_weights_norm'] = [x / prob_sum_options for x in options_weights_list]
            else:
                normalized_params_r['options_weights_norm'] = [1 / len(options_weights_list)] * len(
                    options_weights_list) if options_weights_list else []
            normalized_params_r['option_keys_sorted'] = option_keys_sorted

            first_place_dict = params_r.get('first_place_weights', {})
            first_place_weights_list = [first_place_dict.get(k, 0) for k in option_keys_sorted]
            prob_sum_first_place = sum(first_place_weights_list)
            if prob_sum_first_place > 0:
                normalized_params_r['first_place_weights_norm'] = [x / prob_sum_first_place for x in
                                                                   first_place_weights_list]
            else:
                normalized_params_r['first_place_weights_norm'] = [1 / len(first_place_weights_list)] * len(
                    first_place_weights_list) if first_place_weights_list else []

            normalized_reorder_prob.append(normalized_params_r)
        self.reorder_prob = normalized_reorder_prob

    def zanip(self):
        if not self.ip_api_url:
            return "127.0.0.1:0"
        try:
            response = requests.get(self.ip_api_url, timeout=10)
            response.raise_for_status()
            ip = response.text.strip()
            if not self.validate(ip):
                self.log(f"IP代理API返回无效IP: {ip}")
                return "127.0.0.1:0"
            return ip
        except requests.exceptions.RequestException as e:
            self.log(f"获取代理IP失败: {e}")
            return "127.0.0.1:0"

    def validate(self, ip):
        pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):(\d{1,5})$"
        return re.match(pattern, ip) is not None

    def detect(self, driver: WebDriver) -> List[int]:
        q_list: List[int] = []
        page_num = len(driver.find_elements(By.XPATH, '//*[@id="divQuestion"]/fieldset'))
        if page_num == 0:
            questions_on_page = driver.find_elements(By.XPATH,
                                                     '//*[@id="divQuestion"]/div[@class="field ui-field-contain"]')
            valid_count = sum(
                1 for q in questions_on_page if q.get_attribute("topic") and q.get_attribute("topic").isdigit())
            if valid_count > 0:
                q_list.append(valid_count)
            return q_list

        for i in range(1, page_num + 1):
            questions = driver.find_elements(By.XPATH, f'//*[@id="fieldset{i}"]/div')
            valid_count = sum(1 for q in questions if q.get_attribute("topic") and q.get_attribute("topic").isdigit())
            q_list.append(valid_count)
        return q_list

    def vacant(self, driver: WebDriver, current, index):
        if index >= len(self.texts) or index >= len(self.texts_prob):
            self.log(f"填空题 q{current}: 参数索引超出范围，将随机生成内容。")
            driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(f"随机文本{random.randint(1, 100)}")
            return

        content_list, p_list = self.texts[index], self.texts_prob[index]
        if not content_list or len(content_list) != len(p_list):
            self.log(f"填空题 q{current}: 参数配置错误，将随机生成内容。")
            driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(f"随机文本{random.randint(1, 100)}")
            return

        text_index = numpy.random.choice(numpy.arange(len(p_list)), p=p_list)
        driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(content_list[text_index])

    def single(self, driver: WebDriver, current, index):
        options = driver.find_elements(By.XPATH, f'//*[@id="div{current}"]/div[2]/div')
        if not options:
            options = driver.find_elements(By.XPATH,
                                           f'//*[@id="div{current}"]/div[contains(@class, "ui-controlgroup")]/div')

        r = -1
        if index >= len(self.single_prob):
            self.log(f"单选题 q{current}: 参数索引超出范围，将随机选择。")
            r = random.randint(1, len(options))
        else:
            p = self.single_prob[index]
            if p == -1:
                r = random.randint(1, len(options))
            else:
                if len(p) != len(options):
                    self.log(f"第{current}题(单选)参数长度({len(p)})与选项长度({len(options)})不一致！将随机选择。")
                    r = random.randint(1, len(options))
                else:
                    r = numpy.random.choice(numpy.arange(1, len(options) + 1), p=p)
        driver.find_element(By.CSS_SELECTOR, f"#div{current} > div.ui-controlgroup > div:nth-child({r})").click()

    def droplist(self, driver: WebDriver, current, index):
        driver.find_element(By.CSS_SELECTOR, f"#select2-q{current}-container").click()
        time.sleep(0.5)
        options = driver.find_elements(By.XPATH, f"//*[@id='select2-q{current}-results']/li")
        num_valid_options = len(options) - 1

        r_idx = -1
        if index >= len(self.droplist_prob):
            self.log(f"下拉框 q{current}: 参数索引超出范围，将随机选择。")
            r_idx = random.randint(0, num_valid_options - 1) if num_valid_options > 0 else 0
        else:
            p = self.droplist_prob[index]
            if len(p) != num_valid_options:
                self.log(
                    f"第{current}题(下拉框)参数长度({len(p)})与有效选项长度({num_valid_options})不一致！将随机选择。")
                r_idx = random.randint(0, num_valid_options - 1) if num_valid_options > 0 else 0
            else:
                r_idx = numpy.random.choice(numpy.arange(num_valid_options), p=p)

        # +2 因为li是1-indexed且要跳过“请选择”
        driver.find_element(By.XPATH, f"//*[@id='select2-q{current}-results']/li[{r_idx + 2}]").click()

    def multiple(self, driver: WebDriver, current, index):
        options = driver.find_elements(By.XPATH, f'//*[@id="div{current}"]/div[2]/div')
        if not options:
            options = driver.find_elements(By.XPATH,
                                           f'//*[@id="div{current}"]/div[contains(@class, "ui-controlgroup")]/div')

        mul_list = []
        is_random = False
        if index >= len(self.multiple_prob):
            self.log(f"多选题 q{current}: 参数索引超出范围，将随机选择至少一项。")
            is_random = True
        else:
            p = self.multiple_prob[index]
            if len(options) != len(p):
                self.log(f"第{current}题(多选)概率值长度({len(p)})和选项数量({len(options)})不一致！将随机选择至少一项。")
                is_random = True
            else:
                while sum(mul_list) == 0:
                    mul_list = [1 if numpy.random.choice([0, 1], p=[1 - (prob / 100), prob / 100]) else 0 for prob in p]

        if is_random:
            num_to_select = random.randint(1, len(options))
            selected_indices = random.sample(range(len(options)), num_to_select)
            mul_list = [1 if i in selected_indices else 0 for i in range(len(options))]

        for idx, item_selected in enumerate(mul_list):
            if item_selected == 1:
                driver.find_element(By.CSS_SELECTOR,
                                    f"#div{current} > div.ui-controlgroup > div:nth-child({idx + 1})").click()

    def matrix(self, driver: WebDriver, current, current_matrix_sub_q_index):
        rows = driver.find_elements(By.XPATH, f'//*[@id="divRefTab{current}"]/tbody/tr')
        q_num_in_matrix = sum(1 for tr in rows if tr.get_attribute("rowindex"))

        cols = driver.find_elements(By.XPATH, f'//*[@id="drv{current}_1"]/td')
        num_options_per_sub_q = len(cols) - 1

        for i in range(1, q_num_in_matrix + 1):
            opt_idx = -1
            if current_matrix_sub_q_index >= len(self.matrix_prob):
                self.log(f"矩阵题 q{current} 的子题 {i}: 参数索引超出范围，将随机选择。")
                opt_idx = random.randint(0, num_options_per_sub_q - 1)
            else:
                p = self.matrix_prob[current_matrix_sub_q_index]
                if p == -1:
                    opt_idx = random.randint(0, num_options_per_sub_q - 1)
                else:
                    if len(p) != num_options_per_sub_q:
                        self.log(
                            f"矩阵题 q{current} 子题{i} 参数长度({len(p)})与选项数({num_options_per_sub_q})不一致！将随机。")
                        opt_idx = random.randint(0, num_options_per_sub_q - 1)
                    else:
                        opt_idx = numpy.random.choice(numpy.arange(num_options_per_sub_q), p=p)

            # +2 因为选项从第二个td开始
            driver.find_element(By.CSS_SELECTOR, f"#drv{current}_{i} > td:nth-child({opt_idx + 2})").click()
            current_matrix_sub_q_index += 1
        return current_matrix_sub_q_index

    def reorder(self, driver: WebDriver, current, index):
        all_option_elements_xpath = f'//*[@id="div{current}"]/ul/li'
        all_option_elements = driver.find_elements(By.XPATH, all_option_elements_xpath)
        num_all_options = len(all_option_elements)

        if index >= len(self.reorder_prob) or not self.reorder_prob[index] or num_all_options == 0:
            self.log(f"排序题 q{current}: 参数配置缺失或错误，将随机排序所有可选项。")
            for _ in range(num_all_options):
                try:
                    remaining_options = driver.find_elements(By.XPATH,
                                                             f'{all_option_elements_xpath}[not(contains(@class, "active"))]')
                    if not remaining_options: break
                    random.choice(remaining_options).click()
                    time.sleep(0.4)
                except Exception as e:
                    self.log(f"随机排序 q{current} 时出错: {e}")
                    break
            return

        params = self.reorder_prob[index]
        num_to_select = min(params.get('num_to_select', num_all_options), num_all_options)

        weights_norm = params['options_weights_norm'][:num_all_options]
        if sum(weights_norm) == 0:
            weights_norm = [1 / num_all_options] * num_all_options
        else:
            weights_norm = [w / sum(weights_norm) for w in weights_norm]

        selected_indices = numpy.random.choice(numpy.arange(num_all_options), size=num_to_select, replace=False,
                                               p=weights_norm).tolist()
        ordered_click_indices = []

        if selected_indices and 'first_place_weights_norm' in params and params['first_place_weights_norm']:
            current_first_weights = [params['first_place_weights_norm'][i] for i in selected_indices if
                                     i < len(params['first_place_weights_norm'])]
            map_idx = {i: original_idx for i, original_idx in enumerate(selected_indices) if
                       original_idx < len(params['first_place_weights_norm'])}

            if sum(current_first_weights) > 0:
                normalized_current_weights = [w / sum(current_first_weights) for w in current_first_weights]
                chosen_relative_idx = numpy.random.choice(numpy.arange(len(normalized_current_weights)),
                                                          p=normalized_current_weights)
                first_item_original_idx = map_idx[chosen_relative_idx]

                ordered_click_indices.append(first_item_original_idx)
                selected_indices.remove(first_item_original_idx)

        random.shuffle(selected_indices)
        ordered_click_indices.extend(selected_indices)

        for idx_to_click in ordered_click_indices:
            all_option_elements[idx_to_click].click()
            time.sleep(0.4)

    def scale(self, driver: WebDriver, current, index):
        options = driver.find_elements(By.XPATH, f'//*[@id="div{current}"]/div[2]/div/ul/li')
        if not options:
            options = driver.find_elements(By.XPATH,
                                           f'//*[@id="div{current}"]/div[contains(@class, "scale-div")]/div/ul/li')

        r = -1
        if index >= len(self.scale_prob):
            self.log(f"量表题 q{current}: 参数索引超出范围，将随机选择。")
            r = random.randint(1, len(options))
        else:
            p = self.scale_prob[index]
            if p == -1:
                r = random.randint(1, len(options))
            else:
                if len(p) != len(options):
                    self.log(f"第{current}题(量表)参数长度({len(p)})与选项长度({len(options)})不一致！将随机选择。")
                    r = random.randint(1, len(options))
                else:
                    r = numpy.random.choice(numpy.arange(1, len(options) + 1), p=p)

        driver.find_element(By.CSS_SELECTOR, f"#div{current} div.scale-div div ul li:nth-child({r})").click()

    def brush(self, driver: WebDriver):
        q_list = self.detect(driver)
        if not q_list:
            raise Exception("无法检测到问卷题目")

        counters = {"single": 0, "vacant": 0, "droplist": 0, "multiple": 0, "matrix_sub_q": 0, "scale": 0, "reorder": 0}
        current_q_abs_idx = 0

        for page_idx, num_q_on_page in enumerate(q_list):
            for _ in range(1, num_q_on_page + 1):
                current_q_abs_idx += 1
                try:
                    q_type = driver.find_element(By.CSS_SELECTOR, f"#div{current_q_abs_idx}").get_attribute("type")
                except Exception as e:
                    self.log(f"获取第 {current_q_abs_idx} 题类型失败: {e}，跳过。")
                    continue

                if not q_type: continue

                type_map = {
                    ("1", "2"): ("vacant", self.vacant), ("3",): ("single", self.single),
                    ("4",): ("multiple", self.multiple), ("5",): ("scale", self.scale),
                    ("7",): ("droplist", self.droplist), ("11",): ("reorder", self.reorder)
                }

                handled = False
                for types, (counter_name, func) in type_map.items():
                    if q_type in types:
                        func(driver, current_q_abs_idx, counters[counter_name])
                        counters[counter_name] += 1
                        handled = True
                        break

                if handled: continue

                if q_type == "6":
                    counters["matrix_sub_q"] = self.matrix(driver, current_q_abs_idx, counters["matrix_sub_q"])
                elif q_type == "8":
                    try:
                        score_input = driver.find_element(By.CSS_SELECTOR, f"#q{current_q_abs_idx}")
                        min_val = int(score_input.get_attribute("min") or 1)
                        max_val = int(score_input.get_attribute("max") or 100)
                        score = random.randint(min_val, max_val)
                        driver.execute_script(
                            f"arguments[0].value = '{score}'; arguments[0].dispatchEvent(new Event('change'));",
                            score_input)
                    except Exception as e_slider:
                        self.log(f"处理滑块题 {current_q_abs_idx} 失败: {e_slider}")
                else:
                    self.log(f"第 {current_q_abs_idx} 题为不支持的题型 (type: {q_type})，已跳过。")

            time.sleep(0.5)
            if page_idx < len(q_list) - 1:
                try:
                    driver.find_element(By.CSS_SELECTOR, "#divNext").click()
                    time.sleep(1)
                except Exception:
                    self.log("点击下一页失败，尝试寻找提交按钮。")
            else:
                try:
                    driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
                    time.sleep(1)
                except Exception as e:
                    self.log(f"点击最终提交按钮失败: {e}")
        self.submit(driver)

    def submit(self, driver: WebDriver):
        time.sleep(1)
        try:
            driver.find_element(By.XPATH,
                                '//*[@id="layui-layer1"]/div[3]/a[contains(@class, "layui-layer-btn0")]').click()
            time.sleep(1)
        except:
            pass
        try:
            driver.find_element(By.XPATH, '//*[@id="SM_BTN_1"]').click()
            time.sleep(3)
        except:
            pass
        try:
            slider_text = driver.find_element(By.XPATH, '//*[@id="nc_1__scale_text"]/span')
            if "请按住滑块" in slider_text.text:
                slider_button = driver.find_element(By.XPATH, '//*[@id="nc_1_n1z"]')
                width = slider_text.size.get("width", 260)
                ActionChains(driver).drag_and_drop_by_offset(slider_button, width, 0).perform()
                time.sleep(2)
        except:
            pass

    def run_instance(self, thread_id: int, xx: int, yy: int):
        """单个浏览器实例的运行逻辑"""
        while self.cur_num < self.target_num and not self.stop_flag:
            option = webdriver.ChromeOptions()
            option.add_experimental_option("excludeSwitches", ["enable-automation"])
            option.add_experimental_option("useAutomationExtension", False)
            # 可以在此处添加 --headless 等选项用于后台运行
            # option.add_argument("--headless")
            # option.add_argument("--disable-gpu")

            driver = None
            try:
                if self.use_ip:
                    ip_address = self.zanip()
                    if self.validate(ip_address):
                        option.add_argument(f"--proxy-server={ip_address}")

                driver = webdriver.Chrome(options=option)
                driver.set_page_load_timeout(60)
                driver.set_window_size(550, 650)
                driver.set_window_position(x=xx, y=yy)

                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                                       {
                                           "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'})

                driver.get(self.url)
                url1 = driver.current_url
                self.brush(driver)
                time.sleep(4)
                url2 = driver.current_url

                if url1 != url2 or "finish" in url2 or "survey" not in url2.lower():
                    with self.lock:
                        if self.cur_num < self.target_num:
                            self.cur_num += 1
                            self.log(
                                f"线程 {thread_id}: 已填写 {self.cur_num}/{self.target_num} 份 - 失败 {self.cur_fail} 次 - {time.strftime('%H:%M:%S')}")
                else:
                    raise Exception("URL未跳转或跳转至错误页面，可能提交失败")

            except Exception as e:
                # traceback.print_exc() # 调试时可以取消此行注释以查看详细错误
                self.log(f"线程 {thread_id} 发生错误: {e}")
                with self.lock:
                    self.cur_fail += 1
                    self.log(
                        f"\033[91m线程 {thread_id}: 失败1次 (总失败{self.cur_fail})。错误: {str(e)[:100]}...\033[0m")
                    if self.cur_fail >= self.fail_threshold:
                        self.log(f"失败次数 ({self.cur_fail}) 已达阈值 ({self.fail_threshold})，程序将停止。")
                        self.stop_flag = True
            finally:
                if driver:
                    driver.quit()
                if self.stop_flag:
                    break
            time.sleep(random.uniform(1, 3))

    def start(self):
        """启动所有线程开始执行任务"""
        self.stop_flag = False
        self.log("任务开始...")
        if self.use_ip:
            self.log("将使用代理IP进行填写。")
        else:
            self.log("将使用本机IP进行填写。")

        threads_list: list[Thread] = []
        for i in range(self.num_threads):
            x_pos = 50 + (i % 4) * 600
            y_pos = 50 + (i // 4) * 700
            thread = Thread(target=self.run_instance, args=(i + 1, x_pos, y_pos))
            threads_list.append(thread)
            thread.start()
            time.sleep(0.5)

        for t in threads_list:
            t.join()

        self.log("\n--- 任务结束 ---")
        self.log(f"成功填写: {self.cur_num} 份")
        self.log(f"失败次数: {self.cur_fail} 次")
        if self.stop_flag and self.cur_num < self.target_num:
            self.log("任务因失败次数过多或手动停止而提前终止。")