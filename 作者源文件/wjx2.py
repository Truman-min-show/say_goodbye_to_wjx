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
    greasyfork地址：https://greasyfork.org/zh-CN/scripts/466722-%E9%97%AE%E5%8D%B7%E6%98%9F%E8%84%9A%E6%9C%AC
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
    api = "https://service.ipzan.com/core-extract?num=1&no=???&minute=1&area=all&pool=quality&secret=???"
    ip = requests.get(api).text
    return ip


# 示例问卷,试运行结束后,需要改成你的问卷地址
# 一个可以代刷问卷星的网站： http://sugarblack.top
url = "https://www.wjx.cn/vm/*******.aspx#"

"""
单选题概率参数，"1"表示第一题，0表示不选， [30, 70]表示3:7，-1表示随机
在示例问卷中，第一题有三个选项，"1"后面的概率参数也应该设置三个值才对，否则会报错！！！
同时，题号其实不重要，只是为了填写概率值时方便记录我才加上去的，这个字典在真正使用前会转化为一个列表；（这一行没看懂没关系，下面一行懂了就行）
最重要的其实是保证single_prob的第n个参数对应第n个单选题，比如在示例问卷中第5题是滑块题，但是我single_prob却有“第5题”，因为这个"5"其实对应的是第5个单选题，也就是问卷中的第6题
这个single_prob的"5"可以改成其他任何值，当然我不建议你这么干，因为问卷中只有5个单选题，所以第6个单选题的参数其实是没有用上的，参数只能多不能少！！！（这一点其他类型的概率参数也适用）
"""
single_prob = {
    "1": [1, 1, 0],
    "2": -1,
    "3": -1,
    "4": -1,
    "5": -1,
    "6": [1, 0],
}

# 下拉框参数，具体含义参考单选题，如果没有下拉框题也不要删，就让他躺在这儿吧，其他题也是哦，没有就不动他，别删，只改你有的题型的参数就好啦
droplist_prob = {"1": [2, 1, 1]}

# 此参数和视频演示不一致！！
# 表示每个选项选择的概率，100表示必选，30表示选择B的概率为30；不能写[1,1,1,1]这种比例了，不然含义为选ABCD的概率均为1%
# 最好保证概率和加起来大于100
multiple_prob = {"9": [100, 30, 23, 43]}
# multiple_opts = {"9": 1, }   此参数已失效，可不必理会2024.3.28

# 矩阵题概率参数,-1表示随机，其他含义参考单选题；同样的，题号不重要，保证第几个参数对应第几个矩阵小题就可以了；
# 在示例问卷中矩阵题是第10题，每个小题都要设置概率值才行！！以下参数表示第二题随机，其余题全选A
matrix_prob = {
    "1": [1, 0, 0, 0, 0],
    "2": -1,
    "3": [1, 0, 0, 0, 0],
    "4": [1, 0, 0, 0, 0],
    "5": [1, 0, 0, 0, 0],
    "6": [1, 0, 0, 0, 0],
}

# 量表题概率参数，参考单选题
scale_prob = {"7": [0, 2, 3, 4, 1], "12": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]}

# 填空题参数，在题号后面按该格式填写需要填写的内容，
texts = {
    "8": ["内容1", "内容2", " 内容3"],
}
# 每个内容对应的概率1:1:1,
texts_prob = {"8": [1, 1, 1]}

# 排序题不支持设置参数，如果有排序题程序会自动处理
# 滑块题没支持参数，程序能自动处理部分滑块题

# --------------到此为止，参数设置完毕，可以直接运行啦！-------------------
# 如果需要设置浏览器窗口数量，请转到最后一个函数(main函数)，注意看里面的注释喔！


# 参数归一化，把概率值按比例缩放到概率值和为1，比如某个单选题[1,2,3,4]会被转化成[0.1,0.2,0.3,0.4],[1,1]会转化成[0.5,0.5]
for prob in [single_prob, matrix_prob, droplist_prob, scale_prob, texts_prob]:
    for key in prob:
        if isinstance(prob[key], list):
            prob_sum = sum(prob[key])
            prob[key] = [x / prob_sum for x in prob[key]]

# 转化为列表,去除题号
single_prob = list(single_prob.values())
droplist_prob = list(droplist_prob.values())
multiple_prob = list(multiple_prob.values())
matrix_prob = list(matrix_prob.values())
scale_prob = list(scale_prob.values())
texts_prob = list(texts_prob.values())
texts = list(texts.values())

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
    content = texts[index]
    # 对应填空题概率参数
    p = texts_prob[index]
    text_index = numpy.random.choice(a=numpy.arange(0, len(p)), p=p)
    driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(content[text_index])


