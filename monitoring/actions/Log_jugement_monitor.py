""""Log文件解析模块"""
import re
from pathlib import Path
from bs4 import BeautifulSoup
import re
import chardet
from pathlib import Path
from typing import List, Dict, Tuple, Union, Optional

# 常量定义（提升可维护性）
LOG_ENCODING_DETECT_FAIL = "utf-8"  # 编码检测失败时的默认编码
DISK_SPEED_THRESHOLD = 800 * (10 ** 6)  # 磁盘速度阈值
SEPARATOR_COLON = " : "
SEPARATOR_NEWLINE = "\n"
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"


class LogParser:
    """日志解析器：支持MikeLog/TransitionCapLog/DriversLog/CrystalDiskMarkLog四种日志解析"""
    # 测试用例配置（类常量，便于统一维护）
    TEST_CASE_CONFIG: Dict[str, Dict[str, Union[int, float]]] = {
        "mikelog": {
            'S0i3 / resume ( auto resume)': 300,
            'hibernation / resume test ( auto resume )': 300,
            'power off test': 200,
            'restart test': 261
        },
        "transitioncaplog": {
            'S0i3 / Res (Auto)': 400,
            'monitoring': 400,
        },
        'crystaldiskmarklog': {
            "bytes/s": 1,
            "KB/s": 10 ** 3,
            "MB/s": 10 ** 6,
            "GB/s": 10 ** 9,
            "TB/s": 10 ** 12
        }
    }

    def __init__(self, context, keyword: str):
        self.context = context
        self.keyword = keyword.lower()  # 统一转为小写，避免大小写问题
        self.test_case = self.TEST_CASE_CONFIG.get(self.keyword)  # 简化赋值逻辑
        self.result: Optional[str] = None  # 类型标注+规范命名

    def read_log(self, log_file: Union[str, Path]) -> str:
        """读取日志文件，自动检测编码，处理文件读取异常"""
        try:
            log_file = Path(log_file)
            if not log_file.exists():
                raise FileNotFoundError(f"日志文件不存在：{log_file}")

            # 检测文件编码
            with open(log_file, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data).get('encoding', LOG_ENCODING_DETECT_FAIL)

            # 读取文件内容
            with open(log_file, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            self.context.log(f"读取日志文件失败：{str(e)}")
            return ""

    def _finder_mike_data(self, log_data: str) -> List[str]:
        """解析MikeLog日志数据"""
        test_name = re.findall(r'INSPECTION\s*:\s*(.+)', log_data)
        test_counter = re.findall(r'Resume counter \(Total\)\s*=\s*(.+)', log_data)
        loop_count = re.findall(r'Start power supply management processing', log_data)

        # 处理计数器为空的情况
        if not test_counter:
            test_counter.append(str(len(loop_count)) if loop_count else '0')

        return test_counter + test_name[:1]  # 取第一个测试名称，避免多值

    def _finder_transitioncap_data(self, log_data: str) -> List[str]:
        """解析TransitionCapLog日志数据"""
        test_name = re.findall(r'INSPECTION\s*:\s*(.+)', log_data)
        test_counter = re.findall(r'loop\s*count\s*=\s*(.+)', log_data)
        test_result = re.findall(r'result\s*=\s*(.+)', log_data)
        loop_count = re.findall(r'#\s*count\s*=\s*(\d+)', log_data)

        if test_result:
            self.result = test_result[0]

        # 处理计数器为空的情况
        if not test_counter:
            test_counter.append(str(len(loop_count)) if loop_count else '0')

        return test_counter + test_name[:1]

    def _finder_drivers_data(self, log_data: str) -> List[str]:
        """解析DriversLog日志数据"""
        test_name = re.findall(r'Dock Name\s*:\s*(.+)', log_data)
        test_result = re.findall(r'RC:\s*0\(0\)', log_data)

        if test_result:
            result_info = ["已找到RC字符", RESULT_PASS]
        else:
            result_info = ["未找到RC字符", RESULT_FAIL]

        return test_name + result_info

    def _execute_diskspeed(self, line: str) -> str:
        """解析单行磁盘速度数据，返回格式化字符串"""
        speed_match = re.findall(
            r'Sequential\s*1MiB\s*\(Q=\s*8,\s*T=\s*1\):\s*(\d+.?\d+)\s*(\w+.?\w+)',
            line
        )
        if not speed_match:
            return ""

        number, unit = speed_match[0]
        judge_result = self._diskspeed_judgement(number, unit)
        return SEPARATOR_COLON.join([number + unit, judge_result])

    def _finder_diskspeed_data(self, log_data: str) -> Tuple[List[str], List[str]]:
        """解析CrystalDiskMarkLog日志数据"""
        read_flag = False
        write_flag = False
        data_dict: Dict[str, List[str]] = {"readspeed": [], "writespeed": []}
        log_lines = log_data.split(SEPARATOR_NEWLINE)

        for line in log_lines:
            line = line.strip()
            if not line:
                continue  # 跳过空行

            # 切换读写标记
            if re.search(r'\[Read\]', line):
                read_flag = True
                write_flag = False
            elif re.search(r'\[Write\]', line):
                write_flag = True
                read_flag = False

            # 提取速度数据
            speed_value = self._execute_diskspeed(line)
            if speed_value:
                if read_flag:
                    data_dict["readspeed"].append(speed_value)
                elif write_flag:
                    data_dict["writespeed"].append(speed_value)

        # 整理结果
        formatted_result = []
        for key, value in data_dict.items():
            if value:  # 只添加有数据的项
                formatted_result.append(SEPARATOR_NEWLINE + key.title())
                formatted_result.extend(value)

        # 校验结果
        check_result = [self._check_result_list(v) for v in data_dict.values() if v]
        return formatted_result, check_result

    def _diskspeed_judgement(self, number_str: str, unit: str) -> str:
        """判断磁盘速度是否达标，替换不安全的eval为float"""
        try:
            speed_spec = self.TEST_CASE_CONFIG[self.keyword]
            number = float(number_str)
            actual_speed = number * speed_spec[unit]
            return RESULT_PASS if actual_speed >= DISK_SPEED_THRESHOLD else RESULT_FAIL
        except (ValueError, KeyError) as e:
            self.context.log(f"磁盘速度判断失败：{str(e)}")
            return RESULT_FAIL

    def _data_judgement(self, count_str: str, name: str) -> List[str]:
        """判断测试计数是否达标，处理类型转换异常"""
        try:
            count = int(count_str)
            if not self.test_case or name not in self.test_case:
                return [f"测试名称不在配置中，测试计数：{count}", RESULT_FAIL]

            target_count = self.test_case[name]
            result = RESULT_PASS if count >= target_count else RESULT_FAIL
            return [f"{count}/{target_count}", result]
        except ValueError:
            return [f"测试计数值非法：{count_str}", RESULT_FAIL]

    @staticmethod
    def _check_result_list(result_list: List[str]) -> str:
        """校验结果列表中是否有FAIL"""
        return RESULT_FAIL if any(RESULT_FAIL in item.split(SEPARATOR_COLON) for item in result_list) else RESULT_PASS

    # 日志解析策略映射（替代if-elif，提升扩展性）
    _PARSE_STRATEGY: Dict[str, callable] = {
        "mikelog": _finder_mike_data,
        "transitioncaplog": _finder_transitioncap_data,
        "driverslog": _finder_drivers_data,
        "crystaldiskmarklog": _finder_diskspeed_data
    }

    def parse_log_file(self, paths: Union[str, Path]) -> List[str]:
        """解析单个日志文件/文件夹（此处保留原逻辑，仅处理文件）"""
        log_info = []
        paths = Path(paths)

        if not paths.is_file():
            self.context.log(f"不是有效文件：{paths}")
            return log_info

        # 读取日志内容
        log_data = self.read_log(paths)
        if not log_data:
            return log_info

        # 执行对应解析策略
        parse_method = self._PARSE_STRATEGY.get(self.keyword)
        if not parse_method:
            self.context.log(f"不支持的日志类型：{self.keyword}")
            return log_info

        # 解析日志并处理结果
        parse_result = parse_method(self, log_data)
        if self.keyword in ["mikelog", "transitioncaplog"]:
            judge_result = self._data_judgement(*parse_result)
            log_info = parse_result + judge_result
            self.context.log(SEPARATOR_COLON.join(log_info[1:]))
        elif self.keyword == "driverslog":
            log_info = parse_result
            self.context.log(SEPARATOR_COLON.join(log_info))
        elif self.keyword == "crystaldiskmarklog":
            log_info, check_result = parse_result
            self.context.log(SEPARATOR_NEWLINE.join(log_info))
            log_info.extend(check_result)

        return log_info
class HtmlParser:
    def __init__(self,context):
        super().__init__()
        self.context=context
    def read_html(self,html_file_path:str)->str:
        """
        从HTML文件中提取所有Failure对应的错误描述
        :param html_file_path: HTML文件路径
        :return: 所有错误描述的列表（无则返回空列表）
        """
        # -------------------------- 1. 读取HTML文件（自动处理编码） --------------------------
        try:
            # 第一步：读取二进制内容，检测编码
            with open(html_file_path, "rb") as f:
                raw_data = f.read()
            # 自动检测编码（解决乱码问题）
            detected_encoding = chardet.detect(raw_data)["encoding"]
            # 第二步：用检测到的编码读取文件
            with open(html_file_path, "r", encoding=detected_encoding) as f:
                html_content = f.read()
        except FileNotFoundError:
            self.context.log(f"错误：未找到文件 {html_file_path}")
            return 'None'
        except Exception as e:
            self.context.log(f"读取文件失败：{e}")
            return 'None'
        return html_content

    def fail_jugement_(self,html_data:list)->list:
            if html_data==[]:
                return ['PASS']
            return ['FAIL']

    def finder_html_data(self,html_path:str)->list:
        """
        :param html_data:
        :return:
        """
        html_content=self.read_html(html_path)
        # --------------------------解析HTML并提取所有Failure描述 --------------------------
        soup = BeautifulSoup(html_content, "html.parser")  # 无需lxml，内置解析器
        # 查找所有包含Failure的MT_Message类td标签（精准匹配）
        all_failure_tds = soup.find_all(
            "td",
            class_="MT_Message",
            # 过滤条件：文本非空 + 包含Failure（忽略大小写/首尾空白）
            string=lambda text: text and "Failure" in text.strip()
        )
        failure_messages = []  # 存储所有提取到的错误描述
        if not all_failure_tds:
            self.context.log(f"未找到任何包含Failure的MT_Message标签")
            return failure_messages

        # 遍历每个Failure标签，提取对应的错误描述
        self.context.log(f"共找到 {len(all_failure_tds)} 个Failure，开始提取描述：")
        for idx, failure_td in enumerate(all_failure_tds, 1):
            # 找当前td的下一个同class的兄弟td（错误描述标签）
            error_desc_td = failure_td.find_next_sibling("td", class_="MT_Message")
            if error_desc_td:
                # 提取纯文本，去除首尾空白/换行
                error_msg = error_desc_td.get_text(strip=True)
                failure_messages.append(error_msg)
                self.context.log(f"【第{idx}个Failure】\n错误描述：{error_msg}")
            else:
                # 无对应描述的情况（边界处理）
                self.context.log(f"【第{idx}个Failure】\n未找到对应的错误描述标签")
                failure_messages.append("无错误描述")

        return self.fail_jugement_(failure_messages)