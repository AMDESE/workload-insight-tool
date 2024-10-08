#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import time
import datetime
import os
import json
import re
import psutil
import threading
import platform
import netifaces
import sys
import pickle
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from signal import SIGKILL
from syswit.aggregate_results import AggregateResult

try:
    from numa import info
except ImportError:
    print("Unable to import info please remove numa package")

from syswit.utils import (
    parse_yaml_metrics,
    lscpu,
    generic_yaml_parser,
    timestamp_to_seconds,
    tag_pid_proc_file,
    path_pid_proc_file,
    check_proc_file_tag,
    check_path_pid_proc_file_tag,
    check_nodex_sys_source_file_tag,
)

from syswit import collector_config as config
from syswit import global_vars


class collector_helper:
    def __init__(self):
        self.nr_samples = config.nr_samples
        self.sample_period = config.sample_period
        self.delay_time = config.delay_time
        self.logs_d = config.logs_d
        self.pid = config.pid
        self.cpubind_default = config.cpubind_default
        self.numabind_default = config.cpubind_default
        self.flush_counter = config.flush_counter
        self.workload_given = config.workload_given
        self.flush_limit = config.flush_limit
        self.csv_result = config.csv_result
        self.ignore_workload_logs = config.ignore_workload_logs
        self.batch_size = config.batch_size
        self.ignore_offset = config.ignore_offset
        self.collector_input_config_path = config.collector_input_config_path
        self.output_file_name = config.output_file_name
        self.keep_workload_alive = config.keep_workload_alive

        self.result = {}
        self.parse_metrics = {}
        # process data collection related definitions
        self.p_source_files = {}
        # self.filters = ["numa", "hugepages","memory consumption", "cgroups", "anonymous memory"]
        self.filters = None
        # yaml_input_definations
        self.hugepages = dict()
        self.hugepages["size"] = ["1048576kB", "2048kB"]  # 1GB, 2MB
        self.hugepages["files"] = [
            "nr_hugepages",
            "surplus_hugepages",
            "free_hugepages",
        ]
        self.all_pids, self.cpus_to_run_tool = [], []
        self.all_pids_files = {}
        # global generic as well process level data collection related definitions
        self.g_source_files_save_once, self.g_source_files = {}, {}
        self._g_source_files_nodex_sys, self._g_source_files_proc, self.p_files = (
            [],
            [],
            [],
        )
        # Fetching metrics for special files
        (
            self.global_proc_stat_metrics,
            self.proc_pid_stat_metrics,
            self.proc_pid_statm_metrics,
        ) = ([], [], [])

        # generic parser separator details for some files
        self.generic_parser_separators = generic_yaml_parser(
            config.generic_parser_separators_path
        )
        # special parser designed for some files mapping to them
        special_parser_help = parse_yaml_metrics(config.special_parser_help_path)
        self.global_proc_stat_metrics = special_parser_help["proc_stat"]
        self.proc_pid_stat_metrics = special_parser_help["p_proc_stat"]
        self.proc_pid_statm_metrics = special_parser_help["p_proc_statm"]
        self.parse_proc_functions = {"stat": self.parse_proc_stat}
        self.parse_sys_functions = {}
        self.parse_pid_functions = {
            "stat": self.parse_p_proc_stat,
            "statm": self.parse_p_proc_statm,
        }
        _lscpu = lscpu()
        self.numa_nodes = _lscpu["numa_nodes"]
        self.node_cpu_info = (info.numa_hardware_info())["node_cpu_info"]
        self._cpu_count = os.cpu_count()

    def cpu_list_elements(self, input, hint):
        """
        @params input: str
            ex: Input "1,2,4:6"
        @params hint: int
            0 -> cpu list
            1 -> numa nodes list

        @return list
          [1,2,4,5,6]

        """
        result = set()
        if hint == 0:
            _max = self._cpu_count
        elif hint == 1:
            _max = self.numa_nodes

        for part in input.split(","):
            if ":" in part:
                start, end = part.split(":")
                for i in range(int(start), int(end) + 1):
                    if i < _max:
                        result.add(i)
            else:
                result.add(int(part))
        return list(result)

    def get_cpus_for_running_tool(self, user_cpu_input, user_node_input):
        """
        Convert cpu, numa input list provided to "," separated
        cpu list for affinity set
        """
        cpu_core_list = self.cpu_list_elements(user_cpu_input, 0)
        numa_node_list = self.cpu_list_elements(user_node_input, 1)
        try:
            if max(cpu_core_list) > self._cpu_count - 1 or min(cpu_core_list) < 0:
                sys.exit(f"cpus should be in range of (0,{self._cpu_count - 1})")

            if max(numa_node_list) > self.numa_nodes or min(numa_node_list) < 0:
                sys.exit(f"NUMA nodes should be in range of (0,{self.numa_nodes-1})")
        except ValueError:
            sys.exit(
                f"Invalid args values provided by user for cpu list and numa list, Please recheck defaults \nCpu Default:{self.cpubind_default} \
            NUMA Node defaults:{self.numabind_default}"
            )
        numanodes_combined = []
        for node in numa_node_list:
            numanodes_combined.extend(self.node_cpu_info[node])

        if user_cpu_input == self.cpubind_default:
            if user_node_input == self.numabind_default:
                self.cpus_to_run_tool = cpu_core_list
                return
            else:
                self.cpus_to_run_tool = numanodes_combined
                return
        else:
            if user_node_input == self.numabind_default:
                self.cpus_to_run_tool = cpu_core_list
                return
            else:
                if len(cpu_core_list) <= len(numanodes_combined) and all(
                    element in numanodes_combined for element in cpu_core_list
                ):
                    self.cpus_to_run_tool = cpu_core_list
                    return
                else:
                    sys.exit(
                        f"Incorrect input for cpu->{cpu_core_list} and numa node->{numanodes_combined}"
                    )

    def get_system_details(self):
        """
        Get generic system info
        """
        system = {}
        sys_details = os.uname()
        with open("/proc/cmdline", "r") as f:
            cmdline_proc_cmdline = f.read()
        system["Hostname"] = sys_details[1]
        system["Kernel Release"] = sys_details[2]
        system["cpu count"] = self._cpu_count
        system["NUMA Nodes"] = self.numa_nodes
        system["Operating System"] = sys_details[0]
        system["Python Version"] = platform.python_version()
        system["Processor Architecture"] = sys_details[4]
        system["Cpu Type"] = platform.processor()
        system["Network interfaces"] = netifaces.interfaces()
        system["cmdline"] = cmdline_proc_cmdline
        return system

    def convert_proc_stat_metric_to_logical_metric(self, proc_stat_metric):
        """
        @params proc_stat_metric: list
            proc stat metric list
        @return
            _fields for proc stat data collection

        proc_stat -> metric is made in "CPU<cpuno.> metric_name"
        """
        _fields = []
        for cpu in range(self._cpu_count + 1):
            for metric in proc_stat_metric:
                if cpu == 0:
                    _fields.append("CPU " + metric)
                else:
                    _fields.append("CPU " + str(cpu - 1) + " " + metric)
        return _fields

    def store_run_info(self):
        """
        store_run_info into final results
        """
        print("Logging metrics:")
        print(self.parse_metrics)
        self.result[self.flush_counter][global_vars.file_type] = f"{self.parse_metrics}"
        self.result[self.flush_counter][global_vars.offset] = self.ignore_offset
        self.result[self.flush_counter][global_vars.system_configuration] = []
        self.result[self.flush_counter][global_vars.system_configuration].append(
            dict(self.get_system_details())
        )
        if self.pid == None:
            self.result[self.flush_counter][global_vars.nr_samples] = self.nr_samples
        self.result[self.flush_counter][global_vars.sample_period] = self.sample_period
        self.result[self.flush_counter][global_vars.timestamps] = []
        self.global_proc_stat_field = []
        self.global_proc_stat_field = self.convert_proc_stat_metric_to_logical_metric(
            self.global_proc_stat_metrics
        )
        try:
            if getattr(self, "proc_stat"):
                if self.parse_metrics["proc_stat"] != [config.all_metric_tags]:
                    self.new_global_proc_stat_field = []
                    self.new_global_proc_stat_field = (
                        self.convert_proc_stat_metric_to_logical_metric(
                            self.parse_metrics["proc_stat"]
                        )
                    )
        except AttributeError:
            pass

    def collect_once(self):
        """
        collect metric values once
        like collecting hugepages -> size, files information
        """
        res = {}
        for source in self.g_source_files_save_once:
            try:
                with open(self.g_source_files_save_once[source], "r") as f:
                    value = f.read().split()
                res[source] = value[0]
            except FileNotFoundError:
                print(f"{source} not found")
        return res

    def _get_pid_threads(self, pid):
        """
        @params pid: int
            pid whose task/tid's have to be collected
        """
        try:
            path = "/" + config.identifier_pid_proc_files + "/" + str(pid) + "/task/"
            if os.path.exists(path):
                self.pid_threads.append(os.listdir(path))
        except FileNotFoundError:
            return
        except ProcessLookupError:
            print(f"\nHIT PROCESS LOOKUP ERROR IN _get_pid_threads {pid}")

    def get_pid_threads(self, pids):
        """
        @params pids: list
            list of all pids

        @return list
            self.pid_threads

            n pid's -> [m]*n pid's and tid's
            make a combined list of all id's
        """
        self.pid_threads = []
        worker_threads = []

        for i in pids:
            # pid-> pid/task/*
            worker = threading.Thread(target=self._get_pid_threads, args=(i,))
            worker_threads.append(worker)
            worker.start()
        for thread in worker_threads:
            thread.join()

        return self.pid_threads

    def update_pid_tid_list(self, key):
        """
        update all_pids list with tid if not present
        """
        for _ in self._all_pids_tids[key]:
            if int(_) not in self.all_pids:
                self.all_pids.append(int(_))

    def monitor_pid_children_threads(self):
        """
        This function runs till the time self.run_continue is True
        checks for parent and children pid, tids of parent and children.
        by checking in /proc/* and /proc/<pid>/task/*
        """
        while self.run_continue:
            self.thread_check_counter = self.thread_check_counter - 1
            if not self.pid_ignore_children:
                try:
                    children = self.parent.children(recursive=True)
                except psutil.NoSuchProcess as e:
                    if children in self.all_pids:
                        self.all_pids.remove(children)
                for _ in children:
                    if _ not in self.all_pids:
                        self.all_pids.append(_.pid)
                if not self.pid_ignore_threads:
                    if self.thread_check_counter == 0 or len(self.all_pids) < 3 * (
                        self._cpu_count
                    ):
                        self._all_pids_tids = self.get_pid_threads(self.all_pids)
                        worker_threads = []
                        for key in range(len(self._all_pids_tids)):
                            worker = threading.Thread(
                                target=self.update_pid_tid_list, args=(key,)
                            )
                            worker_threads.append(worker)
                            worker.start()
                        self.thread_check_counter = 5
            self.all_pids_latest = self.all_pids

    def flush_out_collected_data(self, counter):
        try:
            time.sleep(2)
            o = json.dumps(self.result[counter], indent=4)
            NewFileName = config.tmpflushdatafilename + str(counter) + ".json"
            path = os.path.join(self.logs_d, NewFileName)
            res = open(path, "w")
            res.write(o)
            res.close()
            self.result[counter] = {}
        except Exception as e:
            print(e)

    def check_result_sizen_flush(self):
        """
        check result dict size
        if exceeding threshold increment flush counter, flush collected data
        """
        if (
            int(sys.getsizeof(pickle.dumps(self.result[self.flush_counter])))
            > self.flush_limit
        ):
            c = self.flush_counter
            _thread = threading.Thread(target=self.flush_out_collected_data, args=(c,))
            # Dont join this thread as it may lead to missing data
            _thread.start()
            self.flush_counter = int(self.flush_counter) + 1
            self.result[self.flush_counter] = {}
            self.result[self.flush_counter]["timestamps"] = []

    def get_values(self, value):
        try:
            return int(re.sub("[^\d\.]", "", value.strip()))
        except:
            return value.strip()

    def generic_parser(self, file, delimiter, source, pid):
        """
        @params file: str
            Path of file to be collected
        @params delimiter: str
            separator for metric and value pair
        @params source: str
            metric_tag -> "<proc/sys/p_proc><_><filename>
        @params pid
            for global collection acts like a hint is equal to -1
            for  process collection pid is provided

        @return res: dict
            return with a {metric: value,metric: value, ... }
        """
        res = {}
        FlagforNode = False
        if check_nodex_sys_source_file_tag(source):
            parts = source.split("_")
            _source = "_".join(parts[1:])
            NodeNo = parts[0][4:]
            FlagforNode = True
        elif pid != -1:
            _source = "_".join(source.split("_")[1:])
            _source = "p_" + _source
        else:
            _source = source
        try:
            with open(file, "r") as f:
                for line in f.readlines():
                    if delimiter in line:
                        metric, value = line.split(delimiter, 1)
                        metric = metric.strip()
                        if pid != -1:
                            metric = pid + " " + metric
                        elif FlagforNode:
                            # special cases making metrics to be named like
                            # Node <numa node number> <metric>
                            if "numastat" in source or "vmstat" in source:
                                metric = "Node " + NodeNo + " " + metric

                        if self.parse_metrics[_source] == [config.all_metric_tags]:
                            res[metric] = self.get_values(value)
                        else:
                            if pid == -1:
                                if FlagforNode:
                                    _metric = (metric.split(" "))[2]
                                    if _metric in self.parse_metrics[_source]:
                                        res[metric] = self.get_values(value)
                                else:
                                    if metric in self.parse_metrics[_source]:
                                        res[metric] = self.get_values(value)
                            elif pid != -1:
                                _metric = (metric.split(" ", 1))[1]
                                if _metric in self.parse_metrics[_source]:
                                    res[metric] = self.get_values(value)

        except ValueError:
            print(
                "\nValue Error occurred in Fetching data\n",
                "file=",
                file,
                "delimiter=",
                delimiter,
                "source=",
                source,
                "Line=",
                line,
            )
        except FileNotFoundError:
            return self.default_not_found_value
        except ProcessLookupError:
            print(f"\nHIT PROCESS LOOKUP ERROR IN {source}")
            return self.default_not_found_value
        return res

    def parse_proc_stat(self, source):
        lines_count, start_index, end_index = 0, 0, 0
        words = []
        res = {}
        try:
            with open("/proc/stat", "r") as f:
                for line in f.readlines():
                    if lines_count <= self._cpu_count:
                        words = line.split()
                        start_index = end_index
                        end_index = end_index + len(words) - 1
                        small_proc_stat = self.global_proc_stat_field[
                            start_index:end_index
                        ]
                        for word, index in zip(words[1:], small_proc_stat):
                            try:
                                word = int(word)
                            except Exception as e:
                                word = str(word)
                            res[index] = word
                        lines_count = lines_count + 1
            if self.parse_metrics[source] != [config.all_metric_tags]:
                _res = {}
                for key in res.keys():
                    if key in self.new_global_proc_stat_field:
                        _res[key] = res[key]
                res = _res
            return res
        except ProcessLookupError:
            print(f"\nHIT PROCESS LOOKUP ERROR IN {source}")
            return self.default_not_found_value

    def special_parser_p_proc_stat_statm_file(self, source, metrics):
        """
        @params source: str
            "<p_proc><_><filename>
        @params metrics: list
            list of metric name for values
        @return res: dict
        parse /proc/pid/stat and /proc/pid/statm data
        """
        res = {}
        pid = source.split("_")[0]
        _source = "p_" + "_".join(source.split("_")[1:])
        try:
            with open(self.all_pids_files[source], "r") as f:
                data = f.readline().split()
                for i, j in zip(metrics, data):
                    i = pid + " " + i
                    res[i] = j
                if self.parse_metrics[_source] != [config.all_metric_tags]:
                    metrics = self.parse_metrics[_source]
                    _res = {}
                    for key, value in res.items():
                        _key = key.split(" ", 1)[1]
                        if _key in metrics:
                            _res[key] = value
                    res = _res
        except FileNotFoundError:
            if pid in self.all_pids:
                self.all_pids.remove(pid)
            return self.default_not_found_value
        except ProcessLookupError:
            print(f"HIT PROCESS LOOKUP ERROR IN {source}")
            if pid in self.all_pids:
                self.all_pids.remove(pid)
            return self.default_not_found_value
        return res

    def parse_p_proc_stat(self, source):
        metrics = self.proc_pid_stat_metrics
        return self.special_parser_p_proc_stat_statm_file(source, metrics)

    def parse_p_proc_statm(self, source):
        metrics = self.proc_pid_statm_metrics
        return self.special_parser_p_proc_stat_statm_file(source, metrics)

    def call_generic_parser(self, source):
        tmp = source.split("_")
        if check_proc_file_tag(source):
            return self.generic_parser(
                self.g_source_files[source],
                self.generic_parser_separators[source],
                source,
                -1,
            )
        elif check_nodex_sys_source_file_tag(source):
            filename = tmp[1] + "_" + tmp[2]
            return self.generic_parser(
                self.g_source_files[source],
                self.generic_parser_separators[filename],
                source,
                -1,
            )
        elif check_path_pid_proc_file_tag(source):
            pid = tmp[0]
            filename = "p_" + tmp[1] + "_" + tmp[2]
            return self.generic_parser(
                self.all_pids_files[source],
                self.generic_parser_separators[filename],
                source,
                pid,
            )

    def proc_sys_collect(self, source, str_current_datetime, hint):
        """
        @params source: str
            source tag of file to be collected
        @params str_current_datetime: str
            timestamp for collection identification
        @params hint: str
            global : -1
            process collection : 1
        @return
            update result = {timestamp:{res}}
        This function takes decision on which parser to call a/c to the
        source and hint, checking if a special parser available for them
        then calling that or if not checking if a separator is available
        else prompt not supported and continue.
        """
        res = []
        counter = self.flush_counter
        if int(hint) == -1:
            _path = self.g_source_files[source].split("/")
            tail = _path[len(_path) - 1]
            if _path[1] in config.identifier_proc_files:  # proc_->
                if tail in self.parse_proc_functions:
                    res.append(self.parse_proc_functions[tail](source))
                else:
                    try:
                        res.append(self.call_generic_parser(source))
                    except:
                        print("Doesn't support", self.g_source_files[source])
            if (
                _path[1] in config.identifier_sys_numanode_files
            ):  # /sys/*/numa(i)/file sys_ sys_shed -> /sys/
                if tail in self.parse_sys_functions:
                    res.append(self.parse_sys_functions[tail](source))
                else:
                    try:
                        res.append(self.call_generic_parser(source))
                    except:
                        print("Doesn't support", self.g_source_files[source])
        elif int(hint) == 1:
            _path = self.all_pids_files[source].split("/")
            tail = _path[len(_path) - 1]
            if _path[1] in config.identifier_pid_proc_files:  # /proc/pid/file
                if tail in self.parse_pid_functions:
                    res.append(self.parse_pid_functions[tail](source))
                else:
                    try:
                        res.append(self.call_generic_parser(source))
                    except:
                        print("Doesn't support", self.g_source_files[source])
        tempd = {}
        tempd[str_current_datetime] = res
        self.result[counter][source][0].update(tempd)

    def collect_global_data(self, str_current_datetime):
        """
        collect global files data from g_source_files list
        at a current timestamp.
        """
        for source in self.g_source_files:
            if source not in self.result[self.flush_counter]:
                self.result[self.flush_counter][source] = []
                self.result[self.flush_counter][source].append({})
            self.global_executor.submit(
                self.proc_sys_collect, source, str_current_datetime, -1
            )

    def pid_path_to_procfs(self, pid):
        for _file in self.p_files:
            tag = tag_pid_proc_file("proc", pid, _file)
            self.all_pids_files[tag] = path_pid_proc_file(
                config.identifier_pid_proc_files, pid, _file
            )

    def p_proc_sys_collect_caller(self, start, str_current_datetime):
        for source in list(self.all_pids_files.keys())[start : start + self.batch_size]:
            self.proc_sys_collect(source, str_current_datetime, 1)

    def collect_process_data(self, str_current_datetime):
        """
        collect process related data from files for all pids under monitoring
        at a current timestamp.
        """
        # utilization=check_tool_cpus_util(self.cpus_to_run_tool)

        for _ in list(set(self.all_pids_latest)):
            self.pid_path_to_procfs(_)
        for source in self.all_pids_files:
            if source not in self.result[self.flush_counter]:
                self.result[self.flush_counter][source] = []
                self.result[self.flush_counter][source].append({})

        pidListBatchSplit = []
        for i in range(0, len(self.all_pids_files), self.batch_size):
            pidListBatchSplit.append(i)
        self.pid_executor.map(
            self.p_proc_sys_collect_caller,
            pidListBatchSplit,
            repeat(str_current_datetime),
        )

    def check_pid_status(self, pid):
        if pid:
            if not psutil.pid_exists(pid):
                print(f"\na process with pid {pid} does not exists,Process Finished...")
                return False
        return True

    def collect(self):
        """
        This function is for collection of data until self.run_continue is enabled
        in sampling period time gaps
        checks for flushing requirement every iteration
        takes care of sampling time gap for accuracy in collection gaps
        It has two modes
        1. Collect global data
        2. Collect process level data
        stores results in result
        """
        str_last_current_datetime = "0"
        try:
            while self.run_continue:
                self.check_result_sizen_flush()
                print("*", end=" ", flush=True)
                current_datetime = datetime.datetime.now().strftime(
                    config.timestamps_style
                )
                str_current_datetime = str(current_datetime)
                current_time = timestamp_to_seconds(str_current_datetime)
                if str_last_current_datetime != "0":
                    last_time = timestamp_to_seconds(str_last_current_datetime)
                    time_difference = (self.sample_period + last_time) - current_time
                else:
                    time_difference = 0
                    last_time = 0

                if time_difference <= 0:
                    time.sleep(self.sample_period)
                else:
                    time.sleep(time_difference)
                    str_last_current_datetime = str_current_datetime

                self.result[self.flush_counter][global_vars.timestamps].append(
                    str_current_datetime
                )
                self.collect_global_data(str_current_datetime)
                if self.pid:
                    self.collect_process_data(str_current_datetime)
                if self.nr_samples != None:
                    if self.nr_samples <= 1 or not self.check_pid_status(self.pid):
                        self.run_continue = False
                    self.nr_samples -= 1
                else:
                    self.run_continue = self.check_pid_status(self.pid)
                if self.pid:
                    if not self.run_continue:
                        # flush remaining data
                        self.result[self.flush_counter][global_vars.all_pids] = []
                        self.result[self.flush_counter][global_vars.all_pids].append(
                            self.all_pids_latest
                        )
        except Exception as e:
            print(e)

    def kill_running_workload(self):
        try:
            if self.pid and self.check_pid_status(self.pid):
                if not self.keep_workload_alive:
                    os.kill(self.pid, SIGKILL)
                    print(f"\nKilled Process {self.pid}")
        except Exception as e:
            print(f"Issue with killing workload pid:{self.pid}")

    def aggregate_results(self):
        """
        Aggregate flushed results in multiple files to single result set,
        offset enabled in default, remove flushed multiple files after merger.
        """
        AggResObj = AggregateResult()
        AggResObj.path = self.logs_d
        AggResObj.global_varslist = self.global_varslist

        try:
            AggResObj.read_data()
        except Exception as e:
            print(e)

        if not self.ignore_offset:
            AggResObj.offset_data()
        final_path = os.path.join(self.logs_d, self.output_file_name)
        AggResObj.write_merged_data_to_file(final_path)
        if self.csv_result:
            AggResObj.write_csv_data(data=AggResObj.merged_data, file_name=final_path)
        AggResObj.remove_all_temp_result_files()
        print(f"Results at: {final_path}.json")

    def store_results(self):
        """
        This function is called if any exception occurs and tool stops,
        or its a normal exit.
        It stores remaining collected data and flushes out, calls for
        aggregation and store workload output if any.
        """
        self.kill_running_workload()
        time.sleep(1)

        try:
            self.global_executor.shutdown()
            if self.pid is not None:
                self.pid_executor.shutdown()
                self.result[self.flush_counter][global_vars.all_pids] = []
                self.result[self.flush_counter][
                    global_vars.all_pids
                ] = self.all_pids_latest
                self.MonitoringThread.shutdown(wait=False)
            self.flush_out_collected_data(self.flush_counter)
            self.aggregate_results()
            if self.workload_given:
                if not self.ignore_workload_logs:
                    print(f"Workload Output at: {self.workload_output_file}")
        except AttributeError as e:
            print(e)
            pass
        except Exception as e:
            print(e)

    def collect_n_parse(self):
        """
        This is main function for collection, parsing, storing, aggregating
        results for the sample. Flows as below ->
        set affinity of tool
        store run info
        collect and store results of files for single time sampling
        hold for delay_time if any
        start pid monitoring alive and pid,tid list on separate thread
        start collection
        store results, stop separate threads, aggregate results
        return
        """
        self.result[self.flush_counter] = {}
        os.sched_setaffinity(0, self.cpus_to_run_tool)  # tool_cpu_affinity
        self.store_run_info()
        # collect global elements to be parsed once
        self.res_g_source_files_save_once = self.collect_once()
        self.result[self.flush_counter].update(self.res_g_source_files_save_once)
        self.global_varslist = config.global_varslist
        self.global_varslist = self.global_varslist + list(
            self.res_g_source_files_save_once.keys()
        )
        # below if block is for threads synchronization purpose
        if self.delay_time > 0:
            wait_time = self.delay_time
            if wait_time > 0:
                print(f"Delaying Collection for {wait_time}s")
                print("waiting...")
                time.sleep(wait_time)
        self.run_continue = True
        # 0=global parsing only ; 1=pid related parsing
        if self.pid:
            self.result[self.flush_counter][global_vars.offset] = []

        print("Collecting...")
        self.parent = psutil.Process(self.pid)
        self.all_pids.append(self.parent.pid)
        self.all_pids_latest = self.all_pids
        self.thread_check_counter = 1
        self.global_executor = ThreadPoolExecutor(max_workers=self._cpu_count)
        if self.pid:
            self.pid_executor = ThreadPoolExecutor(max_workers=self._cpu_count)
            self.Counter_CheckingPidsList = 0
            self.MonitoringThread = ThreadPoolExecutor(max_workers=1)
            self.MonitoringThread.submit(self.monitor_pid_children_threads)
        self.collect()
        print("Saving logs...")
        self.store_results()
