
### 问卷星自动填写脚本使用说明

本脚本用于自动化填写问卷星的问卷。

**使用步骤：**

1.  **环境准备：**
    *   确保你已安装 Python。
    *   安装所需库：打开命令行/终端，运行 `pip install -r requirements.txt`。
    *   （这一步可能不需要）下载与你的 Chrome 浏览器版本匹配的 ChromeDriver：[https://googlechromelabs.github.io/chrome-for-testing/](https://googlechromelabs.github.io/chrome-for-testing/)
    *   （这一步可能不需要）将下载的 `chromedriver.exe` (Windows) 或 `chromedriver` (macOS/Linux) 文件放到 Python 的安装目录，或者一个你知道的路径，并确保该路径在系统的环境变量 `PATH` 中。

2.  **配置脚本 (`say_goodbye_to_wjx.py`)：**
    打开 `say_goodbye_to_wjx.py` 文件，找到并修改以下参数部分：

    *   **`url` (必需)：**
        ```python
        url = "https://www.wjx.cn/vm/YOUR_SURVEY_ID.aspx#" # 将 YOUR_SURVEY_ID 替换为你的问卷实际ID
        ```

    *   **`single_prob`, `multiple_prob`, `droplist_prob`, `matrix_prob`, `scale_prob` (必需，根据问卷题目类型填写)：**
        这些参数控制每个问题选项的选择概率。你需要根据你的问卷结构和期望的数据分布来配置它们。
        *   键 (如 `"1"`, `"2"`) 只是注释，重要的是值的顺序和数量。
        *   单选、矩阵、量表、下拉框：使用比例值，如 `[70, 30]` 表示选项A占70%，选项B占30%。
        *   多选题：每个选项的独立选择概率 (0-100)，如 `[80, 50, 20]` 表示选项A有80%概率被选，B有50%，C有20%。
        *   `-1` 表示随机选择该题的某个选项。
        *   **非常重要：** 每个概率列表的长度必须与对应题目在问卷中的实际选项数量完全一致！

    *   **`texts`, `texts_prob` (如果问卷有填空题)：**
        设置填空题的预设答案和它们被选中的概率。

    *   **`reorder_prob` (如果问卷有排序题)：**
        ```python
        reorder_prob = {
            "1": { # "1" 表示这是脚本遇到的第1个排序题
                'options_weights': { 'A': 80, 'B': 78, ... }, # 各选项被选入排序的总次数/权重
                'first_place_weights': { 'A': 35, 'B': 30, ... }, # 各选项排在第一位的次数/权重
                'num_to_select': 3 # 这道排序题需要选择并排序几项
            }
        }
        ```
        你需要根据你的排序题选项和期望的排序逻辑来配置。

    *   **运行参数 (可选修改)：**
        ```python
        target_num = 10       # 期望填写的问卷总份数
        num_threads = 2       # 同时打开多少个浏览器窗口进行填写
        use_ip = False        # 是否使用代理IP (True 或 False)
        ```

    *   **代理IP设置 (如果 `use_ip = True`)：**
        如果你需要使用代理IP，请修改 `zanip()` 函数中的 `api` 变量为你自己的IP代理服务API链接。并确保你的电脑公网IP已在代理服务商处加入白名单。
        ```python
        def zanip():
            api = "在此处粘贴你的IP代理API链接"
            # ...
        ```
        如果不需要代理，保持 `use_ip = False` 即可。

3.  **运行脚本：**
    保存你的修改后，在命令行/终端中，导航到 `say_goodbye_to_wjx.py` 文件所在的目录，然后运行：
    `python say_goodbye_to_wjx.py`

## 示例问卷说明
这是我的习概课的调查问卷，py文件中的参数就是按照链接中的问卷所设置的
[查看问卷](https://www.wjx.cn/vm/wFPBGut.aspx#)
