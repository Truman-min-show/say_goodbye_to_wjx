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
任何疑问，请加qq群咨询：774326264 || 427847187 || 850281779 || 931614446
代码简洁版：https://github.com/Zemelee/wjx/blob/master/wjx.py  ---  视频教程： https://www.bilibili.com/video/BV1qc411T7CG/
除了python，作者还发布了js版脚本在scriptcat和greasyfork上，名字就叫“问卷星脚本”，不带任何前后缀，比py更方便且支持跳题逻辑：
    scriptcat地址：https://scriptcat.org/zh-CN/script-show-page/2833
    greasyfork地址：https://greasyfork.org/zh-CN/scripts/466722-%E9%97%AE%E5%8D%B8%E6%98%9F%E8%84%9A%E6%9C%AC
    相关系列教程：https://space.bilibili.com/29109990/channel/collectiondetail?sid=1340503&ctype=0

代码使用规则：
    你需要提前安装python环境，且已具备上述的所有安装包
    还需要下载好chrome的chromeDriver自动化工具（chrome版本号需要和chromedriver匹配，具体参考教程）
    并将chromeDriver放在python安装目录下，以便和selenium配套使用，准备工作做好即可直接运行
    按要求填写比例值并替换成自己的问卷链接即可运行你的问卷。
    虽然但是！！！即使正确填写概率值，不保证100%成功运行，因为代码再强大也强大不过问卷星的灵活性，别问我怎么知道的，都是泪
    如果有疑问可以进群提问，或者直接通过代刷网 http://sugarblack.top 直接刷问卷
