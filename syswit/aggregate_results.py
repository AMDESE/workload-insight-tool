#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import os
import json
import csv
import jsonmerge
from syswit.utils import (
    get_first_available_timestamp_forPfiles,
    get_last_available_timestamp_forPfiles,
    check_placeholder,
    check_proc_file_tag,
    check_nodex_sys_source_file_tag,
    check_path_pid_proc_file_tag,
)
from syswit import collector_config as config
from syswit import global_vars


class AggregateResult:
    """
    This class is for aggregating flushed results
    and offsetting data if required dynamically as per
    metric behavior.
    """

    def __init__(self):
        print("\nAggregating Start")
        self.merged_data_raw = {}
        self.path = ""
        self.global_varslist = config.global_varslist

    def reduce_merged_data(self):
        self.merged_data = {}
        missing_sample_back_search_count = (
            len(self.merged_data_raw[global_vars.timestamps]) // 2
        )

        for file_name, metrics_data in self.merged_data_raw.items():
            if file_name not in self.global_varslist:
                if isinstance(metrics_data, list) and isinstance(metrics_data[0], dict):
                    self.merged_data[file_name] = [{}]
                    for _metric in list(self.offset_primary_value[file_name].keys()):
                        self.merged_data[file_name][0][_metric] = []
                    for counter, cur_timestamp in enumerate(
                        self.merged_data_raw[global_vars.timestamps]
                    ):
                        if cur_timestamp in metrics_data[0].keys():
                            for metric, value in metrics_data[0][cur_timestamp][
                                0
                            ].items():
                                self.merged_data[file_name][0][metric].append(value)
                        else:
                            if (
                                self.first_timestamps_lists[file_name] <= cur_timestamp
                                and cur_timestamp
                                <= self.last_timestamps_lists[file_name]
                            ):
                                # Finding placeholder for samples in between collection missing values get prev values
                                prev_timestamp = self.merged_data_raw[
                                    global_vars.timestamps
                                ][counter - 1]
                                if prev_timestamp in metrics_data[0].keys():
                                    for metric, value in metrics_data[0][
                                        prev_timestamp
                                    ][0].items():
                                        self.merged_data[file_name][0][metric].append(
                                            value
                                        )
                                else:
                                    for i in range(2, missing_sample_back_search_count):
                                        prev_timestamp = self.merged_data_raw[
                                            global_vars.timestamps
                                        ][counter - i]
                                        if prev_timestamp in metrics_data[0].keys():
                                            for metric, value in metrics_data[0][
                                                prev_timestamp
                                            ][0].items():
                                                self.merged_data[file_name][0][
                                                    metric
                                                ].append(value)
                                            break

                            else:
                                # Finding placeholder for samples with before and after of real samples collected
                                for metric in list(
                                    self.merged_data[file_name][0].keys()
                                ):
                                    placeholder = check_placeholder(
                                        self.offset_primary_value[file_name][metric]
                                    )
                                    self.merged_data[file_name][0][metric].append(
                                        placeholder
                                    )
            else:
                self.merged_data[file_name] = self.merged_data_raw[file_name]

    def get_initial_value_set(self):
        # Creating list sets of first timestamp available for a metric, first value,
        # and later creating a list of last timestamp available as well.

        self.offset_primary_value = {}
        self.first_timestamps_lists = {}
        self.last_timestamps_lists = {}

        initial_timestamp = self.merged_data_raw[global_vars.timestamps][0]
        for file_name, metrics in self.merged_data_raw.items():
            if file_name not in self.global_varslist:
                if isinstance(metrics, list) and isinstance(metrics[0], dict):
                    try:
                        self.offset_primary_value[file_name] = metrics[0][
                            initial_timestamp
                        ][0]
                        self.first_timestamps_lists[file_name] = initial_timestamp
                        last_timestamp = get_last_available_timestamp_forPfiles(
                            self.merged_data_raw, file_name
                        )
                        self.last_timestamps_lists[file_name] = last_timestamp
                    except KeyError as e:
                        tmp_timestamp = get_first_available_timestamp_forPfiles(
                            self.merged_data_raw, file_name
                        )
                        self.offset_primary_value[file_name] = metrics[0][
                            tmp_timestamp
                        ][0]
                        self.first_timestamps_lists[file_name] = tmp_timestamp
                        last_timestamp = get_last_available_timestamp_forPfiles(
                            self.merged_data_raw, file_name
                        )
                        self.last_timestamps_lists[file_name] = last_timestamp

    def sort_files(self, heads):
        """
        This function is to sort csv headers in a particular pattern
        such that [timestamps, ^proc_*, *_sys_*, ^p_*]
        proc_ -> Global data of proc files
        _sys_ -> Global nodex_sys_source_files
        ^p_   -> Per Process data from proc files

        Args:
            heads (str): this is unsorted list of headers for csv
        return sorted list for headers
        """
        list_proc = []
        list_sys = []
        list_p_proc = []

        for file in heads:
            if check_proc_file_tag(file):
                list_proc.append(file)
            elif check_nodex_sys_source_file_tag(file):
                list_sys.append(file)
            elif check_path_pid_proc_file_tag(file):
                list_p_proc.append(file)

        return list_proc + list_sys + list_p_proc

    def sort_merged_data(self):
        sorted_merged_data_raw = {}
        sorted_timestamps = sorted(self.merged_data_raw[global_vars.timestamps])
        result_elements_tobesorted = (
            []
        )  # These are files which got data collected in time-series
        for i in self.merged_data_raw.keys():
            if (
                check_nodex_sys_source_file_tag(i)
                or check_path_pid_proc_file_tag(i)
                or check_proc_file_tag(i)
            ):
                result_elements_tobesorted.append(i)
            else:
                sorted_merged_data_raw[i] = self.merged_data_raw[i]
        sorted_merged_data_raw[global_vars.timestamps] = sorted_timestamps

        result_elements_tobesorted = self.sort_files(result_elements_tobesorted)
        for file in result_elements_tobesorted:
            sorted_merged_data_raw[file] = [{}]
            for _timestamp in sorted(self.merged_data_raw[file][0]):
                sorted_merged_data_raw[file][0][_timestamp] = self.merged_data_raw[
                    file
                ][0][_timestamp]
        self.merged_data_raw = sorted_merged_data_raw

    def clean_data(self):
        list_of_pids_files_to_remove = []
        for i in self.merged_data_raw.keys():
            if i not in self.global_varslist:
                try:
                    if not self.merged_data_raw[i][0]:
                        list_of_pids_files_to_remove.append(i)
                except TypeError as e:
                    print(e, i, self.merged_data_raw[i])

        for i in list_of_pids_files_to_remove:
            if i in self.merged_data_raw.keys():
                self.merged_data_raw.pop(i)

    def merge_all_result_files_raw(self, _file):
        with open(_file, "r") as f:
            data1 = json.load(f)
        if not self.merged_data_raw:
            self.merged_data_raw = jsonmerge.merge(data1, self.merged_data_raw)
            return
        self.merged_data_raw = jsonmerge.merge(data1, self.merged_data_raw)
        data0_key = self.merged_data_raw.keys()
        data1_key = data1.keys()
        common_keys = data1_key & data0_key
        for i in common_keys:
            if i == global_vars.timestamps or i == global_vars.all_pids:
                self.merged_data_raw[i] = self.merged_data_raw[i] + data1[i]
            else:
                merged_dict = {**self.merged_data_raw[i][0], **data1[i][0]}
                self.merged_data_raw[i][0] = merged_dict

    def read_data(self):
        lists_of_files_at_path = [
            file
            for file in os.listdir(self.path)
            if file.startswith(config.tmpflushdatafilename)
        ]
        for _file in sorted(lists_of_files_at_path):
            self.merge_all_result_files_raw(os.path.join(self.path, _file))
        self.clean_data()
        self.sort_merged_data()
        self.get_initial_value_set()
        self.reduce_merged_data()

    def make_default_offset_metrics_tree(self, data):
        self.default_offset_metrics = {}
        for i, j in data.items():
            tmp = {}
            if isinstance(j, dict):
                for k, m in j.items():
                    tmp[k] = True
            self.default_offset_metrics[i] = tmp

    def check_metric_offsetable_ifstatic(self, values):
        """
        checking if metric is static and returning false for offset if true
        """
        return len(set(values)) == 1

    def check_metric_offsetable(self, values, primary_value):
        if isinstance(values, list):
            if isinstance(primary_value, str) or self.check_metric_offsetable_ifstatic(
                values
            ):
                return False
            else:
                tmp = 0
                for i in values:
                    if isinstance(i, (int, float)):
                        if i == -1:
                            continue
                        elif i - tmp < 0:
                            return False
                    tmp = i
                return True

    def create_offset_data_file(self):
        self.make_default_offset_metrics_tree(self.offset_primary_value)
        for static_metric_key, static_metric_value in self.offset_primary_value.items():
            for _metric, list_of_values in self.merged_data[static_metric_key][
                0
            ].items():
                self.default_offset_metrics[static_metric_key][
                    _metric
                ] = self.check_metric_offsetable(
                    list_of_values,
                    self.offset_primary_value[static_metric_key][_metric],
                )

        file_name = self.path + "/offset.json"
        with open(file_name, "w") as f:
            json.dump(self.default_offset_metrics, f, indent=4)

    def offset_list(self, list_of_values):
        if not list_of_values:
            return list_of_values
        first_element = list_of_values[0]
        return [element - first_element for element in list_of_values]

    def offset_data(self, offset_metric_file=None):
        if offset_metric_file is None:
            self.create_offset_data_file()
        else:
            # TODO.....
            # read_given_file
            self.create_offset_data_file()

        tmp = self.merged_data
        final_path = os.path.join(self.path, "offset_primary.json")
        # self.write_offset_primary_to_file(final_path)
        with open(final_path, "w") as f:
            json.dump(self.offset_primary_value, f, indent=4)
        for static_metric_key, static_metric_value in self.offset_primary_value.items():
            tmp[static_metric_key].append({})
            tmp[static_metric_key][1][global_vars.offset_value] = {}

            for _metric, list_of_values in self.merged_data[static_metric_key][
                0
            ].items():
                if self.default_offset_metrics[static_metric_key][_metric]:
                    tmp[static_metric_key][0][_metric] = self.offset_list(
                        list_of_values
                    )
                    tmp[static_metric_key][1][global_vars.offset_value][
                        _metric
                    ] = self.offset_primary_value[static_metric_key][_metric]

        self.merged_data = tmp

    def write_csv_data(self, data, file_name):
        data_file = open(f"{file_name}.csv", "w")

        csv_writer = csv.writer(data_file)
        heads = []
        for key in data.keys():
            if key not in self.global_varslist:
                heads.append(key)
        heads = self.sort_files(heads)
        headerrow = ["timestamps"]
        for file in heads:
            for metric in data[file][0].keys():
                if metric not in self.global_varslist:
                    headerrow.append(f"{file} {metric}")
        csv_writer.writerow(headerrow)  # Write header to the csv
        headerrow.remove("timestamps")
        for i in range(len(data["timestamps"])):
            row = [data["timestamps"][i]]
            for file in heads:
                for metric in data[file][0].keys():
                    try:
                        row.append(data[file][0][metric][i])
                    except IndexError as e:
                        if isinstance(data[file][0][metric][0], int):
                            row.append(0)
                        else:
                            row.append("NA")

            csv_writer.writerow(row)  # Writing data of every sample time

        data_file.close()

    def convert_jsontocsv(self, jsonfile):
        """
        This function can be used to convert a json to csv

        Args:
            jsonfile (str): pass path to result json file
                                which needs to be converted to csv
        """

        if os.path.exists(jsonfile):
            file_name = jsonfile.replace(".json", "")
            with open(jsonfile, "r") as f:
                jsondata = json.loads(f.read())
                self.write_csv_data(data=jsondata, file_name=file_name)

    def write_merged_data_to_file(self, file_name):
        with open(f"{file_name}.json", "w") as f:
            json.dump(self.merged_data, f, indent=4)

    def remove_all_temp_result_files(self):
        for file in os.listdir(self.path):
            if file.startswith(config.tmpflushdatafilename):
                os.remove(os.path.join(self.path, file))
