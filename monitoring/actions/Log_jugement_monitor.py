""""Log文件解析模块"""
import re
from pathlib import Path

class Log_parse:

    def __init__(self,context,keyworkd:str):
        super().__init__()
        self.context=context
        self.keyword=keyworkd

        self.test_case_dic={

            "mikelog":{
                    'S0i3 / resume ( auto resume)': 300,
                    'hibernation / resume test ( auto resume )': 300,
                    'power off test': 200,
                    'restart test': 261
                },

            "transitioncaplog":{
                    'S0i3 / Res (Auto)':400,
                    'monitoring':400,
                },
        }

        if self.keyword.lower() in self.test_case_dic.keys():
            self.test_case=self.test_case_dic[self.keyword.lower()]
        else:
            self.test_case=None

        self.result_ = None

    def read_log_(self,log_file)->list:
        with open(log_file,'r',encoding='latin-1') as file:
            log_data=file.read()
        print(log_data)
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

            if self.keyword.lower()=='transitioncaplog':
                log_info_ = self.finder_transitioncap_data(self.read_log_(paths_))
                result_info = self.data_jugement(*log_info_)

            elif self.keyword.lower()=='mikelog':
                log_info_ = self.finder_mike_data(self.read_log_(paths_))
                result_info = self.data_jugement(*log_info_)

            elif self.keyword.lower()=='driverslog':
                log_info_ = self.finder_drivers_data(self.read_log_(paths_))


            if result_info!=None:
                log_info_.append(result_info)

            self.context.log(" : ".join(log_info_))

        return log_info_

