#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import argparse
import os
import sys
import datetime
from syswit.utils import (
    parse_yaml_metrics,
    run_cmd_and_get_pid,
    path_proc_file,
    tag_proc_file,
    path_nodex_sys_hugepages,
    tag_nodex_sys_hugepages,
    path_nodex_sys_source_file,
    tag_nodex_sys_source_file,
)
from syswit.collector_helper import collector_helper
from syswit import collector_config as config


class collector:
    """
    This module collects global and process related system stats
    in a time-series manner for a workload.
    """

    def __init__(self):
        self.print_info = []

    def add_arguments(self, parser=None):
        if parser is None:
            parser = argparse.ArgumentParser(
                description="E.g., python3 collector.py -p 234 -n 10 -s 1",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
        parser.add_argument(
            "-c",
            "--collector-input-config",
            type=str,
            default=config.collector_input_config_path,
            help="Path to the collector input config",
        )
        parser.add_argument(
            "-p", "--pid", type=int, help="PID of process to be monitored"
        )
        parser.add_argument(
            "-w", "--workload", type=str, help="Command/Workload to run"
        )
        parser.add_argument(
            "-C",
            "--ignore-children",
            action="store_true",
            help="Collection will be done for parent process only but not for children processes",
        )
        parser.add_argument(
            "-T",
            "--ignore-threads",
            action="store_true",
            help="Collection will be done for parent and children processes but not for threads",
        )
        parser.add_argument(
            "-K",
            "--keep-workload-alive",
            action="store_true",
            help="Keep workload alive when collection ends",
        )
        parser.add_argument(
            "-n",
            "--nr-samples",
            type=int,
            help=f"No. of samples to be collected" f"(Default:{config.nr_samples})",
        )
        parser.add_argument(
            "-d",
            "--delay-time",
            default=config.delay_time,
            type=int,
            help="Start monitoring after DELAY_TIME(s)",
        )
        parser.add_argument(
            "-s",
            "--sample-period",
            default=config.sample_period,
            type=float,
            help=f"Time period between successive samples(s)(Default:{config.sample_period})",
        )
        parser.add_argument(
            "-o",
            "--output-file-name",
            default=config.output_file_name,
            type=str,
            help="Output file name",
        )
        parser.add_argument(
            "-j",
            "--cpu-affinity",
            default=config.cpubind_default,
            type=str,
            help="Bind the tool to specified CPUs. E.g., '0:2,6' -> '[0,1,2,6]'",
        )
        parser.add_argument(
            "-m",
            "--node-affinity",
            default=config.numabind_default,
            type=str,
            help="Bind the tool to specified NUMA node. E.g., '0,1'",
        )
        parser.add_argument(
            "-f",
            "--flush-limit",
            default=config.flush_limit,
            type=int,
            help=f"Flushing intermediate results to storage if collected data exceeds this FLUSH_LIMIT in bytes, Default: {config.flush_limit}",
        )
        parser.add_argument(
            "-L",
            "--ignore-workload-logs",
            action="store_true",
            help="Don't capture workload output. By default it is captured in workload.output",
        )
        parser.add_argument(
            "-l",
            "--log-dir",
            default=config.logs_d,
            type=str,
            help="Results path",
        )
        parser.add_argument(
            "-a",
            "--csv-result",
            default=config.csv_result,
            action="store_true",
            help="Get results in CSV format",
        )
        parser.add_argument(
            "-R",
            "--ignore-offset",
            action="store_true",
            help=f"Don't offset the metric values, Default: {config.ignore_offset}",
        )
        # TODO
        # parser.add_argument(
        #     "--offset_metric_file",
        #     default=None,
        #     type=str,
        #     help="offset the metrics using given offset yaml(Not Implemented yet)",
        # )
        return parser

    def process_arguments(self, params):
        parser = self.add_arguments()

        if params is None:
            self.args = parser.parse_args()
        else:
            self.args = params

    def make_log_directory(self):
        current_datetime = datetime.datetime.now().strftime(config.timestamps_style)
        str_current_datetime = str(current_datetime)

        if self.args.log_dir != None:
            logs_d = os.path.join(os.getcwd(), self.args.log_dir, str_current_datetime)
        else:
            logs_d = os.path.join(os.getcwd(), self.col_h.logs_d, str_current_datetime)
        self.col_h.logs_d = logs_d
        try:
            # Create target Directory
            os.makedirs(self.col_h.logs_d)
            self.print_info.append("Directory Created: " + self.col_h.logs_d)
        except FileExistsError:
            self.print_info.append("Directory " + self.col_h.logs_d + " already exists")

    def run_workload(self):
        """
        This function runs workload, and return with pid
        """
        self.col_h.workload_given = True
        if not self.args.ignore_workload_logs:
            self.col_h.workload_output_file = self.col_h.logs_d + "/workload.output"
            cmd = self.args.workload + " > " + self.col_h.workload_output_file
        else:
            self.col_h.ignore_workload_logs = True
            cmd = self.args.workload

        self.print_info.append("Command: " + cmd)
        return run_cmd_and_get_pid(cmd)

    def process_pid(self):
        """
        Process pid if provided any
        Run workload for user if provided and get pid,
        raise exception if pid < 0
        continue if pid is None or > 0, for global or global+process
        collection mode
        """
        pid = None
        if self.args.workload != None:
            pid = self.run_workload()
        else:
            if self.args.pid != None:
                pid = self.args.pid
        try:
            if pid:
                if pid > 0:
                    self.col_h.pid = pid
                    self.print_info.append("Parent PID: " + str(self.col_h.pid))
                elif pid < 0:
                    raise Exception(f"Improper cmd or pid {pid}")
            else:
                self.col_h.pid = None
        except Exception as e:
            raise e

    def parse_yaml_metric_inputs(self, data, prefix=""):
        """
        parse collector_input_yaml inputs
        """
        for key, value in data.items():
            if isinstance(value, dict):
                if key == "hugepages":
                    hugepages = value
                    if hugepages != None:
                        if hugepages["size"] != None:
                            self.col_h.hugepages["size"] = hugepages["size"].split(",")
                        else:
                            self.col_h.hugepages["size"] = self.col_h.hugepages["size"]
                        if hugepages["files"] != None:
                            self.col_h.hugepages["files"] = hugepages["files"].split(
                                ","
                            )
                        else:
                            self.col_h.hugepages["files"] = self.col_h.hugepages[
                                "files"
                            ]

                        print(
                            "Hugepages- size:",
                            self.col_h.hugepages["size"],
                            " files: ",
                            self.col_h.hugepages["files"],
                        )
                else:
                    for sub_key, sub_value in value.items():
                        self.parse_yaml_metric_inputs(
                            {sub_key: sub_value}, f"{prefix}{key}."
                        )
            else:
                if value == None:
                    value = [config.all_metric_tags]
                variable_name = f"{key}"
                globals()[variable_name] = value
                setattr(self.col_h, variable_name, value)
                split_key = key.split("_")
                for _key, _value in vars(self.col_h).items():
                    if _value == getattr(self.col_h, variable_name):
                        self.col_h.parse_metrics[key] = value
                if len(split_key) == 2:
                    if split_key[0] == config.identifier_proc_files:
                        self.col_h._g_source_files_proc.append(path_proc_file(key))
                    elif split_key[0] == config.identifier_sys_numanode_files:
                        self.col_h._g_source_files_nodex_sys.append(split_key[1])
                elif len(split_key) == 3 and split_key[0] == "p":
                    if split_key[1] == config.identifier_pid_proc_files:
                        self.col_h.p_files.append(split_key[2])
                else:
                    print(f"Incorrect metric input {key} {value}")
        if len(self.col_h.p_files) == 0:
            self.col_h.pid_ignore_children = True
            self.col_h.pid_ignore_threads = True

    def get_file_paths(self):
        hugepages_files = {}
        for numa in range(0, self.col_h.numa_nodes, 1):
            # hugepages_files prepare
            for size in self.col_h.hugepages["size"]:
                for files in self.col_h.hugepages["files"]:
                    _path = path_nodex_sys_hugepages(numa, files, size)
                    _tag = tag_nodex_sys_hugepages(numa, files, size)
                    hugepages_files[_tag] = _path
                    self.col_h.g_source_files_save_once[_tag] = _path

            # g_source_file prepare
            for source_file in self.col_h._g_source_files_nodex_sys:
                _path = path_nodex_sys_source_file(numa, source_file)
                _tag = tag_nodex_sys_source_file(numa, source_file)
                self.col_h.g_source_files[_tag] = _path
        for files in self.col_h._g_source_files_proc:
            _tag = tag_proc_file(files)
            self.col_h.g_source_files[_tag] = files

    def main(self, params=None, *args):
        """
        @params params:
        Collector collector params, args and process arguments and sets the
        table for collector_helper which later starts collecting and storing
        data in time-series manner.
        KeyboardInterrupt handled, stops all functions stores whatever is in
        flush and gets out.
        """
        self.process_arguments(params)
        self.col_h = collector_helper()
        self.col_h.keep_workload_alive = self.args.keep_workload_alive
        self.col_h.ignore_offset = self.args.ignore_offset
        # self.col_h.offset_metric_file = self.args.offset_metric_file
        self.col_h.pid_ignore_children = self.args.ignore_children
        self.col_h.pid_ignore_threads = self.args.ignore_threads
        self.col_h.flush_limit = self.args.flush_limit
        self.col_h.csv_result = self.args.csv_result
        # get cpu no. or/and NUMA node to run syswit
        self.col_h.get_cpus_for_running_tool(
            self.args.cpu_affinity, self.args.node_affinity
        )
        print("Tool Defined to run on specific cpus:", self.col_h.cpus_to_run_tool)
        if self.args.sample_period != None:
            self.col_h.sample_period = self.args.sample_period
        if self.args.delay_time != None:
            self.col_h.delay_time = int(self.args.delay_time)
        if self.args.output_file_name != None:
            self.col_h.output_file_name = self.args.output_file_name

        self.make_log_directory()
        self.process_pid()

        self.print_info.append("Delay Time: " + str(self.col_h.delay_time))
        self.print_info.append("Sample Period: " + str(self.col_h.sample_period))

        if self.args.nr_samples:
            self.col_h.nr_samples = self.args.nr_samples
        else:
            # if self.col_h.pid = None and self.args.nr_iteration = None;
            # use default self.col_h.nr_samples
            if self.col_h.pid:
                # if collecting process and global data, and nr_samples
                # not provided, giving process alive as precedence
                self.args.nr_samples = None
                self.col_h.nr_samples = None

        if self.col_h.nr_samples:
            self.print_info.append("nr_samples: " + str(self.col_h.nr_samples))
        self.print_info.append(
            "Keep Workload alive: " + str(self.col_h.keep_workload_alive)
        )

        self.print_info.append("No. of NUMA Nodes: " + str(self.col_h.numa_nodes))

        # input from yaml
        if self.args.collector_input_config != config.collector_input_config_path:
            self.col_h.collector_input_config_path = self.args.collector_input_config
        else:
            self.col_h.collector_input_config_path = config.collector_input_config_path
        self.print_info.append(
            "Config File Path: " + self.col_h.collector_input_config_path
        )

        data = parse_yaml_metrics(self.col_h.collector_input_config_path)

        self.parse_yaml_metric_inputs(data)
        self.get_file_paths()
        for i in self.print_info:
            print(i)

        # Start collection
        try:
            self.col_h.collect_n_parse()
        except KeyboardInterrupt:
            self.col_h.run_continue = False
            self.col_h.store_results()
        except Exception as e:
            print(e)
            sys.exit(0)


def main(params=None, *args):
    _collector = collector()
    try:
        _collector.main(params, args)
    except NameError as e:
        _collector.main()


if __name__ == "__main__":
    main()
