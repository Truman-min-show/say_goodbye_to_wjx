import logging
import random
import re
import threading
import traceback
from threading import Thread
import time
from typing import List

import numpy
import requests
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


"""
代码使用规则：
    1. 安装Python环境及依赖库 (requests, selenium, numpy)。
       如果你使用clone方式的话，执行命令：pip3 install -r requirements.txt
       如果直接copy代码，确保本地环境中已安装这些库。
    2. 下载与你的Chrome浏览器版本匹配的ChromeDriver。
       最新驱动下载地址: https://googlechromelabs.github.io/chrome-for-testing/
    3. 将ChromeDriver可执行文件放在Python安装目录下，或确保它在系统PATH中。
    4. 修改下面的参数：
        - `url`: 替换为你的问卷链接。
        - `*_prob` 参数: 根据你的问卷题目类型和期望的答案比例进行配置。
        - `texts` 和 `texts_prob`: 如果有填空题，配置这些参数。
        - `reorder_prob`: 如果有排序题，配置此参数。
        - `use_ip`: 如果要使用代理IP，设置为True，并在 `zanip()` 函数中配置你的IP代理API链接。
        - `target_num`: 设置期望填写的问卷总份数。
        - `num_threads`: 设置同时运行的浏览器窗口数量。
    5. 运行脚本: python say_goodbye_to_wjx.py

"""

"""
IP代理设置 (可选):
    如果你需要使用代理IP来避免IP限制，可以使用第三方IP代理服务，如“品赞IP” (https://www.ipzan.com)。
    1. 注册并实名认证。(gxy的补充：这个是必须的，否则无法代理)
    2. 将你电脑的公网IP添加到代理网站的白名单中。(gxy的补充：校园网有可能会有多个IP出口，在添加白名单时需要点击“检查是否有其他出口IP”)
    3. 生成API链接（通常选择1分钟时长，txt格式，提取数量1）。
    4. 将API链接粘贴到下面的 `zanip()` 函数中。
    5. 将主程序中的 `use_ip` 设置为 `True`。
    如果不需要代理IP，可以将 `use_ip` 设置为 `False`，脚本将使用本机IP。
"""
def zanip():
    # >>>>> 如果使用代理IP，请将下面的示例API链接替换为你的实际IP代理API链接 <<<<<
    # 示例API链接格式: "https://service.ipzan.com/core-extract?num=1&no=YOUR_ORDER_NO&minute=1&format=txt&pool=quality&mode=whitelist&secret=YOUR_SECRET"
    api = "在此处粘贴你的IP代理API链接" 
    try:
        response = requests.get(api, timeout=10) # 设置超时以防API无响应
        response.raise_for_status() # 如果请求失败 (如4xx, 5xx错误)，则抛出异常
        ip = response.text.strip()
        if not ip: # 如果API返回空字符串
            logging.warning("IP代理API返回空字符串。")
            return "127.0.0.1:0" # 返回一个无效IP，强制使用本机IP
        return ip
    except requests.exceptions.RequestException as e:
        logging.error(f"获取代理IP失败: {e}")
        return "127.0.0.1:0" # 返回一个无效IP，强制使用本机IP


# >>>>> 1. 替换为你的问卷链接 (必改) <<<<<
url = "https://www.wjx.cn/vm/YOUR_SURVEY_ID.aspx#" # 示例链接，请务必修改

# >>>>> 2. 配置题目概率 (必改) <<<<<
# 说明:
#   - 字典的键 (如 "1", "2") 仅为方便人类阅读的题号注释，脚本会按定义顺序处理。
#   - 概率值:
#     - 对于单选、矩阵、量表、下拉框、填空题选项: 使用比例值，如 [85, 15] 表示85%:15%。脚本会自动归一化。
#     - 对于多选题: 每个选项的独立选择概率 (0-100)，如 [40, 78, 85] 表示选项A有40%概率被选，B有78%，C有85%。
#     - -1: 表示随机选择。
#   - 确保每道题的参数列表长度与实际选项数量一致，否则会报错。

# 单选题概率参数
single_prob = {
    "1": [5, 85, 4, 2, 0],  # 示例: Q0. 身份：本科生 85%, 研究生 15%
    "2": [30, 62, 3, 5],  # 示例: Q6. 平衡保护与开发
    "3": [45, 48, 5, 1, 1],  # 示例: Q8. 是否愿意贡献力量
}

