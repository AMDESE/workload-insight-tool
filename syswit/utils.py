#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


import os
import subprocess
import psutil
from datetime import datetime
import datetime as ds
import socket
import errno
import yaml
from yaml.loader import SafeLoader
import json


def lscpu():
    output = os.popen("lscpu").read()
    res = {}
    for line in output.split("\n"):
        if "NUMA node(s):" in line:
            res["numa_nodes"] = int(line.split(":")[1].strip())
    return res


def run_cmd_and_get_pid(cmd):
    """
    Run command and return with a valid pid
    else return -1
    """
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        # Wait for the new process to start and get its PID.
        proc.poll()
        pid = proc.pid
        parent = psutil.Process(pid)
        children = parent.children()
        pid = children[0].pid
        # Return the PID of the new process.
        return pid
    except Exception as e:
        print(e)
        return -1


def run(cmd):
    print("Running:", {cmd})
    ret = os.system(cmd)
    if ret < 0:
        print({cmd}, "could not run returned", {ret})
        return -1
    return 0


def timestamp_to_seconds(timestamp):
    from syswit import collector_config as config

    return datetime.strptime(timestamp, config.timestamps_style).timestamp()


def get_current_time():
    from syswit import collector_config as config

    current_datetime = ds.datetime.now().strftime(config.timestamps_style)
    str_current_datetime = str(current_datetime)
    print(str_current_datetime)


def generic_yaml_parser(config_file_path):
    if config_file_path:
        try:
            with open(config_file_path) as f:
                _data = yaml.load(f, Loader=SafeLoader)
            return _data
        except FileNotFoundError:
            print("***File not Found")
            return False
    else:
        return False


def parse_yaml_metrics(config_file_path):
    __data = generic_yaml_parser(config_file_path)

    def _parse(_data):
        data = {}
        if _data:
            for metric, values in _data.items():
                # 'hugepages': [{'size': None}, {'files': None}]
                if metric == "hugepages":
                    if values is not None:
                        if type(values) is list:
                            data["hugepages"] = {}
                            for _ in values:
                                data["hugepages"].update(_)
                    else:
                        data[metric] = None
                elif type(values) is list:
                    for _metric, _values in values[0].items():
                        if _values is not None:
                            data[metric] = [item.strip() for item in _values.split(",")]
                        else:
                            data[metric] = None
                elif metric == "filters":
                    if values is not None:
                        kk = values.split(",")
                        data[metric] = [item.strip() for item in kk]
                    else:
                        data[metric] = None
                elif type(values) is dict:
                    data[metric] = _parse(values)
            return data
        else:
            return False

    return _parse(__data)


def path_nodex_sys_source_file(numa_node, file_name):
    return os.path.join(
        "/sys/devices/system/node/node" + str(numa_node), file_name
    ).strip()


def tag_nodex_sys_source_file(numa_node, file_name):
    return "node" + str(numa_node) + "_sys_" + file_name


def check_nodex_sys_source_file_tag(key):
    from syswit import collector_config as config

    tmp = key.split("_")
    if len(tmp) == 3:
        if "node" in tmp[0] and config.identifier_sys_numanode_files in tmp[1]:
            return True
    return False


def path_nodex_sys_hugepages(numa_node, file_name, size):
    return os.path.join(
        "/sys/devices/system/node/node" + str(numa_node),
        "hugepages/hugepages-" + size,
        file_name,
    ).strip()


def tag_nodex_sys_hugepages(numa_node, file_name, size):
    return "numa" + str(numa_node) + "_sys_" + file_name + "_" + size


def path_proc_file(key):
    path = ""
    for i in key.split("_"):
        path += "/" + i
    return path


def tag_proc_file(files):
    temp = files.split("/")
    _tag = temp[1] + "_" + temp[2]
    return _tag


def check_proc_file_tag(key):
    from syswit import collector_config as config

    tmp = key.split("_")
    if len(tmp) == 2:
        if tmp[0] == config.identifier_proc_files:
            return True
    return False


def path_pid_proc_file(prepend, pid, file_name):
    return os.path.join(" ", prepend, str(pid), file_name).strip()


def tag_pid_proc_file(prepend, pid, file_name):
    return str(pid) + "_" + prepend + "_" + file_name


def check_path_pid_proc_file_tag(key):
    from syswit import collector_config as config

    tmp = key.split("_")
    if len(tmp) == 3:
        if tmp[0].isdigit() and config.identifier_pid_proc_files in tmp[1]:
            return True
    return False


def write_json_to_file(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def get_first_available_timestamp_forPfiles(data, tag):
    try:
        return list(data[tag][0].keys())[0]
    except (IndexError, KeyError, AttributeError) as e:
        try:
            return list(data[tag][0][0].keys())[0]
        except (IndexError, KeyError) as e:
            return False


def get_last_available_timestamp_forPfiles(data, tag):
    try:
        return list(data[tag][0].keys())[-1]
    except (IndexError, KeyError, AttributeError) as e:
        try:
            return list(data[tag][0][0].keys())[-1]
        except (IndexError, KeyError) as e:
            return False


def check_placeholder(_input):
    """
    @params _input: list
    check for placeholder in a _input list
    if str: "NA"
    if float: 0.0
    if int: 0
    """
    if isinstance(_input, list):
        sample = _input[0]
    else:
        sample = _input
    if isinstance(sample, str):
        placeholder = "NA"
    elif isinstance(sample, float):
        placeholder = 0.0
    elif isinstance(sample, int):
        placeholder = 0
    return placeholder


def check_tool_cpus_util(cpus_to_run_tool):
    per_cpu_utlization = psutil.cpu_percent(percpu=True)
    totalutil = 0
    for i in cpus_to_run_tool:
        totalutil = totalutil + per_cpu_utlization[i]
    return int(totalutil / len(cpus_to_run_tool))


def get_IPaddr():
    """
    Get Public IP Address of system, if not possible return with localhost
    IP Address.
    """
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        if result.returncode == 0:
            ip_addresses = [ip for ip in result.stdout.split() if ip.strip()]
            return ip_addresses[0]
        else:
            public_ip = socket.gethostbyname(socket.gethostname())
            return public_ip
    except Exception as e:
        print("Error:", e)


def get_port(public_ip, port=8050):
    """
    check if default port is available, if not give next available port
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((public_ip, port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            print("Port is already in use", port)
            port = port + 1
            get_port(public_ip, port)
        else:
            print(e)
            print(f"****Port: {port} cannot be acessed****")
            return False
    s.close()
    return port


def make_list_of_given_size(input_list, max_length):
    placeholder = check_placeholder(input_list)
    input_list.extend([placeholder] * (max_length - len(input_list)))
    return input_list
