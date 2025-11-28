import win32evtlog
import win32evtlogutil
from datetime import datetime
from config.paths import get_patvs_root
from pathlib import Path
import json
import wmi
import win32evtlog
from datetime import datetime
"""统计s4，s3的时间进行保存在本地"""
class Json_Excute:
    def __init__(self):
        super().__init__()
    def write_json(self,data):
        # 将字典写入JSON文件
        with open( self.path_, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    def read_json(self):

        try:
            with open(self.path_, 'r', encoding='utf-8') as f:
                # 尝试加载文件内容，如果文件为空或格式错误，会抛出异常
                existing_data = json.load(f)
                if existing_data==None:
                    existing_data=[]
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在，或者文件为空/格式错误，初始化一个空列表
            existing_data = []

        return existing_data
    def remove_json(self):
        # 检查文件是否存在
        if self.path_.exists():
            # 删除文件
            self.path_.unlink()

    def view_times(self):
        if self.read_json()!=[]:
            for i in  self.read_json():
                self.context.log(f'{i[0] ,i[-1]}')

class S4_times(Json_Excute):

    def __init__(self,context,state='S4'):
        super().__init__()
        if state=='S4':
            self.max_records=50
        else:
            self.max_records = 10
        self.root_=get_patvs_root()
        self.state=state
        self.path_=self.root_ / f"{state}_times.json"
        self.time_formate="%Y-%m-%d %H:%M:%S.%f"
        self.context=context

    def count_times(self,start,end,count):
        json_info_=self.read_json()
        times_=datetime.strptime(end, self.time_formate)-datetime.strptime(start, self.time_formate)
        times_=times_.total_seconds()
        self.context.log(" , ".join([f"第{str(count)}次{self.state}到使用间隔",self.trans_form(int(times_))]))
        json_info_.append([f"第{str(count)}次{self.state}",start,end,self.trans_form(int(times_))])

        self.write_json(json_info_)

    def trans_form(self,total_seconds):

        # 4. 分解总秒数为 时、分、秒
        hours = total_seconds // 3600  # 1小时 = 3600秒
        remaining_seconds = total_seconds % 3600
        minutes = remaining_seconds // 60  # 1分钟 = 60秒
        seconds = remaining_seconds % 60

        # 5. 格式化输出
        return f"{hours:02d}小时{minutes:02d}分钟{seconds:02d}秒"


    def read_system_events(self,log_name="System"):
        """
            读取指定事件日志的事件
            :param log_name: 日志名称（如 "System"、"Application"、"Security"）
            :param max_records: 最大读取记录数
            :return: 事件列表
            """
        events = []
        try:
            # 1. 打开事件日志（参数：计算机名None=本地，日志名称）
            log_handle = win32evtlog.OpenEventLog(None, log_name)
            if not log_handle:
                return [f"无法打开日志：{log_name}"]
            # 2. 配置读取模式：从最新事件向最早读取（逆序），按顺序读取
            read_flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            read_count = 0  # 已读取的事件数
            while read_count < self.max_records:
                # 3. 读取事件（每次最多读100条，避免性能问题）
                # 参数：日志句柄、读取模式、起始位置（0=从当前位置）
                event_list = win32evtlog.ReadEventLog(log_handle, read_flags, 0)
                if not event_list:
                    break  # 无更多事件
                for event in event_list:
                    # 4. 解析事件属性
                    # 事件ID（注意：需用event.EventID & 0xFFFF获取实际ID，避免高位标志位干扰）
                    event_id = event.EventID & 0xFFFF
                    # 事件来源（如 "Microsoft-Windows-Kernel-Power"）
                    source = event.SourceName
                    # 事件生成时间（本地时间）
                    time_generated = event.TimeGenerated.strftime(self.time_formate)
                    # 事件描述（需用win32evtlogutil格式化，部分事件可能无描述）
                    try:
                        # 格式化事件消息（需要事件来源的消息文件支持）
                        description = win32evtlogutil.FormatEvent(event)
                    except:
                        description = "无法获取事件描述"
                    # 存储事件信息
                    events.append({
                        "时间": time_generated,
                        "来源": source,
                        "事件ID": event_id,
                        "描述": description
                    })

                    read_count += 1
                    if read_count >= self.max_records:
                        break
            # 5. 关闭日志句柄
            win32evtlog.CloseEventLog(log_handle)
            return events if events else [f"日志 {log_name} 中未找到事件"]
        except Exception as e:
            return [f"读取日志失败：{str(e)}（可能需要管理员权限）"]

    def filter_deepsleep_events(self,start_time,count=1,):
        events = self.read_system_events(log_name="System")
        if not isinstance(events, list):
            return events
        sleep_events = []
        # 筛选条件：来源为Kernel-Power，事件ID为187（进入睡眠）
        for event in events:
            if isinstance(event, dict) and datetime.strptime(event["时间"], self.time_formate) >= start_time:
                sleep_events.append(event["时间"])
                if event["事件ID"] == 187:
                    sleep_events.append(event["时间"])
                    break
        self.count_times(sleep_events[-1], sleep_events[0],count)

        return

    def filter_sleep_events(self,start_time,count=1,):
        events = self.read_system_events(log_name="System")
        if not isinstance(events, list):
            return events
        sleep_events = []
        for event in events:
            if isinstance(event, dict) and datetime.strptime(event["时间"], self.time_formate) >= start_time:
                if event["事件ID"] ==566 and len(sleep_events)<2:
                    sleep_events.append(event["时间"])

        self.count_times(sleep_events[-1], sleep_events[0],count)
        return