# 下拉框概率参数 (如果没有此类题，保持默认或清空)
droplist_prob = {
    "1": [1, 2, 1], # 示例: 第1个下拉框题，3个选项，比例1:2:1
}

# 多选题概率参数
multiple_prob = {
    "1": [40, 78, 85, 25, 68],  # 示例: Q1. 红色文化遗产价值 (5选项)
    "2": [60, 35, 75, 55, 8],  # 示例: Q2. 了解的遗产地 (5选项)
    "3": [55, 72, 90, 45, 80],  # 示例: Q3. 看重的体验 (5选项)
    "4": [78, 82, 70, 60, 15, 3],  # 示例: Q4. 展陈问题 (6选项)
    "5": [55, 88, 38, 78, 25, 70],  # 示例: Q5. 了解方式 (6选项)
    "6": [55, 90, 72, 85, 48],  # 示例: Q7. 传承方式 (5选项)
    "7": [65, 38, 88, 42, 78, 55, 50],  # 示例: Q10. 发挥作用 (7选项)
}

# 矩阵题概率参数 (如果没有此类题，保持默认或清空)
# 每个子问题都需要一行参数
matrix_prob = {
    "1": [1, 0, 0, 0, 0], # 示例: 矩阵题1的子问题1，5个选项，选第1个
    "2": -1,             # 示例: 矩阵题1的子问题2，随机选
}

# 量表题概率参数 (如果没有此类题，保持默认或清空)
scale_prob = {
    "1": [0, 0, 1, 2, 7], # 示例: 第1个量表题，5个等级，比例0:0:1:2:7
}

# 填空题内容及概率 (如果没有此类题，保持默认或清空)
texts = {
    "1": ["内容A", "内容B", "内容C"], # 示例: 第1个填空题的可能答案
}
texts_prob = {
    # "1": [1, 1, 1], # 示例: 第1个填空题答案的比例1:1:1
}

# 排序题概率参数 (如果没有此类题，保持默认或清空)
# key: 排序题的内部索引（从0开始，如第1个排序题，键为"1"）
# options_weights: 字典，键为选项字母(A,B,C...)，值为该选项被选入排序的总次数/权重。
# first_place_weights: 字典，键为选项字母，值为该选项排在第一位的次数/权重。
# num_to_select: 这道排序题总共需要选择并排序几项。
reorder_prob = {
    "1": { # 示例: 第1个排序题 (对应你之前的Q9)
        'options_weights': { 'A': 80, 'B': 78, 'C': 35, 'D': 38, 'E': 20, 'F': 60, 'G': 45, 'H': 10 },
        'first_place_weights': { 'A': 35, 'B': 30 }, # 其他选项作为第一位的权重可设为0或按比例分配
        'num_to_select': 3
    }
}
# 滑块题: 脚本会自动处理，在1-100之间随机选择一个值。

# --- 参数配置结束 ---

# 参数归一化和列表转换 (无需修改)
for prob_dict in [single_prob, droplist_prob, matrix_prob, scale_prob, texts_prob]:
    for key in prob_dict:
        if isinstance(prob_dict[key], list):
            prob_sum = sum(prob_dict[key])
            if prob_sum == 0 and len(prob_dict[key]) > 0: # 避免除以零
                prob_dict[key] = [1 / len(prob_dict[key])] * len(prob_dict[key])
            elif prob_sum > 0 :
                prob_dict[key] = [x / prob_sum for x in prob_dict[key]]

single_prob = list(single_prob.values())
droplist_prob = list(droplist_prob.values())
multiple_prob = list(multiple_prob.values()) # 多选题概率不需要归一化，是独立概率
matrix_prob = list(matrix_prob.values())
scale_prob = list(scale_prob.values())
texts = list(texts.values())
texts_prob = list(texts_prob.values())

