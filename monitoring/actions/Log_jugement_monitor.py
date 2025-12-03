""""Log文件解析模块"""
import re
from pathlib import Path

class Log_parse:

    def __init__(self,context,keyworkd:str):
        super().__init__()
        self.context=context
        self.keyword=keyworkd

        self.test_case_dic={

            "MikeLog".lower():{
                    'S0i3 / resume ( auto resume)': 300,
                    'hibernation / resume test ( auto resume )': 300,
                    'power off test': 200,
                    'restart test': 261
                },

            "TransitionCapLog".lower():{
                    'S0i3 / Res (Auto)':400,
                    'monitoring':400,
                },

            'CrystalDiskMarkLog'.lower():{
                "bytes/s":1,
                "KB/s": 10**3,
                "MB/s": 10**6,
                "GB/s": 10**9,
                "TB/s": 10**12
              }
        }

        if self.keyword.lower() in self.test_case_dic.keys():
            self.test_case=self.test_case_dic[self.keyword.lower()]
        else:
            self.test_case=None

        self.result_ = None

    def read_log_(self,log_file,encoding:str='latin-1')->list:
        with open(log_file,'r',encoding=encoding) as file:
            log_data=file.read()
        return log_data

    def finder_mike_data(self,log_data):
        test_name=re.findall(r'INSPECTION\s*:\s*(.+)',log_data)
        test_counter=re.findall(r'Resume counter \(Total\)\s*=\s*(.+)',log_data)
        loop_count=re.findall(r'Start power supply management processing',log_data)
        if test_counter==[]:
            if  loop_count!=[]:
                test_counter.append(str(len(loop_count)))
            else:
                test_counter.append('0')
        return test_name[:1]+test_counter

    def finder_transitioncap_data(self,log_data)->list:

        test_name=re.findall(r'INSPECTION\s*:\s*(.+)',log_data)
        test_counter=re.findall(r'loop\s*count\s*=\s*(.+)',log_data)
        test_result= re.findall(r'result\s*=\s*(.+)', log_data)
        loop_count=re.findall(r'#\s*count\s*=\s*(\d+)',log_data)

        if test_result!=[]:
            self.result_=test_result[0]

        if  test_counter==[]:
            if  loop_count!=[]:
                test_counter.append(str(len(loop_count)))
            else:
                test_counter.append('0')

        return test_name[:1]+test_counter

    def finder_drivers_data(self,log_data)->list:

        test_name=re.findall(r'Dock Name\s*:\s*(.+)',log_data)
        test_result=re.findall(r'RC:\s*0\(0\)', log_data)

        if test_result!=[]:
            test_result.append("PASS")
        else:
            test_result.append("FAIL")

        return test_name+[test_result[-1]]

    def excute_diskspeed_(self,string_data:str)->list:

        dicsk_speed_=re.findall(
            r'Sequential\s*1MiB\s*\(Q=\s*8,\s*T=\s*1\):\s*(\d+.?\d+)\s*(\w+.?\w+)',
            string_data
        )

        if dicsk_speed_!=[]:
            dicsk_speed_= ([i+j for i,j in dicsk_speed_]+
                           [self.diskspeed_jugement(*dicsk_speed_[0])])
        return " : ".join(dicsk_speed_)

    def finder_diskspeed_data(self,log_data)->list:

        _read_flag_=False
        _write_flag_=False
        data_dic={}
        log_data=log_data.split('\n')

        for i in log_data:

            if re.search(r'\[Read\]',i)!=None:
                _read_flag_= True
                _write_flag_ = False

            if re.search(r'\[Write\]',i)!=None:
                _write_flag_= True
                _read_flag_=False

            speed_value_ = self.excute_diskspeed_(i)

            if _read_flag_ and speed_value_ not in ["",None," "]:
                data_dic.setdefault('readspeed',[]).append(speed_value_)

            if _write_flag_ and speed_value_ not in ["",None," "]:
                data_dic.setdefault('writespeed',[]).append(speed_value_)

        result_=[value[-1] for key,value in  data_dic.items() if 'PASS' in  value]
        check_has_one = lambda lst: "FAIL" if lst!=[] else "PASS"
        return  (sum([["\n"+key.title()]+value for key,value in data_dic.items()],[])
                     ,[check_has_one(result_)])


    def diskspeed_jugement(self, number: str, unite: str):
        """
        :param name:
        :param count:
        :return:
        """
        speed_Specificate = self.test_case_dic[self.keyword.lower()]
        result_=None

        if eval(f"{number}*{speed_Specificate[unite]}")<800*(10**6):
            result_= "FAIL"
        else:
            result_= "PASS"

        return result_

    def data_jugement(self,name:str,count:str)->str:
        """
        :param name:
        :param count:
        :return:
        """
        if name in list(self.test_case.keys()):
            if int(count)<self.test_case[name]:
                return "FAIL"+" : "+str(eval(f'{self.test_case[name]}-{count}'))
            else:
                return "PASS"

        return "Test Name not in Tab , "+f"Test Counter is {count}"

    def folder_files(self,paths)->list:

        result_=[]
        log_info_=[]
        result_info=None
        paths_ = Path(paths)
        if paths_.is_file() :
            if self.keyword.lower()=='TransitionCapLog'.lower():
                log_info_ = self.finder_transitioncap_data(self.read_log_(paths_))
                result_info = self.data_jugement(*log_info_)
                self.context.log(" : ".join(log_info_))

            elif self.keyword.lower()=='MikeLog'.lower():
                log_info_ = self.finder_mike_data(self.read_log_(paths_))
                result_info = self.data_jugement(*log_info_)
                self.context.log(" : ".join(log_info_))

            elif self.keyword.lower()=='DriversLog'.lower():
                log_info_ = self.finder_drivers_data(self.read_log_(paths_))
                self.context.log(" : ".join(log_info_))

            elif self.keyword.lower() == 'CrystalDiskMarkLog'.lower():
                log_info_,result_info = self.finder_diskspeed_data(self.read_log_(paths_, 'utf-16'))
                self.context.log("\n".join(log_info_))

            if result_info!=None:
                log_info_.append(result_info)

        return log_info_

