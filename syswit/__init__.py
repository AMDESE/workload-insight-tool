#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import os
import pkg_resources

try:
    from numa import info
except ImportError:
    print("Unable to import info please remove numa package")
from syswit.utils import lscpu


class global_vars:
    system_configuration = "system configuration"
    timestamps = "timestamps"
    nr_samples = "nr_samples"
    sample_period = "sample_period"
    all_pids = "all_pids"
    offset = "offset"
    input_yaml = "input_yaml"
    file_type = "file_type"
    offset_value = "offset_value"


class collector_config:
    nr_samples = 10
    sample_period = 5
    delay_time = 0
    flush_counter = 0
    flush_limit = 13545880
    batch_size = 1000
    global_data_required = 0
    logs_d = "logs"
    output_file_name = "results"
    tmpflushdatafilename = "tmpresult_"
    workload_given = False
    keep_workload_alive = False
    pid = None
    ignore_offset = False
    ignore_workload_logs = False
    csv_result = False
    all_metric_tags = "all"
    identifier_proc_files = "proc"
    identifier_sys_numanode_files = "sys"
    identifier_pid_proc_files = "proc"
    timestamps_style = "%Y_%m_%d_%H_%M_%S_%f"
    collector_input_config__path = "collector_configs/input.yaml"
    special_parser_help__path = "tool_configs/special_parser_helper.yaml"
    generic_parser_separators__path = "tool_configs/metric_separator.yaml"

    collector_input_config_path = pkg_resources.resource_filename(
        __name__, collector_input_config__path
    )
    special_parser_help_path = pkg_resources.resource_filename(
        __name__, special_parser_help__path
    )
    generic_parser_separators_path = pkg_resources.resource_filename(
        __name__, generic_parser_separators__path
    )

    # Fetching Number of numa nodes in that SUT
    _lscpu = lscpu()
    numa_nodes = _lscpu["numa_nodes"]
    _cpu_count = os.cpu_count()
    node_cpu_info = (info.numa_hardware_info())["node_cpu_info"]
    cpubind_default = f"0:{_cpu_count}"
    numabind_default = f"0:{numa_nodes}"
    _global_varslist = list(vars(global_vars))
    global_varslist = []
    for i in _global_varslist:
        if not i.startswith("__"):
            global_varslist.append(getattr(global_vars, i))


class results_parser_config:
    Tool_Name = "Workload Insight Tool"
    Tool_Name_small = "SYSWIT"
    header_background_color = "#000000"
    header_text_color = "white"
    background_color = "white"
    xaxisLabel = "time(s)"
    displayModeBar = True
    displaylogo = False
    legendText = False
    legendPosition = True
    textAlign = "center"
    border_width = "3%"
    border_style = "solid"
    border_color = "black"
    sys_config_metrics = [
        "Hostname",
        "Kernel Release",
        "cpu count",
        "NUMA Nodes",
    ]
    graph_config = {
        "displayModeBar": displayModeBar,
        "displaylogo": displaylogo,
        "edits": {"legendText": legendText, "legendPosition": legendPosition},
    }