# 归一化 reorder_prob
normalized_reorder_prob = []
for key_r in sorted(reorder_prob.keys()): # 按key排序以保证顺序
    params_r = reorder_prob[key_r]
    normalized_params_r = {'num_to_select': params_r.get('num_to_select', 0)}

    # 归一化 options_weights
    options_dict = params_r.get('options_weights', {})
    option_keys_sorted = sorted(options_dict.keys()) 
    options_weights_list = [options_dict.get(k, 0) for k in option_keys_sorted]
    prob_sum_options = sum(options_weights_list)
    if prob_sum_options == 0 and len(options_weights_list) > 0:
        normalized_params_r['options_weights_norm'] = [1 / len(options_weights_list)] * len(options_weights_list)
    elif prob_sum_options > 0:
        normalized_params_r['options_weights_norm'] = [x / prob_sum_options for x in options_weights_list]
    else:
        normalized_params_r['options_weights_norm'] = []
    normalized_params_r['option_keys_sorted'] = option_keys_sorted # 保存原始选项键顺序

    # 归一化 first_place_weights
    first_place_dict = params_r.get('first_place_weights', {})
    # 使用 options_dict 的键序来确保 first_place_weights_norm 与 options_weights_norm 对应
    first_place_weights_list = [first_place_dict.get(k, 0) for k in option_keys_sorted]
    prob_sum_first_place = sum(first_place_weights_list)
    if prob_sum_first_place == 0 and len(first_place_weights_list) > 0:
        normalized_params_r['first_place_weights_norm'] = [1 / len(first_place_weights_list)] * len(first_place_weights_list)
    elif prob_sum_first_place > 0:
        normalized_params_r['first_place_weights_norm'] = [x / prob_sum_first_place for x in first_place_weights_list]
    else:
        normalized_params_r['first_place_weights_norm'] = []
    
    normalized_reorder_prob.append(normalized_params_r)
reorder_prob = normalized_reorder_prob


print("往年都是我往群里发问卷，今年送大家一个小礼物，从github上修改的一个问卷星脚本")
print("但目前仍有缺陷，无法处理跳题逻辑，只能按顺序处理")


# --- 以下为核心脚本逻辑，一般无需修改 ---

# 校验IP地址合法性
def validate(ip):
    pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):(\d{1,5})$"
    if re.match(pattern, ip):
        return True
    return False


# 检测题量
def detect(driver: WebDriver) -> List[int]:
    q_list: List[int] = []
    page_num = len(driver.find_elements(By.XPATH, '//*[@id="divQuestion"]/fieldset'))
    if page_num == 0: # 单页问卷
        questions_on_page = driver.find_elements(By.XPATH, '//*[@id="divQuestion"]/div[@class="field ui-field-contain"]')
        valid_count = sum(1 for q in questions_on_page if q.get_attribute("topic") and q.get_attribute("topic").isdigit())
        if valid_count > 0:
            q_list.append(valid_count)
        return q_list

    for i in range(1, page_num + 1):
        questions = driver.find_elements(By.XPATH, f'//*[@id="fieldset{i}"]/div')
        valid_count = sum(
            1 for question in questions if question.get_attribute("topic") and question.get_attribute("topic").isdigit()
        )
        q_list.append(valid_count)
    return q_list


# 填空题处理函数
def vacant(driver: WebDriver, current, index):
    if index >= len(texts) or index >= len(texts_prob):
        logging.warning(f"填空题 q{current}: 参数texts或texts_prob的索引超出范围，将随机生成内容。")
        driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(f"随机文本{random.randint(1,100)}")
        return

    content_list = texts[index]
    p_list = texts_prob[index]
    if not content_list or not p_list or len(content_list) != len(p_list):
        logging.warning(f"填空题 q{current}: texts或texts_prob参数配置错误，将随机生成内容。")
        driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(f"随机文本{random.randint(1,100)}")
        return

    text_index = numpy.random.choice(a=numpy.arange(0, len(p_list)), p=p_list)
    driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(content_list[text_index])