# 单选题处理函数
def single(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div'
    a = driver.find_elements(By.XPATH, xpath)
    p = single_prob[index]
    if p == -1:
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
    p = multiple_prob[index]
    assert len(options) == len(p), f"第{current}题概率值和选项值不一致"
    # 生成序列,同时保证至少有一个1
    while sum(mul_list) <= 1:
        mul_list = []
        for item in p:
            a = numpy.random.choice(
                a=numpy.arange(0, 2), p=[1 - (item / 100), item / 100]
            )
            mul_list.append(a)
    # 依次点击
    for index, item in enumerate(mul_list):
        if item == 1:
            css = f"#div{current} > div.ui-controlgroup > div:nth-child({index + 1})"
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
        p = matrix_prob[index]
        index += 1
        if p == -1:
            opt = random.randint(2, len(b))
        else:
            opt = numpy.random.choice(a=numpy.arange(2, len(b) + 1), p=p)
        driver.find_element(
            By.CSS_SELECTOR, f"#drv{current}_{i} > td:nth-child({opt})"
        ).click()
    return index


# 排序题处理函数，排序暂时只能随机
def reorder(driver: WebDriver, current):
    xpath = f'//*[@id="div{current}"]/ul/li'
    a = driver.find_elements(By.XPATH, xpath)
    for j in range(1, len(a) + 1):
        b = random.randint(j, len(a))
        driver.find_element(
            By.CSS_SELECTOR, f"#div{current} > ul > li:nth-child({b})"
        ).click()
        time.sleep(0.4)


# 量表题处理函数
def scale(driver: WebDriver, current, index):
    xpath = f'//*[@id="div{current}"]/div[2]/div/ul/li'
    a = driver.find_elements(By.XPATH, xpath)
    p = scale_prob[index]
    if p == -1:
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
                matrix_num = matrix(driver, current, matrix_num)
            elif q_type == "7":  # 下拉框
                droplist(driver, current, droplist_num)
                droplist_num += 1
            elif q_type == "8":  # 滑块题
                score = random.randint(1, 100)
                driver.find_element(By.CSS_SELECTOR, f"#q{current}").send_keys(score)
            elif q_type == "11":  # 排序题
                reorder(driver, current)
            else:
                print(f"第{k}题为不支持题型！")
        time.sleep(0.5)
        #  一页结束过后要么点击下一页，要么点击提交
        try:
            driver.find_element(By.CSS_SELECTOR, "#divNext").click()  # 点击下一页
            time.sleep(0.5)
        except:
            # 点击提交
            driver.find_element(By.XPATH, '//*[@id="ctlNext"]').click()
    submit(driver)


# 提交函数
def submit(driver: WebDriver):
    time.sleep(1)
    # 点击对话框的确认按钮
    try:
        driver.find_element(By.XPATH, '//*[@id="layui-layer1"]/div[3]/a').click()
        time.sleep(1)
    except:
        pass
    # 点击智能检测按钮，因为可能点击提交过后直接提交成功的情况，所以智能检测也要try
    try:
        driver.find_element(By.XPATH, '//*[@id="SM_BTN_1"]').click()
        time.sleep(3)
    except:
        pass
    # 滑块验证
    try:
        slider = driver.find_element(By.XPATH, '//*[@id="nc_1__scale_text"]/span')
        sliderButton = driver.find_element(By.XPATH, '//*[@id="nc_1_n1z"]')
        if str(slider.text).startswith("请按住滑块"):
            width = slider.size.get("width")
            ActionChains(driver).drag_and_drop_by_offset(
                sliderButton, width, 0
            ).perform()
    except:
        pass


def run(xx, yy):
    option = webdriver.ChromeOptions()
    option.add_experimental_option("excludeSwitches", ["enable-automation"])
    option.add_experimental_option("useAutomationExtension", False)
    global cur_num, cur_fail
    while cur_num < target_num:
        if use_ip:
            ip = zanip()
            option.add_argument(f"--proxy-server={ip}")
        driver = webdriver.Chrome(options=option)
        driver.set_window_size(550, 650)
        driver.set_window_position(x=xx, y=yy)
        # 有学过 vue2 的吗, Object.defineProperty 这个 api 是不是很眼熟啊哈哈哈
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
                cur_num += 1
                print(
                    f"已填写{cur_num}份 - 失败{cur_fail}次 - {time.strftime('%H:%M:%S', time.localtime(time.time()))} "
                )
                driver.quit()
        except:
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
                quit()
            driver.quit()
            continue


# 多线程执行run函数
if __name__ == "__main__":
    # 一个可以代刷问卷星的网站： http://sugarblack.top
    target_num = 3  # 目标份数
    # 失败阈值，数值可自行修改为固定整数
    fail_threshold = target_num / 4 + 1
    cur_num = 0  # 已提交份数
    cur_fail = 0  # 已失败次数
    lock = threading.Lock()
    use_ip = False
    stop = False
    if validate(zanip()):
        print("IP设置成功, 将使用代理ip填写")
        use_ip = True
    else:
        print("IP设置失败, 将使用本机ip填写")
    num_threads = 2  # 窗口数量
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

"""
    总结,你需要修改的有: 1 每个题的比例参数(必改)  2 问卷链接(必改)  3 ip链接(可选)  4 浏览器窗口数量(可选)
    有疑问可以加qq群喔: 774326264 || 427847187 || 850281779 || 931614446; 
    虽然我不一定回hhh, 但是群友们不一定不回
    Presented by 鐘
"""