"""

"""
获取代理ip，这里要使用到一个叫“品赞ip”的第三方服务: https://www.ipzan.com?pid=ggj6roo98
注册，需要实名认证（这是为了防止你用代理干违法的事，相当于网站的免责声明，属于正常步骤，所有代理网站都会有这一步）
将自己电脑的公网ip添加到网站的白名单中，然后选择地区，时长为1分钟，数据格式为txt，提取数量选1
然后点击生成api，将链接复制到放在zanip函数里
设置完成后，不要问为什么和视频教程有点不一样，因为与时俱进！(其实是因为懒，毕竟代码改起来容易，视频录起来不容易嘿嘿2023.10.29)
如果不需要ip可不设置，只是所有问卷的ip都会是同一个（悄悄提醒，品赞ip每周可以领3块钱）
"""


def zanip():
    # 这里放你的ip链接，选择你想要的地区，1分钟，ip池无所谓，数据格式txt，提取数量1，数量一定是1!其余默认即可
    api = "https://service.ipzan.com/core-extract?num=1&no=20250522189605937191&minute=1&format=txt&pool=quality&mode=whitelist&secret=0v7gjkts5jv9l5o"
    ip = requests.get(api).text
    return ip


# 示例问卷,试运行结束后,需要改成你的问卷地址
# >>>>> 请将此处的问卷链接替换为你的问卷链接！！！ <<<<<
url = "https://www.wjx.cn/vm/wFPBGut.aspx#"

"""
单选题概率参数，"1"表示第一题，0表示不选， [30, 70]表示3:7，-1表示随机
根据你提供的 Q0, Q6, Q8 题的数据进行修改
"""
single_prob = {
    "1": [5, 85, 4, 2, 0],  # Q0. 身份：本科生 85%, 研究生 15%
    "2": [30, 62, 3, 5],  # Q6. 如何平衡“保护”与“开发”：严格保护优先 30%, 在有效保护的前提下适度开发 62%, 以开发利用为主 3%, 视具体情况而定 5%
    "3": [45, 48, 5, 1, 1],  # Q8. 是否愿意为红色文化遗产保护贡献力量：非常愿意 45%, 比较愿意 48%, 一般 5%, 不太愿意 1%, 完全不愿意 1%
}

# 下拉框参数，你的问卷中没有此类题型，保持默认
droplist_prob = {"1": [2, 1, 1]}

# 多选题概率参数，表示每个选项选择的概率，100表示必选，30表示选择B的概率为30
# 根据你提供的 Q1, Q2, Q3, Q4, Q5, Q7, Q9, Q10 题的数据进行修改
multiple_prob = {
    "1": [40, 78, 85, 25, 68],  # Q1. 红色文化遗产最重要的价值
    "2": [60, 35, 75, 55, 8],  # Q2. 比较了解的红色文化遗产地
    "3": [55, 72, 90, 45, 80],  # Q3. 参观时最看重的体验
    "4": [78, 82, 70, 60, 15, 3],  # Q4. 当前展陈方式的主要问题
    "5": [55, 88, 38, 78, 25, 70],  # Q5. 更倾向于了解红色文化的方式
    "6": [55, 90, 72, 85, 48],  # Q7. 更有效向年轻一代传承红色文化的方式
    "7": [65, 38, 88, 42, 78, 55, 50],  # Q10. 青年一代传承红色基因最应该发挥作用的方式
}

# 矩阵题概率参数，你的问卷中没有此类题型，保持默认
matrix_prob = {
    "1": [1, 0, 0, 0, 0],
    "2": -1,
    "3": [1, 0, 0, 0, 0],
    "4": [1, 0, 0, 0, 0],
    "5": [1, 0, 0, 0, 0],
    "6": [1, 0, 0, 0, 0],
}

# 量表题概率参数，你的问卷中没有此类题型，保持默认
scale_prob = {"7": [0, 2, 3, 4, 1], "12": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]}

# 填空题参数，你的问卷中没有此类题型，保持默认
texts = {
    "8": ["内容1", "内容2", " 内容3"],
}
# 每个内容对应的概率1:1:1, 你的问卷中没有此类题型，保持默认
texts_prob = {"8": [1, 1, 1]}
# >>>>> START OF NEW CODE BLOCK FOR REORDER_PROB <<<<<
# 排序题概率参数
# key: 排序题的内部索引（从0开始，Q9是你的第一个排序题，所以是"1"）
# options_weights: 对应选项的总选择次数，用于概率性选择要排序的3项（按A,B,C...顺序）
# first_place_weights: 用于确定被选中的3项中哪一个排在第一位（按选项字母表示）
reorder_prob = {
    "1": { # Q9是你的第一个排序题，对应这里的索引为"1"（实际上是list[0]）
        'options_weights': { # 选项的原始权重（总次数），用于决定哪些选项被选中
            'A': 80, 'B': 78, 'C': 35, 'D': 38, 'E': 20, 'F': 60, 'G': 45, 'H': 10
        },
        'first_place_weights': { # 选项作为第一位的权重，用于确定被选中的3项中的首位
            'A': 35, # A. 增加高科技互动体验 (35%的人将其选为第一重要)
            'B': 30, # B. 引入更生动的叙事方式 (30%的人将其选为第一重要)
            # 其他选项未明确给出“第一重要”的比例，这里假设为0，或者可以根据总次数按比例分配
        },
        'num_to_select': 3 # 每人选3项并排序
    }
}
# 排序题不支持设置参数，如果有排序题程序会自动处理
# 滑块题没支持参数，程序能自动处理部分滑块题

# --------------到此为止，参数设置完毕，可以直接运行啦！-------------------
# 如果需要设置浏览器窗口数量，请转到最后一个函数(main函数)，注意看里面的注释喔！


# 参数归一化，把概率值按比例缩放到概率值和为1，比如某个单选题[1,2,3,4]会被转化成[0.1,0.2,0.3,0.4],[1,1]会转化成[0.5,0.5]
for prob in [single_prob, matrix_prob, droplist_prob, scale_prob, texts_prob]:
    for key in prob:
        if isinstance(prob[key], list):
            prob_sum = sum(prob[key])
            # 避免除以零，如果所有概率都为0，则平均分配
            if prob_sum == 0:
                num_options = len(prob[key])
                prob[key] = [1 / num_options] * num_options
            else:
                prob[key] = [x / prob_sum for x in prob[key]]

# 转化为列表,去除题号
single_prob = list(single_prob.values())
droplist_prob = list(droplist_prob.values())
multiple_prob = list(multiple_prob.values())
matrix_prob = list(matrix_prob.values())
scale_prob = list(scale_prob.values())
texts_prob = list(texts_prob.values())
texts = list(texts.values())

# >>>>> START OF NEW CODE BLOCK FOR REORDER_PROB NORMALIZATION <<<<<
# 归一化 reorder_prob
for key in reorder_prob:
    # 归一化 options_weights
    options_dict = reorder_prob[key]['options_weights']
    option_keys_sorted = sorted(options_dict.keys()) # 确保顺序 (A, B, C...)
    options_weights_list = [options_dict[k] for k in option_keys_sorted]
    prob_sum_options = sum(options_weights_list)
    if prob_sum_options == 0:
        reorder_prob[key]['options_weights_norm'] = [1 / len(options_weights_list)] * len(options_weights_list)
    else:
        reorder_prob[key]['options_weights_norm'] = [x / prob_sum_options for x in options_weights_list]

    # 归一化 first_place_weights
    first_place_dict = reorder_prob[key]['first_place_weights']
    first_place_weights_list = [first_place_dict.get(k, 0) for k in option_keys_sorted] # 如果某项没有权重，则为0
    prob_sum_first_place = sum(first_place_weights_list)
    if prob_sum_first_place == 0:
        reorder_prob[key]['first_place_weights_norm'] = [1 / len(first_place_weights_list)] * len(first_place_weights_list)
    else:
        reorder_prob[key]['first_place_weights_norm'] = [x / prob_sum_first_place for x in first_place_weights_list]

reorder_prob = list(reorder_prob.values()) # 转换为列表
# >>>>> END OF NEW CODE BLOCK FOR REORDER_PROB NORMALIZATION <<<<<


print("所有按照比例刷题的脚本只能让问卷总体数据表面上看起来合理, 并不保证高信效度。")
print("刷问卷的其他方法可以参考:  http://sugarblack.top  ")
print("如果程序对你有帮助，请给我一个免费的 star 或 fork ~!")


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
    for i in range(1, page_num + 1):
        questions = driver.find_elements(By.XPATH, f'//*[@id="fieldset{i}"]/div')
        valid_count = sum(
            1 for question in questions if question.get_attribute("topic").isdigit()
        )
        q_list.append(valid_count)
    return q_list


# 填空题处理函数
def vacant(driver: WebDriver, current, index):
    # 检查texts和texts_prob列表长度是否足够
    if index >= len(texts) or index >= len(texts_prob):
        logging.warning(f"填空题 q{current}: 参数texts或texts_prob的索引超出范围，将随机生成内容。")
        driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(f"随机生成内容 {random.randint(1,100)}")
        return

    content = texts[index]
    # 对应填空题概率参数
    p = texts_prob[index]
    text_index = numpy.random.choice(a=numpy.arange(0, len(p)), p=p)
    driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(content[text_index])


# 单选题处理函数
def single(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div'
    a = driver.find_elements(By.XPATH, xpath)
    # 检查single_prob列表长度是否足够
    if index >= len(single_prob):
        logging.warning(f"单选题 q{current}: 参数single_prob的索引超出范围，将随机选择。")
        r = random.randint(1, len(a))
    else:
        p = single_prob[index]
        if p == -1: # -1 表示随机
            r = random.randint(1, len(a))
        else:
            assert len(p) == len(
                a
            ), f"第{current}题参数长度：{len(p)},选项长度{len(a)},不一致！"
            r = numpy.random.choice(a=numpy.arange(1, len(a) + 1), p=p)
    driver.find_element(
        By.CSS_SELECTOR, f"#div{current} > div.ui-controlgroup > div:nth-child({r})"
    ).click()


# 下拉框处理函数
def droplist(driver: WebDriver, current, index):
    # 检查droplist_prob列表长度是否足够
    if index >= len(droplist_prob):
        logging.warning(f"下拉框 q{current}: 参数droplist_prob的索引超出范围，将随机选择。")
        # 随机选择一个选项
        driver.find_element(By.CSS_SELECTOR, f"#select2-q{current}-container").click()
        time.sleep(0.5)
        options = driver.find_elements(By.XPATH, f"//*[@id='select2-q{current}-results']/li")
        r = random.randint(1, len(options) - 1) # 假设第一个是“请选择”
        driver.find_element(By.XPATH, f"//*[@id='select2-q{current}-results']/li[{r + 1}]").click()
        return

    # 先点击“请选择”
    driver.find_element(By.CSS_SELECTOR, f"#select2-q{current}-container").click()
    time.sleep(0.5)
    # 选项数量
    options = driver.find_elements(
        By.XPATH, f"//*[@id='select2-q{current}-results']/li"
    )
    p = droplist_prob[index]  # 对应概率
    r = numpy.random.choice(a=numpy.arange(1, len(options)), p=p)
    driver.find_element(
        By.XPATH, f"//*[@id='select2-q{current}-results']/li[{r + 1}]"
    ).click()


def multiple(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div'
    options = driver.find_elements(By.XPATH, xpath)
    mul_list = []

    # 检查multiple_prob列表长度是否足够
    if index >= len(multiple_prob):
        logging.warning(f"多选题 q{current}: 参数multiple_prob的索引超出范围，将随机选择至少一项。")
        # 随机选择至少一个选项
        num_to_select = random.randint(1, len(options))
        selected_indices = random.sample(range(len(options)), num_to_select)
        mul_list = [1 if i in selected_indices else 0 for i in range(len(options))]
    else:
        p = multiple_prob[index]
        assert len(options) == len(p), f"第{current}题概率值和选项值不一致"
        # 生成序列,同时保证至少有一个1
        while sum(mul_list) == 0: # 确保至少选择一项
            mul_list = []
            for item in p:
                a = numpy.random.choice(
                    a=numpy.arange(0, 2), p=[1 - (item / 100), item / 100]
                )
                mul_list.append(a)
    # 依次点击
    for idx, item in enumerate(mul_list):
        if item == 1:
            css = f"#div{current} > div.ui-controlgroup > div:nth-child({idx + 1})"
            driver.find_element(By.CSS_SELECTOR, css).click()


# 矩阵题处理函数
def matrix(driver: WebDriver, current, index):
    xpath1 = f'//*[@id="divRefTab{current}"]/tbody/tr'
    a = driver.find_elements(By.XPATH, xpath1)
    q_num = 0  # 矩阵的题数量
    for tr in a:
        if tr.get_attribute("rowindex") is not None:
            q_num += 1
    # 选项数量
    xpath2 = f'//*[@id="drv{current}_1"]/td'
    b = driver.find_elements(By.XPATH, xpath2)  # 题的选项数量+1 = 6

    # 遍历每一道小题
    for i in range(1, q_num + 1):
        # 检查matrix_prob列表长度是否足够
        if index >= len(matrix_prob):
            logging.warning(f"矩阵题 q{current} 的子题 {i}: 参数matrix_prob的索引超出范围，将随机选择。")
            opt = random.randint(2, len(b))
        else:
            p = matrix_prob[index]
            if p == -1: # -1 表示随机
                opt = random.randint(2, len(b))
            else:
                opt = numpy.random.choice(a=numpy.arange(2, len(b) + 1), p=p)
        driver.find_element(
            By.CSS_SELECTOR, f"#drv{current}_{i} > td:nth-child({opt})"
        ).click()
        index += 1 # 移动到下一个矩阵小题的概率参数
    return index


# 排序题处理函数，现在支持根据参数进行概率性选择和排序
def reorder(driver: WebDriver, current, index):  # 新增 index 参数
    # 获取所有选项元素
    all_option_elements = driver.find_elements(By.XPATH, f'//*[@id="div{current}"]/ul/li')
    num_all_options = len(all_option_elements)

    # 检查是否有为当前排序题设置的参数
    if index >= len(reorder_prob) or not reorder_prob[index]:
        logging.warning(f"排序题 q{current}: 未设置参数或索引超出范围，将随机排序。")
        # 如果没有参数，回退到随机排序的逻辑
        for j in range(1, num_all_options + 1):
            b = random.randint(j, num_all_options)
            driver.find_element(
                By.CSS_SELECTOR, f"#div{current} > ul > li:nth-child({b})"
            ).click()
            time.sleep(0.4)
        return

    params = reorder_prob[index]
    num_to_select = params.get('num_to_select', num_all_options)  # 获取要选择的数量，默认为所有选项

    # 1. 概率性选择 num_to_select 个选项
    # options_weights_norm 是一个列表，其索引对应 all_option_elements 的索引
    # numpy.random.choice 返回的是0-indexed的索引
    selected_option_indices = numpy.random.choice(
        a=numpy.arange(num_all_options),
        size=min(num_to_select, num_all_options),  # 确保选择数量不超过总选项数
        replace=False,  # 不重复选择
        p=params['options_weights_norm']
    ).tolist()

    ordered_click_indices = []

    # 2. 确定排序顺序 (优先选择第一位，剩余的随机)
    if len(selected_option_indices) > 0 and 'first_place_weights_norm' in params:
        # 从已选中的选项中，根据 first_place_weights_norm 概率性地选择第一个
        current_first_place_weights = [params['first_place_weights_norm'][i] for i in selected_option_indices]

        # 确保权重列表的和不为零，避免归一化错误
        sum_current_weights = sum(current_first_place_weights)
        if sum_current_weights > 0:
            normalized_current_weights = [w / sum_current_weights for w in current_first_place_weights]

            first_item_in_selected_list_idx = numpy.random.choice(
                a=numpy.arange(len(selected_option_indices)),  # 在selected_option_indices内部的索引
                p=normalized_current_weights
            )

            actual_first_item_index = selected_option_indices.pop(first_item_in_selected_list_idx)  # 从待选列表中移除并获取实际索引
            ordered_click_indices.append(actual_first_item_index)
        else:
            # 如果没有有效的first_place_weights，随机选择一个作为第一个
            first_item_in_selected_list_idx = random.randint(0, len(selected_option_indices) - 1)
            actual_first_item_index = selected_option_indices.pop(first_item_in_selected_list_idx)
            ordered_click_indices.append(actual_first_item_index)

    # 剩余的已选选项进行随机排序
    random.shuffle(selected_option_indices)
    ordered_click_indices.extend(selected_option_indices)

    # 3. 按照确定的顺序点击选项
    for idx_to_click in ordered_click_indices:
        # 因为 nth-child 是 1-indexed，而列表索引是 0-indexed，所以需要 +1
        driver.find_element(By.CSS_SELECTOR, f"#div{current} > ul > li:nth-child({idx_to_click + 1})").click()
        time.sleep(0.4)


# 量表题处理函数
def scale(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div/ul/li'
    a = driver.find_elements(By.XPATH, xpath)

    # 检查scale_prob列表长度是否足够
    if index >= len(scale_prob):
        logging.warning(f"量表题 q{current}: 参数scale_prob的索引超出范围，将随机选择。")
        b = random.randint(1, len(a))
    else:
        p = scale_prob[index]
        if p == -1: # -1 表示随机
            b = random.randint(1, len(a))
        else:
            b = numpy.random.choice(a=numpy.arange(1, len(a) + 1), p=p)
    driver.find_element(
        By.CSS_SELECTOR, f"#div{current} > div.scale-div > div > ul > li:nth-child({b})"
    ).click()


# 刷题逻辑函数
def brush(driver: WebDriver):
    q_list = detect(driver)  # 检测页数和每一页的题量
    single_num = 0  # 第num个单选题
    vacant_num = 0  # 第num个填空题
    droplist_num = 0  # 第num个下拉框题
    multiple_num = 0  # 第num个多选题
    matrix_num = 0  # 第num个矩阵小题
    scale_num = 0  # 第num个量表题
    reorder_num = 0 # >>>>> 新增：第num个排序题的计数器 <<<<<
    current = 0  # 题号
    for j in q_list:  # 遍历每一页
        for k in range(1, j + 1):  # 遍历该页的每一题
            current += 1
            # 判断题型 md, python没有switch-case语法
            q_type = driver.find_element(
                By.CSS_SELECTOR, f"#div{current}"
            ).get_attribute("type")
            if q_type == "1" or q_type == "2":  # 填空题
                vacant(driver, current, vacant_num)
                # 同时将vacant_num+1表示运行vacant函数时该使用texts参数的下一个值
                vacant_num += 1
            elif q_type == "3":  # 单选
                single(driver, current, single_num)
                # single_num+1表示运行single函数时该使用single_prob参数的下一个值
                single_num += 1
            elif q_type == "4":  # 多选
                multiple(driver, current, multiple_num)
                multiple_num += 1
            elif q_type == "5":  # 量表题
                scale(driver, current, scale_num)
                scale_num += 1
            elif q_type == "6":  # 矩阵题
                matrix_num = matrix(driver, current, matrix_num) # matrix_num 会在函数内部更新
            elif q_type == "7":  # 下拉框
                droplist(driver, current, droplist_num)
                droplist_num += 1
            elif q_type == "8":  # 滑块题
                score = random.randint(1, 100)
                driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(score)
            elif q_type == "11":  # 排序题
                reorder(driver, current, reorder_num)  # >>>>> 修改：传入 reorder_num <<<<<
                reorder_num += 1  # >>>>> 新增：递增计数器 <<<<<
            else:
                print(f"警告：第{current}题为不支持题型（类型：{q_type}），将跳过。")
        time.sleep(0.5)
        #  一页结束过后要么点击下一页，要么点击提交
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "#divNext")
            if next_button.is_displayed() and next_button.is_enabled():
                next_button.click()  # 点击下一页
                time.sleep(0.5)
            else: # 如果没有下一页按钮，尝试点击提交
                driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
        except:
            # 点击提交 (这是最后一页的情况)
            try:
                driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
            except Exception as e:
                print(f"尝试点击提交按钮失败: {e}")
    submit(driver)


# 提交函数
def submit(driver: WebDriver):
    time.sleep(1)
    # 点击对话框的确认按钮 (例如问卷星的“温馨提示”框)
    try:
        confirm_button = driver.find_element(By.XPATH, '//*[@id="layui-layer1"]/div[3]/a')
        if confirm_button.is_displayed() and confirm_button.is_enabled():
            confirm_button.click()
            time.sleep(1)
    except:
        pass # 没有弹窗或点击失败则继续

    # 点击智能检测按钮 (例如验证码之前的安全检测)
    try:
        sm_button = driver.find_element(By.XPATH, '//*[@id="SM_BTN_1"]')
        if sm_button.is_displayed() and sm_button.is_enabled():
            sm_button.click()
            time.sleep(3) # 等待智能检测完成
    except:
        pass # 没有智能检测或点击失败则继续

    # 滑块验证
    try:
        slider = driver.find_element(By.XPATH, '//*[@id="nc_1__scale_text"]/span')
        sliderButton = driver.find_element(By.XPATH, '//*[@id="nc_1_n1z"]')
        if str(slider.text).startswith("请按住滑块"):
            width = slider.size.get("width")
            ActionChains(driver).drag_and_drop_by_offset(
                sliderButton, width, 0
            ).perform()
            time.sleep(2) # 给滑块验证留出反应时间
    except:
        pass # 没有滑块验证或操作失败则继续


def run(xx, yy):
    option = webdriver.ChromeOptions()
    option.add_experimental_option("excludeSwitches", ["enable-automation"])
    option.add_experimental_option("useAutomationExtension", False)
    global cur_num, cur_fail
    while cur_num < target_num:
        # 由于你不需要代理IP，此处 if use_ip: 的代码块将不会执行。
        if use_ip:
            ip = zanip()
            # 只有当zanip返回的IP有效时才添加代理
            if validate(ip):
                option.add_argument(f"--proxy-server={ip}")
            else:
                logging.warning("获取到的IP地址无效，将使用本机IP。")
                # 如果获取的IP无效，则不添加代理参数，继续使用本机IP
        
        driver = webdriver.Chrome(options=option)
        driver.set_window_size(550, 650)
        driver.set_window_position(x=xx, y=yy)
        
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            },
        )
        try:
            driver.get(url)
            url1 = driver.current_url  # 表示问卷链接
            brush(driver)
            # 刷完后给一定时间让页面跳转
            time.sleep(4)
            url2 = (
                driver.current_url
            )  # 表示问卷填写完成后跳转的链接，一旦跳转说明填写成功
            if url1 != url2:
                lock.acquire() # 锁定，防止多线程同时修改计数器
                cur_num += 1
                lock.release() # 解锁
                print(
                    f"已填写{cur_num}份 - 失败{cur_fail}次 - {time.strftime('%H:%M:%S', time.localtime(time.time()))} "
                )
                driver.quit()
            else:
                # 如果URL未跳转，可能填写失败，或者问卷没有跳转页
                logging.warning(f"问卷可能未成功提交 (URL未跳转)。当前URL: {url2}")
                raise Exception("URL未跳转，可能提交失败")
        except Exception as e:
            traceback.print_exc()
            lock.acquire()
            cur_fail += 1
            lock.release()
            print(
                "\033[42m",
                f"已失败{cur_fail}次,失败超过{int(fail_threshold)}次(左右)将强制停止",
                "\033[0m",
            )
            if cur_fail >= fail_threshold:  # 失败阈值
                logging.critical(
                    "失败次数过多，为防止耗尽ip余额，程序将强制停止，请检查代码是否正确"
                )
                global stop # 引入全局停止变量
                stop = True # 设置停止标志
                break # 退出当前线程的循环
            driver.quit()
        
        if stop: # 检查停止标志
            break


# 多线程执行run函数
if __name__ == "__main__":
    # 一个可以代刷问卷星的网站： http://sugarblack.top
    target_num = 20  # >>>>> 目标份数，你可以根据需要修改 <<<<<
    # 失败阈值，数值可自行修改为固定整数
    fail_threshold = target_num / 4 + 1
    cur_num = 0  # 已提交份数
    cur_fail = 0  # 已失败次数
    lock = threading.Lock()
    
    # >>>>> IP设置：你不需要代理IP，所以这里设置为 False <<<<<
    use_ip = True
    
    stop = False # 全局停止标志，用于控制所有线程的退出
    
    # 尽管use_ip为False，validate函数仍然会被调用，用于打印信息
    if use_ip and validate(zanip()): # 只有当use_ip为True并且zanip返回有效IP时才认为IP设置成功
        print("IP设置成功, 将使用代理ip填写")
    else:
        print("IP设置失败或你选择不使用代理IP, 将使用本机ip填写")
        use_ip = False # 再次强制设置为False，以防万一

    num_threads = 2  # >>>>> 窗口数量，你可以根据需要修改 <<<<<
    threads: list[Thread] = []
    # 创建并启动线程
    for i in range(num_threads):
        x = 50 + i * 60  # 浏览器弹窗左上角的横坐标
        y = 50  # 纵坐标
        thread = Thread(target=run, args=(x, y))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    if stop:
        print("\033[91m程序已因失败次数过多而强制停止。\033[0m")
    else:
        print("\033[92m所有问卷填写任务已完成！\033[0m")

"""
    总结,你需要修改的有: 1 问卷链接(必改)  2 目标份数(可选)  3 浏览器窗口数量(可选)
    所有题目的比例参数已根据你提供的模拟数据调整完毕。
    有疑问可以加qq群喔: 774326264 || 427847187 || 850281779 || 931614446; 
    虽然我不一定回hhh, 但是群友们不一定不回
    Presented by 鐘
"""