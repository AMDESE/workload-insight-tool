#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import pandas as pd
import json
import datetime
from syswit.utils import (
    check_proc_file_tag,
    check_path_pid_proc_file_tag,
    check_nodex_sys_source_file_tag,
)
from syswit import collector_config as config, global_vars


class result_parser_helper:
    def __init__(self):
        (
            self.timestamps,
            self.all_pids,
            self._g_source_files_proc,
            self._g_source_files_nodex_sys,
            self.p_files,
        ) = ([], [], [], [], [])

        self.pids_enable = False
        self.hugepages = dict()
        self.hugepages["size"] = ["1048576kB", "2048kB"]
        self.hugepages["files"] = [
            "nr_hugepages",
            "surplus_hugepages",
            "free_hugepages",
        ]
        self.system_configuration = {}
        self.read_results_json_tags = {
            global_vars.timestamps: self.timestamps,
            global_vars.all_pids: self.all_pids,
        }

    def get_current_time(self):
        current_datetime = datetime.datetime.now().strftime(config.timestamps_style)
        str_current_datetime = str(current_datetime)
        print(str_current_datetime)

    def get_system_configuration_data(self):
        system_configuration_keys = [
            "cpu count",
            "NUMA Nodes",
            "Operating System",
            "Hostname",
            "Kernel Release",
            "Python Version",
            "Processor Architecture",
            "Cpu Type",
            "Network interfaces",
        ]

        for keys in system_configuration_keys:
            self.system_configuration[keys] = self.df[global_vars.system_configuration][
                0
            ][0][keys]

    def get_results_json_tags(self):
        p_files = []
        for key in self.read_results_json_tags:
            if key == global_vars.all_pids:
                dfkeyslist = list(self.df.keys())
                for i in dfkeyslist:
                    if "_proc_" in i:
                        p_files.append(i)
                if key in self.df and len(p_files) > 0:
                    self.pids_enable = True
                else:
                    continue

            for i in self.df[key][0]:
                self.read_results_json_tags[key].append(i)

    def get_results_json_tags_metrics(self):
        for tag in self.result_tags_g_source_files_proc.keys():
            for key in self._g_source_files_proc:
                if key in tag:
                    for i in list(self.df[tag][0][0].keys()):
                        self.result_tags_g_source_files_proc[tag][i] = []
        for tag in self.result_tags_g_source_files_nodex_sys.keys():
            for key in self._g_source_files_nodex_sys:
                if key in tag:
                    for i in list(self.df[tag][0][0].keys()):
                        self.result_tags_g_source_files_nodex_sys[tag][i] = []
        if self.pids_enable:
            for tag in self.result_tags_p_files.keys():
                for key in self.p_files:
                    if key in tag:
                        for i in list(self.df[tag][0][0].keys()):
                            self.result_tags_p_files[tag][i] = []

    def get_metric_values_g_source_files_proc(self, tag, metric):
        self.result_tags_g_source_files_proc[tag][metric] = self.df[tag][0][0][metric]

    def get_metric_values_g_source_files_nodex_sys(self, tag, metric):
        self.result_tags_g_source_files_nodex_sys[tag][metric] = self.df[tag][0][0][
            metric
        ]

    def get_metric_values_p_files(self, tag, metric):
        self.result_tags_p_files[tag][metric] = self.df[tag][0][0][metric]

    def read_json(self, file_name):
        try:
            with open(file_name, "r") as f:
                self.df = pd.json_normalize(json.loads(f.read()))
        except FileNotFoundError:
            print(f"File Not Found {file_name}")
            exit()

        self.get_system_configuration_data()
        self.get_results_json_tags()
        self.result_tags, self.result_tags_hugepages = [], []
        (
            self.result_tags_g_source_files_proc,
            self.result_tags_g_source_files_nodex_sys,
            self.result_tags_p_files,
        ) = ({}, {}, {})

        for key in self.df:
            tmp = key.split("_")
            if check_proc_file_tag(key):
                if key not in self._g_source_files_proc:
                    self._g_source_files_proc.append(key)
            elif check_nodex_sys_source_file_tag(key):
                filename = "_" + tmp[1] + "_" + tmp[2]
                if filename not in self._g_source_files_nodex_sys:
                    self._g_source_files_nodex_sys.append(filename)
            elif check_path_pid_proc_file_tag(key):
                filename = "_" + tmp[1] + "_" + tmp[2]
                if filename not in self.p_files:
                    self.p_files.append(filename)

        for key in self.df:
            if key not in config.global_varslist and key not in self.result_tags:
                self.result_tags.append(key)
                for file in self._g_source_files_proc:
                    if file in key and key not in self.result_tags_g_source_files_proc:
                        if "_proc_stat" not in key:
                            self.result_tags_g_source_files_proc[key] = {}
                for file in self._g_source_files_nodex_sys:
                    if (
                        file in key
                        and key not in self.result_tags_g_source_files_nodex_sys
                    ):
                        self.result_tags_g_source_files_nodex_sys[key] = {}
                for file in self.p_files:
                    if file in key and key not in self.result_tags_p_files:
                        self.result_tags_p_files[key] = {}
                for file in self.hugepages["files"]:
                    if file in key:
                        self.result_tags_hugepages.append(key)
        self.get_results_json_tags_metrics()