# 单选题处理函数
def single(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div'
    options = driver.find_elements(By.XPATH, xpath)
    if not options: # 备用路径，如果上面路径找不到选项
        xpath = f'//*[@id="div{current}"]/div[contains(@class, "ui-controlgroup")]/div'
        options = driver.find_elements(By.XPATH, xpath)
    
    if index >= len(single_prob):
        logging.warning(f"单选题 q{current}: 参数single_prob的索引超出范围，将随机选择。")
        r = random.randint(1, len(options))
    else:
        p = single_prob[index]
        if p == -1:
            r = random.randint(1, len(options))
        else:
            if len(p) != len(options):
                logging.error(f"第{current}题(单选)参数长度({len(p)})与选项长度({len(options)})不一致！将随机选择。")
                r = random.randint(1, len(options))
            else:
                r = numpy.random.choice(a=numpy.arange(1, len(options) + 1), p=p)
    driver.find_element(
        By.CSS_SELECTOR, f"#div{current} > div.ui-controlgroup > div:nth-child({r})"
    ).click()


# 下拉框处理函数
def droplist(driver: WebDriver, current, index):
    if index >= len(droplist_prob):
        logging.warning(f"下拉框 q{current}: 参数droplist_prob的索引超出范围，将随机选择。")
        driver.find_element(By.CSS_SELECTOR, f"#select2-q{current}-container").click()
        time.sleep(0.5)
        options = driver.find_elements(By.XPATH, f"//*[@id='select2-q{current}-results']/li")
        # 通常第一个是 "请选择"，所以从第二个开始随机（索引1到len-1）
        r = random.randint(1, len(options) -1) if len(options) > 1 else 0
        driver.find_element(By.XPATH, f"//*[@id='select2-q{current}-results']/li[{r + 1}]").click()
        return

    driver.find_element(By.CSS_SELECTOR, f"#select2-q{current}-container").click()
    time.sleep(0.5)
    options = driver.find_elements(By.XPATH, f"//*[@id='select2-q{current}-results']/li")
    p = droplist_prob[index]
    
    # 下拉框选项通常包含一个无效的 "请选择" 选项，概率参数应对应有效选项
    num_valid_options = len(options) -1 
    if len(p) != num_valid_options:
        logging.error(f"第{current}题(下拉框)参数长度({len(p)})与有效选项长度({num_valid_options})不一致！将随机选择。")
        r_idx = random.randint(0, num_valid_options - 1) if num_valid_options > 0 else 0
    else:
        r_idx = numpy.random.choice(a=numpy.arange(0, num_valid_options), p=p)
    
    driver.find_element(By.XPATH, f"//*[@id='select2-q{current}-results']/li[{r_idx + 2}]").click() # +2 因为li是1-indexed且跳过“请选择”

#多选题处理函数
def multiple(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div'
    options = driver.find_elements(By.XPATH, xpath)
    if not options: # 备用路径
        xpath = f'//*[@id="div{current}"]/div[contains(@class, "ui-controlgroup")]/div'
        options = driver.find_elements(By.XPATH, xpath)

    mul_list = []
    
    if index >= len(multiple_prob):
        logging.warning(f"多选题 q{current}: 参数multiple_prob的索引超出范围，将随机选择至少一项。")
        num_to_select = random.randint(1, len(options))
        selected_indices = random.sample(range(len(options)), num_to_select)
        mul_list = [1 if i in selected_indices else 0 for i in range(len(options))]
    else:
        p = multiple_prob[index]
        if len(options) != len(p):
            logging.error(f"第{current}题(多选)概率值长度({len(p)})和选项数量({len(options)})不一致！将随机选择至少一项。")
            num_to_select = random.randint(1, len(options))
            selected_indices = random.sample(range(len(options)), num_to_select)
            mul_list = [1 if i in selected_indices else 0 for i in range(len(options))]
        else:
            while sum(mul_list) == 0: # 确保至少选择一项
                mul_list = []
                for item_prob in p:
                    a = numpy.random.choice(a=[0, 1], p=[1 - (item_prob / 100), item_prob / 100])
                    mul_list.append(a)
    
    for idx, item_selected in enumerate(mul_list):
        if item_selected == 1:
            css = f"#div{current} > div.ui-controlgroup > div:nth-child({idx + 1})"
            driver.find_element(By.CSS_SELECTOR, css).click()


# 矩阵题处理函数
def matrix(driver: WebDriver, current, current_matrix_sub_q_index):
    xpath1 = f'//*[@id="divRefTab{current}"]/tbody/tr'
    rows = driver.find_elements(By.XPATH, xpath1)
    q_num_in_matrix = 0
    for tr in rows:
        if tr.get_attribute("rowindex") is not None:
            q_num_in_matrix += 1
    
    if q_num_in_matrix == 0: # 如果没有找到rowindex，尝试另一种方式计数
        q_num_in_matrix = len(driver.find_elements(By.XPATH, f'//*[@id="divRefTab{current}"]/tbody/tr[td[@class="matrixdatatitle"]]'))


    xpath2 = f'//*[@id="drv{current}_1"]/td' # 获取一个子问题的选项列数
    cols = driver.find_elements(By.XPATH, xpath2)
    num_options_per_sub_q = len(cols) -1 # -1 是因为第一列是题干

    for i in range(1, q_num_in_matrix + 1):
        if current_matrix_sub_q_index >= len(matrix_prob):
            logging.warning(f"矩阵题 q{current} 的子题 {i}: 参数matrix_prob的索引超出范围，将随机选择。")
            opt_idx = random.randint(0, num_options_per_sub_q - 1)
        else:
            p = matrix_prob[current_matrix_sub_q_index]
            if p == -1:
                opt_idx = random.randint(0, num_options_per_sub_q - 1)
            else:
                if len(p) != num_options_per_sub_q:
                    logging.error(f"矩阵题 q{current} 子题{i} 参数长度({len(p)})与选项数({num_options_per_sub_q})不一致！将随机。")
                    opt_idx = random.randint(0, num_options_per_sub_q - 1)
                else:
                    opt_idx = numpy.random.choice(a=numpy.arange(0, num_options_per_sub_q), p=p)
        
        # CSS selector td:nth-child(opt_idx + 2) because options start from the 2nd td
        driver.find_element(By.CSS_SELECTOR, f"#drv{current}_{i} > td:nth-child({opt_idx + 2})").click()
        current_matrix_sub_q_index += 1
    return current_matrix_sub_q_index


# 排序题处理函数
def reorder(driver: WebDriver, current, index):
    all_option_elements_xpath = f'//*[@id="div{current}"]/ul/li'
    all_option_elements = driver.find_elements(By.XPATH, all_option_elements_xpath)
    num_all_options = len(all_option_elements)

    if index >= len(reorder_prob) or not reorder_prob[index] or num_all_options == 0:
        logging.warning(f"排序题 q{current}: 未设置参数、索引超出范围或无选项，将随机排序所有可选项。")
        for j in range(1, num_all_options + 1):
            # nth-child is 1-indexed. Randomly pick from remaining UNCLICKED options.
            # This simplified random click might not be true reordering but sequential random picks.
            # A better random reorder would be to shuffle indices then click.
            # For now, using original script's random click logic for fallback.
            remaining_options = driver.find_elements(By.XPATH, f'{all_option_elements_xpath}[not(contains(@class, "active"))]')
            if not remaining_options: break
            random.choice(remaining_options).click()
            time.sleep(0.4)
        return

    params = reorder_prob[index]
    num_to_select = params.get('num_to_select', num_all_options)
    option_keys_sorted = params.get('option_keys_sorted', [chr(65+i) for i in range(num_all_options)]) # A, B, C...
    
    # Ensure options_weights_norm matches the number of actual options on page
    actual_options_weights_norm = params['options_weights_norm'][:num_all_options]
    if sum(actual_options_weights_norm) > 0: # Renormalize if truncated
         actual_options_weights_norm = [w / sum(actual_options_weights_norm) for w in actual_options_weights_norm]
    else: # Fallback to uniform if all zero after truncation
        actual_options_weights_norm = [1/num_all_options]*num_all_options


    selected_option_indices_0_based = numpy.random.choice(
        a=numpy.arange(num_all_options),
        size=min(num_to_select, num_all_options),
        replace=False,
        p=actual_options_weights_norm
    ).tolist()

    ordered_click_indices_0_based = []

    if selected_option_indices_0_based and 'first_place_weights_norm' in params and params['first_place_weights_norm']:
        # Filter first_place_weights to only include selected options
        current_first_place_weights = []
        map_selected_idx_to_original_idx = {} # Maps position in selected_option_indices_0_based to original 0-based index
        
        for i, original_idx in enumerate(selected_option_indices_0_based):
            # Check if original_idx is within the bounds of first_place_weights_norm
            if original_idx < len(params['first_place_weights_norm']):
                 current_first_place_weights.append(params['first_place_weights_norm'][original_idx])
                 map_selected_idx_to_original_idx[len(current_first_place_weights)-1] = original_idx
            # else: # if an option was selected that doesn't have a first_place_weight (e.g. more options on page than in config)
                # current_first_place_weights.append(0) # assign zero weight
                # map_selected_idx_to_original_idx[len(current_first_place_weights)-1] = original_idx


        if sum(current_first_place_weights) > 0:
            normalized_current_weights = [w / sum(current_first_place_weights) for w in current_first_place_weights]
            
            # Choose based on the relative index within current_first_place_weights
            chosen_relative_idx_for_first = numpy.random.choice(
                a=numpy.arange(len(current_first_place_weights)),
                p=normalized_current_weights
            )
            # Map back to original 0-based index
            actual_first_item_original_idx = map_selected_idx_to_original_idx[chosen_relative_idx_for_first]
            
            ordered_click_indices_0_based.append(actual_first_item_original_idx)
            selected_option_indices_0_based.remove(actual_first_item_original_idx) # Remove from list of to-be-shuffled
        elif selected_option_indices_0_based: # If no valid first place weights, pick randomly from selected
            actual_first_item_original_idx = random.choice(selected_option_indices_0_based)
            ordered_click_indices_0_based.append(actual_first_item_original_idx)
            selected_option_indices_0_based.remove(actual_first_item_original_idx)

    random.shuffle(selected_option_indices_0_based)
    ordered_click_indices_0_based.extend(selected_option_indices_0_based)

    for idx_0_based_to_click in ordered_click_indices_0_based:
        # nth-child is 1-indexed
        all_option_elements[idx_0_based_to_click].click()
        time.sleep(0.4)


# 量表题处理函数
def scale(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div/ul/li'
    options = driver.find_elements(By.XPATH, xpath)
    if not options: # 备用
        xpath = f'//*[@id="div{current}"]/div[contains(@class, "scale-div")]/div/ul/li'
        options = driver.find_elements(By.XPATH, xpath)

    if index >= len(scale_prob):
        logging.warning(f"量表题 q{current}: 参数scale_prob的索引超出范围，将随机选择。")
        r = random.randint(1, len(options))
    else:
        p = scale_prob[index]
        if p == -1:
            r = random.randint(1, len(options))
        else:
            if len(p) != len(options):
                logging.error(f"第{current}题(量表)参数长度({len(p)})与选项长度({len(options)})不一致！将随机选择。")
                r = random.randint(1, len(options))
            else:
                r = numpy.random.choice(a=numpy.arange(1, len(options) + 1), p=p)
    
    driver.find_element(
        # Original selector might be too specific if structure varies
        By.CSS_SELECTOR, f"#div{current} div.scale-div div ul li:nth-child({r})"
        # f"#div{current} > div.scale-div > div > ul > li:nth-child({r})"
    ).click()


# 刷题逻辑函数
def brush(driver: WebDriver):
    q_list = detect(driver)
    if not q_list:
        logging.error("未能检测到问卷题目数量，可能问卷结构不支持或已更改。")
        raise Exception("无法检测题目")

    single_num, vacant_num, droplist_num, multiple_num, matrix_sub_q_num, scale_num, reorder_num = 0, 0, 0, 0, 0, 0, 0
    current_q_abs_idx = 0 # 绝对题号计数器

    for page_idx, num_q_on_page in enumerate(q_list):
        for q_on_page_idx in range(1, num_q_on_page + 1):
            current_q_abs_idx += 1
            
            # 查找当前题目元素
            try:
                current_q_element = driver.find_element(By.CSS_SELECTOR, f"#div{current_q_abs_idx}")
                q_type = current_q_element.get_attribute("type")
            except Exception as e:
                logging.error(f"获取第 {current_q_abs_idx} 题的类型失败: {e}。将跳过此题。")
                continue # 跳过无法处理的题目

            if not q_type: # 如果type属性为空，尝试从其他属性推断或记录错误
                logging.warning(f"第 {current_q_abs_idx} 题类型未知 (type属性为空)。将尝试跳过。")
                continue

            # print(f"正在处理第 {current_q_abs_idx} 题，类型: {q_type}") # 调试信息
            if q_type == "1" or q_type == "2":  # 填空题
                vacant(driver, current_q_abs_idx, vacant_num)
                vacant_num += 1
            elif q_type == "3":  # 单选
                single(driver, current_q_abs_idx, single_num)
                single_num += 1
            elif q_type == "4":  # 多选
                multiple(driver, current_q_abs_idx, multiple_num)
                multiple_num += 1
            elif q_type == "5":  # 量表题
                scale(driver, current_q_abs_idx, scale_num)
                scale_num += 1
            elif q_type == "6":  # 矩阵题
                matrix_sub_q_num = matrix(driver, current_q_abs_idx, matrix_sub_q_num)
            elif q_type == "7":  # 下拉框
                droplist(driver, current_q_abs_idx, droplist_num)
                droplist_num += 1
            elif q_type == "8":  # 滑块题
                try:
                    score_input = driver.find_element(By.CSS_SELECTOR, f"#q{current_q_abs_idx}")
                    score = random.randint(int(score_input.get_attribute("min") or 1), 
                                         int(score_input.get_attribute("max") or 100))
                    driver.execute_script(f"arguments[0].value = '{score}'; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'));", score_input)
                except Exception as e_slider:
                    logging.warning(f"处理滑块题 {current_q_abs_idx} 失败: {e_slider}, 将尝试简单send_keys")
                    try:
                        driver.find_element(By.CSS_SELECTOR, f"#q{current_q_abs_idx}").send_keys(str(random.randint(1,100)))
                    except: pass # 再次失败则放弃
            elif q_type == "11":  # 排序题
                reorder(driver, current_q_abs_idx, reorder_num)
                reorder_num += 1
            else:
                logging.warning(f"第 {current_q_abs_idx} 题为不支持的题型 (type: {q_type})，已跳过。")
        
        time.sleep(0.5)
        # 点击下一页或提交
        if page_idx < len(q_list) - 1: # 如果不是最后一页
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "#divNext")
                if next_button.is_displayed() and next_button.is_enabled():
                    next_button.click()
                    time.sleep(1) # 等待页面加载
                else: # 后备方案，如果下一页按钮不满足条件，尝试通过JS点击
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(1)
            except Exception:
                logging.warning(f"点击下一页按钮失败，可能是最后一页或按钮不存在。尝试寻找提交按钮。")
                # 如果下一页失败，可能是最后一页了，尝试提交
                try:
                    driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
                    time.sleep(1)
                except: pass # 再次失败则等待submit函数处理
        else: # 最后一页，直接点击提交
            try:
                driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
                time.sleep(1)
            except Exception as e:
                logging.error(f"点击最终提交按钮失败: {e}")
    submit(driver)


# 提交函数
def submit(driver: WebDriver):
    time.sleep(1)
    # 点击可能的确认弹窗
    try:
        confirm_button = driver.find_element(By.XPATH, '//*[@id="layui-layer1"]/div[3]/a[contains(@class, "layui-layer-btn0")]')
        if confirm_button.is_displayed() and confirm_button.is_enabled():
            confirm_button.click()
            time.sleep(1)
    except:
        pass

    # 点击智能检测按钮 (如有)
    try:
        sm_button = driver.find_element(By.XPATH, '//*[@id="SM_BTN_1"]')
        if sm_button.is_displayed() and sm_button.is_enabled():
            sm_button.click()
            time.sleep(3)
    except:
        pass

    # 滑块验证 (如有)
    try:
        slider_text_element = driver.find_element(By.XPATH, '//*[@id="nc_1__scale_text"]/span')
        slider_button = driver.find_element(By.XPATH, '//*[@id="nc_1_n1z"]')
        if "请按住滑块" in slider_text_element.text:
            width = slider_text_element.size.get("width", 260) # Default width if not found
            ActionChains(driver).drag_and_drop_by_offset(slider_button, width, 0).perform()
            time.sleep(2)
    except:
        pass


def run(thread_id, xx, yy):
    option = webdriver.ChromeOptions()
    option.add_experimental_option("excludeSwitches", ["enable-automation"])
    option.add_experimental_option("useAutomationExtension", False)
    # option.add_argument("--headless")  # 可选: 无头模式，不在前台显示浏览器窗口
    # option.add_argument("--disable-gpu") # 可选: 配合无头模式
    # option.add_argument("--log-level=3") # 可选: 减少控制台日志输出
    # option.add_argument("--blink-settings=imagesEnabled=false") # 可选：不加载图片，加快速度

    global cur_num, cur_fail, stop_flag

    while cur_num < target_num and not stop_flag:
        driver = None # 初始化driver
        try:
            if use_ip:
                ip_address = zanip()
                if validate(ip_address):
                    option.add_argument(f"--proxy-server={ip_address}")
                    # print(f"线程 {thread_id} 使用代理IP: {ip_address}") # 调试信息
                else:
                    logging.warning(f"线程 {thread_id} 获取的IP {ip_address} 无效，将使用本机IP。")
                    # 移除可能存在的旧代理设置
                    current_args = option.arguments
                    option.arguments = [arg for arg in current_args if not arg.startswith('--proxy-server=')]
            
            driver = webdriver.Chrome(options=option)
            driver.set_page_load_timeout(60) # 设置页面加载超时
            driver.set_window_size(550, 650)
            driver.set_window_position(x=xx, y=yy)
            
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
            )
            
            driver.get(url)
            url1 = driver.current_url
            brush(driver)
            time.sleep(4) # 等待提交后页面跳转
            url2 = driver.current_url
            
            if url1 != url2 or "finish" in url2 or "survey" not in url2.lower(): # 成功条件更灵活
                with lock:
                    if cur_num < target_num : # 再次检查，避免超额计数
                        cur_num += 1
                        print(f"线程 {thread_id}: 已填写 {cur_num}/{target_num} 份 - 失败 {cur_fail} 次 - {time.strftime('%H:%M:%S')}")
            else:
                raise Exception("URL未跳转或跳转至错误页面，可能提交失败")

        except Exception as e:
            # traceback.print_exc() # 打印详细错误，调试时开启
            logging.error(f"线程 {thread_id} 发生错误: {e}")
            with lock:
                cur_fail += 1
                print(f"\033[91m线程 {thread_id}: 失败1次 (总失败{cur_fail})。错误: {str(e)[:100]}...\033[0m")
                if cur_fail >= fail_threshold:
                    logging.critical(f"失败次数 ({cur_fail}) 已达阈值 ({fail_threshold})，程序将停止。")
                    stop_flag = True
        finally:
            if driver:
                driver.quit()
            # 移除本次使用的代理，以便下次循环获取新的 (如果使用了代理)
            if use_ip:
                 current_args = option.arguments
                 option.arguments = [arg for arg in current_args if not arg.startswith('--proxy-server=')]
            
            if stop_flag: # 如果需要停止，则线程退出循环
                break
        
        # 控制请求频率，避免过快，可根据需要调整
        time.sleep(random.uniform(1, 3))


# --- 主程序入口 ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # >>>>> 3. 配置运行参数 (可选修改) <<<<<
    target_num = 10       # 目标填写的问卷总份数
    num_threads = 2       # 同时运行的浏览器窗口数量 (线程数)
    use_ip = False        # 是否使用代理IP (True/False)

    # --- 以下为内部变量，一般无需修改 ---
    fail_threshold = max(5, target_num // 2 + 1) # 失败阈值，至少为5，或目标数的一半加1
    cur_num = 0           # 当前已成功提交份数
    cur_fail = 0          # 当前已失败次数
    lock = threading.Lock() # 线程锁，用于同步计数器
    stop_flag = False     # 全局停止标志

    if use_ip:
        print("将尝试使用代理IP进行填写。请确保zanip()函数已配置正确。")
        # 可以在这里做一次初步的IP获取测试，但不强制，run函数内部会处理
        # test_ip = zanip()
        # if not validate(test_ip):
        #     print(f"警告: 初步测试获取的IP {test_ip} 无效。脚本仍会尝试在运行时获取。")
    else:
        print("将使用本机IP进行填写。")

    threads_list: list[Thread] = []
    for i in range(num_threads):
        # 计算浏览器窗口位置，避免重叠过多
        x_pos = 50 + (i % 4) * 600 # 每行最多4个窗口
        y_pos = 50 + (i // 4) * 700
        thread = Thread(target=run, args=(i + 1, x_pos, y_pos)) # 传入线程ID
        threads_list.append(thread)
        thread.start()
        time.sleep(0.5) # 错开启动时间

    for t in threads_list:
        t.join()

    print(f"\n--- 任务结束 ---")
    print(f"成功填写: {cur_num} 份")
    print(f"失败次数: {cur_fail} 次")
    if stop_flag and cur_num < target_num:
        print("任务因失败次数过多或手动停止而提前终止。")