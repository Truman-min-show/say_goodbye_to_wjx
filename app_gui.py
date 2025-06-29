# app_gui.py

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import json
from survey_engine import SurveyRunner  # 导入我们的核心引擎


class BaseDynamicFrame(ttk.Frame):
    """所有动态列表的基础框架，只负责提供容器和通用的删除/重绘逻辑"""

    # 在 BaseDynamicFrame 类中，用此版本替换旧的 __init__ 方法
    def __init__(self, parent, title, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.row_widgets = []

        # --- UI设置部分 ---
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # --- 核心修复：更健壮的事件绑定逻辑 ---

        # 1. 定义滚轮事件的处理函数
        def _on_mousewheel(event):
            # 根据不同平台的事件差异，计算滚动的单位
            if event.num == 5 or event.delta < 0:
                self.canvas.yview_scroll(1, "units")
            if event.num == 4 or event.delta > 0:
                self.canvas.yview_scroll(-1, "units")

        # 2. 定义一个函数，用来将滚轮事件绑定到窗口上
        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.canvas.bind_all("<Button-4>", _on_mousewheel)
            self.canvas.bind_all("<Button-5>", _on_mousewheel)

        # 3. 定义一个函数，用来解除绑定
        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

        # 4. 当鼠标进入Canvas或其内部的Frame时，绑定事件
        self.canvas.bind('<Enter>', _bind_to_mousewheel)
        self.scrollable_frame.bind('<Enter>', _bind_to_mousewheel)
        # 当鼠标离开时，解除绑定
        self.canvas.bind('<Leave>', _unbind_from_mousewheel)
        self.scrollable_frame.bind('<Leave>', _unbind_from_mousewheel)

        # --- 界面布局部分（保持不变）---
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 5))
        ttk.Label(header, text=title, font=("", 10, "bold")).pack(side="left")
        ttk.Button(header, text="添加", command=lambda: self.add_row()).pack(side="right")
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件，滚动Canvas"""
        # 根据不同平台的事件差异，计算滚动的单位
        # 在Windows上，event.delta通常是120的倍数
        # 在Linux上，event.num是4或5
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    def add_row(self, restored_data=None):
        # 这个方法将由子类具体实现
        raise NotImplementedError

    def get_all_data(self):
        # 这个方法将由子类具体实现
        raise NotImplementedError

    def remove_row(self, index):
        """通用的删除和重绘逻辑"""
        if not (0 <= index < len(self.row_widgets)): return

        all_data = self.get_all_data()
        if 0 <= index < len(all_data):
            all_data.pop(index)

        for widget_info in self.row_widgets:
            widget_info['frame'].destroy()
        self.row_widgets = []

        for data_dict in all_data:
            self.add_row(restored_data=data_dict)


class DynamicListFrame(BaseDynamicFrame):
    """用于单选、多选、矩阵、量表题的UI框架"""

    def __init__(self, parent, title, fields, *args, **kwargs):
        # fields 参数在这里不再需要，但保留以兼容旧的调用方式
        super().__init__(parent, title, *args, **kwargs)

    def add_row(self, restored_data=None):
        row_index = len(self.row_widgets)
        container = ttk.LabelFrame(self.scrollable_frame, text=f"题目 {row_index + 1}")
        container.pack(fill="x", expand=True, pady=5, padx=5)

        top_frame = ttk.Frame(container)
        top_frame.pack(fill="x", pady=2)
        options_frame = ttk.Frame(container)
        options_frame.pack(fill="x", pady=2)

        ttk.Label(top_frame, text="选项数量:").pack(side="left")

        initial_num = restored_data['num_options'] if restored_data else 4
        num_var = tk.StringVar(value=str(initial_num))

        option_vars = []

        def _update_options():
            nonlocal option_vars
            for widget in options_frame.winfo_children():
                widget.destroy()

            try:
                num = int(num_var.get())
            except ValueError:
                num = 0

            new_vars = []
            restored_values = restored_data['values'] if restored_data and len(restored_data['values']) == num else [
                                                                                                                        ''] * num

            for i in range(num):
                opt_frame = ttk.Frame(options_frame)
                opt_frame.grid(row=i // 5, column=i % 5, sticky='w', padx=5, pady=1)
                ttk.Label(opt_frame, text=f"选项 {i + 1}:").pack(side="left")
                entry_var = tk.StringVar(value=str(restored_values[i]))
                ttk.Entry(opt_frame, textvariable=entry_var, width=10).pack(side="left")
                new_vars.append(entry_var)
            option_vars = new_vars

        spinbox_cmd = lambda event=None: _update_options()
        spinbox = ttk.Spinbox(top_frame, from_=1, to=50, textvariable=num_var, width=5, command=spinbox_cmd)
        spinbox.bind("<Return>", spinbox_cmd)
        spinbox.bind("<FocusOut>", spinbox_cmd)
        spinbox.pack(side="left", padx=5)

        ttk.Button(top_frame, text="删除", command=lambda idx=row_index: self.remove_row(idx)).pack(side="right")

        _update_options()  # 初始创建

        self.row_widgets.append({'frame': container, 'num_var': num_var, 'get_option_vars': lambda: option_vars})

    def get_all_data(self):
        all_data = []
        for row in self.row_widgets:
            num = int(row['num_var'].get())
            vals = [var.get() for var in row['get_option_vars']()]
            all_data.append({'num_options': num, 'values': vals})
        return all_data


class TextQuestionFrame(BaseDynamicFrame):
    """为填空题定制的专用UI框架"""

    def __init__(self, parent, title, fields, *args, **kwargs):
        super().__init__(parent, title, *args, **kwargs)

    def add_row(self, restored_data=None):
        row_index = len(self.row_widgets)
        container = ttk.LabelFrame(self.scrollable_frame, text=f"题目 {row_index + 1}")
        container.pack(fill="x", expand=True, pady=5, padx=5)

        content_var = tk.StringVar()
        prob_var = tk.StringVar()

        if restored_data:
            content_var.set(restored_data.get('内容', ''))
            prob_var.set(restored_data.get('概率', ''))

        f1 = ttk.Frame(container)
        f1.pack(fill='x', expand=True, padx=5, pady=2)
        ttk.Label(f1, text="可选内容 (用,分隔):").pack(side="left")
        ttk.Entry(f1, textvariable=content_var, width=50).pack(side="left", fill='x', expand=True)

        f2 = ttk.Frame(container)
        f2.pack(fill='x', expand=True, padx=5, pady=2)
        ttk.Label(f2, text="对应概率 (用,分隔):").pack(side="left")
        ttk.Entry(f2, textvariable=prob_var, width=50).pack(side="left", fill='x', expand=True)

        ttk.Button(container, text="删除", command=lambda idx=row_index: self.remove_row(idx)).pack(side="right",
                                                                                                    pady=5)

        self.row_widgets.append({'frame': container, 'vars': {'内容': content_var, '概率': prob_var}})

    def get_all_data(self):
        return [{'内容': r['vars']['内容'].get(), '概率': r['vars']['概率'].get()} for r in self.row_widgets]


class ReorderQuestionFrame(BaseDynamicFrame):
    """为排序题定制的专用UI框架"""

    def __init__(self, parent, title, fields, *args, **kwargs):
        super().__init__(parent, title, *args, **kwargs)

    def add_row(self, restored_data=None):
        row_index = len(self.row_widgets)
        container = ttk.LabelFrame(self.scrollable_frame, text=f"题目 {row_index + 1}")
        container.pack(fill="x", expand=True, pady=5, padx=5)

        vars_dict = {
            '选项权重': tk.StringVar(),
            '首位权重': tk.StringVar(),
            '选择数量': tk.StringVar(value="3")
        }
        if restored_data:
            for key, var in vars_dict.items():
                var.set(restored_data.get(key, ''))

        for key, var in vars_dict.items():
            frame = ttk.Frame(container)
            frame.pack(fill='x', expand=True, padx=5, pady=2)
            ttk.Label(frame, text=f"{key} (格式 A:80,B:75):" if key != '选择数量' else f"{key}:").pack(side="left")
            ttk.Entry(frame, textvariable=var, width=50 if key != '选择数量' else 10).pack(side="left",
                                                                                           fill='x' if key != '选择数量' else 'none',
                                                                                           expand=True if key != '选择数量' else False)

        ttk.Button(container, text="删除", command=lambda idx=row_index: self.remove_row(idx)).pack(side="right",
                                                                                                    pady=5)

        self.row_widgets.append({'frame': container, 'vars': vars_dict})

    def get_all_data(self):
        return [{key: var.get() for key, var in r['vars'].items()} for r in self.row_widgets]


class SurveyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("问卷星助手")
        self.root.geometry("800x650")

        self.log_queue = queue.Queue()
        self.engine_thread = None
        self.question_frames = {}

        main_config_frame = ttk.LabelFrame(self.root, text="主配置", padding=10)
        main_config_frame.pack(fill="x", padx=10, pady=5)

        # 创建一个垂直方向的、可拖动的窗格
        paned_window = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned_window.pack(fill="both", expand=True, padx=10, pady=5)

        question_config_frame = ttk.LabelFrame(paned_window, text="题目配置", padding=10)
        # 使用 .add() 方法将框架放入窗格，weight=1表示它会获得更多的初始空间
        paned_window.add(question_config_frame, weight=7)

        control_log_frame = ttk.LabelFrame(paned_window, text="控制与日志", padding=10)
        paned_window.add(control_log_frame, weight=3)

        self.setup_main_config_widgets(main_config_frame)
        self.setup_question_config_widgets(question_config_frame)
        self.setup_control_log_widgets(control_log_frame)

        self.update_log_widget()  # 启动日志更新循环

    def setup_main_config_widgets(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="问卷链接:").grid(row=0, column=0, sticky="w", pady=2)
        self.url_var = tk.StringVar()
        ttk.Entry(parent_frame, textvariable=self.url_var).grid(row=0, column=1, sticky="ew")

        sub_frame = ttk.Frame(parent_frame)
        sub_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Label(sub_frame, text="目标份数:").pack(side="left")
        self.target_num_var = tk.StringVar(value="10")
        ttk.Spinbox(sub_frame, from_=1, to=1000, textvariable=self.target_num_var, width=8).pack(side="left",
                                                                                                 padx=(0, 20))
        ttk.Label(sub_frame, text="并发数量:").pack(side="left")
        self.num_threads_var = tk.StringVar(value="2")
        ttk.Spinbox(sub_frame, from_=1, to=20, textvariable=self.num_threads_var, width=8).pack(side="left")

        self.use_ip_var = tk.BooleanVar(value=False)
        ip_checkbutton = ttk.Checkbutton(parent_frame, text="使用代理IP", variable=self.use_ip_var,
                                         command=self.toggle_ip_entry)
        ip_checkbutton.grid(row=2, column=0, sticky="w", pady=2)
        self.ip_api_url_var = tk.StringVar()
        self.ip_api_entry = ttk.Entry(parent_frame, textvariable=self.ip_api_url_var, state="disabled")
        self.ip_api_entry.grid(row=2, column=1, sticky="ew")

        help_button = ttk.Button(parent_frame, text="使用说明", command=self.show_help_window)
        help_button.grid(row=0, column=2, sticky='e', padx=(10, 0))

    def toggle_ip_entry(self):
        self.ip_api_entry.config(state="normal" if self.use_ip_var.get() else "disabled")

    def _parse_user_input(self, input_str: str):
        """
                智能解析用户输入的字符串。
                - 如果包含冒号':'，则尝试解析为字典。
                - 否则，尝试解析为列表。
                - 自动处理数字和字符串。
                """
        input_str = input_str.strip()
        if not input_str:
            return {} if ':' in input_str else []

        if ':' in input_str:
            # 解析为字典
            result_dict = {}
            pairs = input_str.split(',')
            for pair in pairs:
                if ':' in pair:
                    key, val = pair.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    try:
                        # 尝试将值转为数字
                        result_dict[key] = int(val) if val.isdigit() else float(val)
                    except ValueError:
                        # 如果失败，则保留为字符串
                        result_dict[key] = val
            return result_dict
        else:
            # 解析为列表
            result_list = []
            items = input_str.split(',')
            for item in items:
                item = item.strip()
                try:
                    result_list.append(int(item) if item.isdigit() else float(item))
                except ValueError:
                    result_list.append(item)
            return result_list

        # 在 SurveyApp 类中，用此版本替换旧的 setup_question_config_widgets 方法

    def setup_question_config_widgets(self, parent_frame):
        """创建题目配置区域的控件 (为特殊题型加载专用UI)"""
        notebook = ttk.Notebook(parent_frame)
        notebook.pack(fill="both", expand=True)

        # 定义所有题型及其对应的UI类和字段
        configs = {
            "single_prob": ("单选题", DynamicListFrame, {"概率": 60}),
            "multiple_prob": ("多选题", DynamicListFrame, {"概率": 60}),
            "matrix_prob": ("矩阵题", DynamicListFrame, {"概率": 60}),
            "scale_prob": ("量表题", DynamicListFrame, {"概率": 60}),
            "texts": ("填空题", TextQuestionFrame, {}),  # 特殊UI，fields为空
            "reorder_prob": ("排序题", ReorderQuestionFrame, {})  # 特殊UI，fields为空
        }

        for key, (title, FrameClass, fields) in configs.items():
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=title)
            # 根据配置，实例化正确的UI类
            self.question_frames[key] = FrameClass(tab, f"{title}列表", fields)
            self.question_frames[key].pack(fill="both", expand=True, padx=5, pady=5)

    def setup_control_log_widgets(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=0)

        self.log_text = scrolledtext.ScrolledText(parent_frame, height=10, state="disabled", wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        button_frame = ttk.Frame(parent_frame)
        button_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        self.start_button = ttk.Button(button_frame, text="开始任务", command=self.start_task)
        self.start_button.pack(fill="x", pady=5)
        self.stop_button = ttk.Button(button_frame, text="停止任务", state="disabled", command=self.stop_task)
        self.stop_button.pack(fill="x")

    def update_log_widget(self):
        """从队列中获取日志并更新到文本框中"""
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.config(state="disabled")
            self.log_text.see(tk.END)  # 滚动到底部
        self.root.after(100, self.update_log_widget)

    def log_to_queue(self, message):
        """将消息放入队列，此函数可被其他线程安全调用"""
        self.log_queue.put(message)

    def start_task(self):
        """收集配置并启动后台线程执行任务"""
        try:
            config = self.collect_config()
        except Exception as e:
            messagebox.showerror("配置错误", f"读取配置失败: {e}")
            return

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)  # 清空日志
        self.log_text.config(state="disabled")

        self.engine_thread = threading.Thread(target=self.run_engine_thread, args=(config,), daemon=True)
        self.engine_thread.start()

    def run_engine_thread(self, config):
        """在线程中运行引擎，任务结束后恢复按钮状态"""
        try:
            self.engine = SurveyRunner(config, output_callback=self.log_to_queue)
            self.engine.start()
        except Exception as e:
            self.log_to_queue(f"!!! 引擎发生严重错误: {e}")
        finally:
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")

    def stop_task(self):
        """停止正在运行的任务"""
        if self.engine_thread and self.engine_thread.is_alive():
            self.log_to_queue(">>> 正在发送停止信号... <<<")
            self.engine.stop_flag = True
            self.stop_button.config(state="disabled")

        # 用此版本替换原来的 collect_config 方法

    """
    def collect_config(self):
        # 从UI控件收集所有配置信息（使用新的解析方式）
        config = {
            "url": self.url_var.get(),
            "target_num": int(self.target_num_var.get()),
            "num_threads": int(self.num_threads_var.get()),
            "use_ip": self.use_ip_var.get(),
            "ip_api_url": self.ip_api_url_var.get(),
        }

        # 从动态列表中收集题目配置
        for key, frame in self.question_frames.items():
            data_list = frame.get_all_data()
            prob_dict = {}
            for i, data_row in enumerate(data_list):
                # 使用我们新的、更智能的解析函数
                if key == 'texts':
                    if 'texts_prob' not in config: config['texts_prob'] = {}
                    # 填空题有两个输入框，分别解析
                    prob_dict[str(i + 1)] = self._parse_user_input(data_row.get('内容', ''))
                    config['texts_prob'][str(i + 1)] = self._parse_user_input(data_row.get('概率', ''))
                elif key == 'reorder_prob':
                    prob_dict[str(i + 1)] = {
                        'options_weights': self._parse_user_input(data_row.get('选项权重', '')),
                        'first_place_weights': self._parse_user_input(data_row.get('首位权重', '')),
                        'num_to_select': int(data_row.get('选择数量', '0'))
                    }
                else:  # 单选、多选、矩阵、量表
                    prob_dict[str(i + 1)] = self._parse_user_input(data_row.get('概率', ''))

            config[key] = prob_dict

        return config
    """

    # 在 SurveyApp 类中，用此版本替换旧的 collect_config 方法
    def collect_config(self):
        """从UI控件收集所有配置信息（适配所有新UI）"""
        config = {
            "url": self.url_var.get(),
            "target_num": int(self.target_num_var.get()),
            "num_threads": int(self.num_threads_var.get()),
            "use_ip": self.use_ip_var.get(),
            "ip_api_url": self.ip_api_url_var.get(),
        }

        # 从动态列表中收集题目配置
        for key, frame in self.question_frames.items():
            data_list = frame.get_all_data()
            prob_dict = {}

            if key == 'texts':
                if 'texts_prob' not in config: config['texts_prob'] = {}
                contents_dict = {}
                probs_dict = {}
                for i, data_row in enumerate(data_list):
                    contents_dict[str(i + 1)] = self._parse_user_input(data_row.get('内容', ''))
                    probs_dict[str(i + 1)] = self._parse_user_input(data_row.get('概率', ''))
                config['texts'] = contents_dict
                config['texts_prob'] = probs_dict
                continue  # 处理完填空题，跳过后续通用逻辑

            if key == 'reorder_prob':
                for i, data_row in enumerate(data_list):
                    prob_dict[str(i + 1)] = {
                        'options_weights': self._parse_user_input(data_row.get('选项权重', '')),
                        'first_place_weights': self._parse_user_input(data_row.get('首位权重', '')),
                        'num_to_select': int(data_row.get('选择数量', '0'))
                    }
                config[key] = prob_dict
                continue  # 处理完排序题，跳过后续通用逻辑

            # --- 核心修复：处理通用列表类题型 (单选, 多选等) ---
            prob_dict = {}
            for i, data_dict in enumerate(data_list):
                # 1. 从数据结构中提取 'values' 列表
                str_values = data_dict.get('values', [])

                # 2. 将字符串列表转换为数字列表
                num_values = []
                for val in str_values:
                    if val.strip():  # 只处理非空字符串
                        try:
                            # 尝试转换为浮点数，以支持小数
                            num_values.append(float(val))
                        except ValueError:
                            # 如果转换失败（例如用户输入了文本），则忽略该值
                            self.log_to_queue(f"警告：在 {key} 题目 {i + 1} 中发现非数字值 '{val}'，已忽略。")
                            pass

                prob_dict[str(i + 1)] = num_values

            config[key] = prob_dict

        return config

    # 在 SurveyApp 类的末尾，用此版本替换旧的 show_help_window 方法
    def show_help_window(self):
        """创建一个弹出窗口来显示详细的使用说明"""
        help_win = tk.Toplevel(self.root)
        help_win.title("使用说明 (详细版)")
        help_win.geometry("750x650")  # 窗口可以再大一些以容纳更多内容
        help_win.transient(self.root)
        help_win.grab_set()

        help_text_widget = scrolledtext.ScrolledText(help_win, wrap=tk.WORD, padx=10, pady=10, font=("", 10))
        help_text_widget.pack(fill="both", expand=True)

        # --- 新版详细使用说明内容 ---
        help_content = """
    欢迎使用问卷星助手！本工具可以帮助您根据预设的概率自动填写问卷，节省您大量的时间和精力。

    --- 必读：重要提示 ---

    ▶ 关于题目顺序
    题目配置中的“题目1”, “题目2”...指的是该【类型】下的第几个题目，而非问卷上的总题号。
    对于矩阵单选题则是所有大题按顺序排布的某一个小题。
    例如：“单选题”选项卡下的“题目2”指的是脚本在问卷中遇到的【第二个单选题】，它在问卷上的实际题号可能是Q5或Q8等。
         “若第一个矩阵单选题有3个小题，则矩阵单选题”选项卡下的“题目5”指的是脚本在问卷中遇到的【第二个矩阵单选题的第二个小题】。

    ▶ 关于跳题逻辑
    本脚本目前【无法处理】问卷中的跳题逻辑（即根据某一题的答案显示或隐藏后续题目）。请确保您的问卷是按固定顺序从头到尾填写的，否则脚本可能会出错或提交失败。
    
    ▶ 关于题目配置
    若您配置的选项数量或是题目数量与所填的问卷的实际内容不匹配，程序将在不匹配的题目上进行随机选择，对于填空题则填写“随机文本x”,x为一个随机数。
    
    --- 主配置区 ---

    - 问卷链接: 粘贴您的问卷星问卷URL。
    - 目标份数: 您希望总共提交多少份问卷。
    - 并发数量: 同时打开多少个浏览器窗口进行填写（建议不要超过CPU核心数）。
    - 使用代理IP: 勾选此项可通过代理IP提交，避免IP限制。

    --- 如何获取代理IP链接？ ---

    如果您需要使用代理IP，可以借助第三方IP代理服务。以下以“品赞IP”为例：
    1. 前往其官网 (ipzan.com) 并注册账号（通常需要实名认证）。
    2. 将您电脑的公网IP地址添加到网站的“IP白名单”中，注意您的公网IP的出口可能不止一个，需要全部添加进白名单。
    3. 在网站上生成API链接，建议选择以下配置：
       - 地区：任意
       - 时长：1分钟
       - 数据格式：txt
       - 提取数量：1
    4. 将生成好的API链接完整地粘贴到本程序的“代理API链接”输入框中。

    --- 题目配置与输入格式示例 ---

    请在下方对应的选项卡中，点击“添加”按钮来配置每个题目。
    选项的概率是按照选项顺序排布的，所以编辑问卷时请不要使用“自动打乱选项顺序”功能

    ▶ 列表类 (单选/多选/矩阵单选/量表/填空内容/填空概率)
       说明：请首先输入选项数量，随后依次填入各选项概率。程序会自动识别数字和文本。
       - 单选题/量表题概率: 80,15,5
         (代表三个选项的选中概率比为80:15:5,这里不一定和为100,程序可以自动归一化)
       - 矩阵单选题概率: 100,0,0,0
         (注意：矩阵单选题的每个【小题】都需要单独添加一行配置。例如，一个有3个小题的矩阵单选题，需要在此选项卡下点击“添加”3次，并分别为这3个小题填写概率)
       - 多选题概率: 80,50,100
         (代表选项A有80%概率被选，B有50%，C有100%(必选))

    ▶ 字典类 (填空题/排序题)
       填空题说明：格式为"内容1,内容2"以及"内容1的概率比,内容2的概率比"，每个之间用英文逗号 (,) 分隔。
         - 填空题内容: 本科, 硕士, 博士
         - 填空题概率: 60,30,10
         (需与上方“内容”一一对应,填空填写三个学历的概率分别为60%,30%,10%,概率也可自动归一化)
       排序题说明：格式为“键:值”，每对之间用英文逗号 (,) 分隔。
         - 选项权重: A:80,B:75,C:50
         (代表A、B、C这几个选项被【选入排序】的总概率比，A,B,C只是一个标签，用于确定首位权重)
         - 首位权重: A:60, B:40
         (在被选中的选项里，A排在【第一位】的概率比B高)
         - 选择数量: 3
         (代表这道排序题总共需要选择并排序3个选项，该值应该小于等于选项权重中概率非零选项的个数)

    --- 控制与日志 ---

    - 开始任务: 根据当前所有配置启动自动化任务。
    - 停止任务: 向正在运行的任务发送停止信号，任务会在完成当前问卷后安全退出。
    - 日志窗口: 会实时显示任务的进度和状态，如果出错可以查看这里的提示。

    祝您使用愉快！
    """
        # --- 内容结束 ---

        help_text_widget.insert(tk.END, help_content)

        # 定义标题样式
        help_text_widget.tag_configure("h1", font=("", 12, "bold", "underline"), spacing3=10)
        help_text_widget.tag_configure("h2", font=("", 10, "bold"), spacing1=10, lmargin1=10)

        lines = help_content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith("---") and line.strip().endswith("---"):
                help_text_widget.tag_add("h1", f"{i + 1}.0", f"{i + 1}.end")
            if line.strip().startswith("▶"):
                help_text_widget.tag_add("h2", f"{i + 1}.0", f"{i + 1}.end")

        help_text_widget.config(state="disabled")

        close_button = ttk.Button(help_win, text="我已了解，关闭窗口", command=help_win.destroy)
        close_button.pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = SurveyApp(root)
    root.mainloop()

# https://www.wjx.cn/vm/O42WOKh.aspx#
