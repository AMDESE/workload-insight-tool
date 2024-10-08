#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


from dash import Dash, html, dcc, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
from syswit.utils import get_IPaddr, get_port
from syswit.result_parser import result_parser_helper
import argparse
import logging
from syswit import global_vars, results_parser_config
import sys


class Analyzer:
    """
    This module is used to view/analyze results collected by SYSWIT collector.
    """

    def __init__(self):
        log = logging.getLogger("werkzeug")
        log.disabled = True
        self.proc = {}
        self.sys = {}
        self.p_proc = {}
        self.sys_details_print = {}
        self.tool_config_metrics = [global_vars.sample_period]
        self.tool_details_print = {}
        self.name = "Analyzer"
        self.data = result_parser_helper()

    def add_arguments(self, parser=None):
        if parser is None:
            parser = argparse.ArgumentParser(
                description="E.g., python3 analyzer.py -f '/logs/results.json' ",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
        parser.add_argument("-f", "--file", type=str, help="Path to results(json) file")
        return parser

    def process_arguments(self, params):
        parser = self.add_arguments()

        if params is None:
            self.args = parser.parse_args()
        else:
            self.args = params

    def main(self, params=None, *args):
        """
        This takes care of handling UI for Analyzer, parsing results from
        input file, callbacks for updating graphs.
        """
        self.process_arguments(params)
        self.file = self.args.file
        self.data.read_json(self.file)
        color = {"backgroundcolor": results_parser_config.background_color}
        display_graph_count = 0

        # check for which source data is enabled in collection and show graphs accordingly
        if not self.data.pids_enable:
            self.data.result_tags_p_files["NA"] = "NA"

        self.data.result_tags_g_source_files_proc_enable = False
        self.data.result_tags_g_source_files_nodex_sys_enable = False

        if self.data.result_tags_g_source_files_proc == {}:
            self.data.result_tags_g_source_files_proc_enable = False
            self.data.result_tags_g_source_files_proc["NA"] = "'NA"
        else:
            self.data.result_tags_g_source_files_proc_enable = True
            display_graph_count = display_graph_count + 1

        if self.data.result_tags_g_source_files_nodex_sys == {}:
            self.data.result_tags_g_source_files_nodex_sys_enable = False
            self.data.result_tags_g_source_files_nodex_sys["NA"] = "'NA"
        else:
            self.data.result_tags_g_source_files_nodex_sys_enable = True
            display_graph_count = display_graph_count + 1

        for i in results_parser_config.sys_config_metrics:
            self.sys_details_print[i] = self.data.system_configuration[i]
        self.sample_period = self.data.df[global_vars.sample_period][0]
        self.tool_details_print[f"{global_vars.sample_period}(s)"] = self.sample_period

        if self.data.pids_enable:
            self.tool_details_print["Parent PID"] = self.data.df[global_vars.all_pids][
                0
            ][0]
            display_graph_count = display_graph_count + 1
        else:
            try:
                self.tool_details_print[global_vars.nr_samples] = self.data.df[
                    global_vars.nr_samples
                ][0]
            except Exception as e:
                pass

        self.tool_details_print["Result File Path"] = self.file

        for key, value in self.tool_details_print.items():
            print(f"{key}: {value}")

        if display_graph_count == 1:
            self.graph_height = "85%"
        elif display_graph_count == 2:
            self.graph_height = "45%"
        elif display_graph_count == 3:
            self.graph_height = "31%"
        elif display_graph_count == 0:
            print("No graphs to be displayed, verify the results logs")
            sys.exit(0)

        self.app = Dash(self.name, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.app.config.suppress_callback_exceptions = True
        self.app.title = f"{results_parser_config.Tool_Name_small} {self.name}"
        self.app.layout = html.Div(
            [
                html.H1(
                    children=results_parser_config.Tool_Name,
                    style={
                        "textAlign": results_parser_config.textAlign,
                        "background-color": results_parser_config.header_background_color,
                        "border-width": results_parser_config.border_width,
                        "border-style": results_parser_config.border_style,
                        "border-color": results_parser_config.border_color,
                        "color": results_parser_config.header_text_color,
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H4("System Details"),
                                        html.Table(
                                            [
                                                html.Td(
                                                    [
                                                        html.Tr(col)
                                                        for col in self.sys_details_print.keys()
                                                    ]
                                                )
                                            ]
                                            + [
                                                html.Td(
                                                    [
                                                        html.Tr(
                                                            self.sys_details_print[col]
                                                        )
                                                        for col in self.sys_details_print.keys()
                                                    ]
                                                )
                                            ],
                                            style={
                                                "font-weight": "bold",
                                                "padding": "10px",
                                                "border-collapse": "separate",
                                                "border-spacing": "2px",
                                            },
                                        ),
                                        html.Br(),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.H4(children="Tool Details"),
                                        html.Table(
                                            [
                                                html.Td(
                                                    [
                                                        html.Tr(col)
                                                        for col in self.tool_details_print.keys()
                                                    ]
                                                )
                                            ]
                                            + [
                                                html.Td(
                                                    [
                                                        html.Tr(
                                                            self.tool_details_print[
                                                                col
                                                            ],
                                                            style={
                                                                "word-wrap": "break-word"
                                                            },
                                                        )
                                                        for col in self.tool_details_print.keys()
                                                    ],
                                                    style={"word-wrap": "break-word"},
                                                )
                                            ],
                                            style={
                                                "font-weight": "bold",
                                                "border-spacing": "2px",
                                                "padding-right": "50px",
                                            },
                                        ),
                                        html.Br(),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.H4(children="Select Graph Input"),
                                        html.Div(
                                            [
                                                html.H5(
                                                    children="Global /proc/(*) data"
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_proc",
                                                    options=list(
                                                        self.data.result_tags_g_source_files_proc.keys()
                                                    ),
                                                    value=[
                                                        list(
                                                            self.data.result_tags_g_source_files_proc.keys()
                                                        )[0]
                                                    ],
                                                    multi=True,
                                                    maxHeight=300,
                                                    clearable=False,
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_proc_metrics",
                                                    multi=True,
                                                    placeholder="Select metrics for above tags",
                                                    style={
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ]
                                                    },
                                                    clearable=False,
                                                ),
                                                html.Br(),
                                            ],
                                            style={
                                                "display": (
                                                    "none"
                                                    if not self.data.result_tags_g_source_files_proc_enable
                                                    else "block"
                                                ),
                                                "backgroundColor": color[
                                                    "backgroundcolor"
                                                ],
                                            },
                                        ),
                                        html.Div(
                                            [
                                                html.H5(children="nodeX/sys/(*) data"),
                                                dcc.Dropdown(
                                                    id="tag_sys",
                                                    options=list(
                                                        self.data.result_tags_g_source_files_nodex_sys.keys()
                                                    ),
                                                    value=[
                                                        list(
                                                            self.data.result_tags_g_source_files_nodex_sys.keys()
                                                        )[0]
                                                    ],
                                                    multi=True,
                                                    maxHeight=300,
                                                    clearable=False,
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_sys_metrics",
                                                    multi=True,
                                                    maxHeight=300,
                                                    placeholder="Select metrics for above tags",
                                                    style={
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ]
                                                    },
                                                    clearable=False,
                                                ),
                                                html.Br(),
                                            ],
                                            style={
                                                "display": (
                                                    "none"
                                                    if not self.data.result_tags_g_source_files_nodex_sys_enable
                                                    else "block"
                                                ),
                                                "backgroundColor": color[
                                                    "backgroundcolor"
                                                ],
                                            },
                                        ),
                                        html.Div(
                                            [
                                                html.H5(
                                                    children="/proc/<pid>/(*) data"
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_p_proc",
                                                    options=list(
                                                        self.data.result_tags_p_files.keys()
                                                    ),
                                                    value=[
                                                        list(
                                                            self.data.result_tags_p_files.keys()
                                                        )[0]
                                                    ],
                                                    multi=True,
                                                    maxHeight=300,
                                                    style={
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ]
                                                    },
                                                    clearable=False,
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_p_proc_metrics",
                                                    multi=True,
                                                    maxHeight=300,
                                                    placeholder="Select metrics for above tags",
                                                    style={
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ]
                                                    },
                                                    clearable=False,
                                                ),
                                                html.Br(),
                                            ],
                                            style={
                                                "display": (
                                                    "none"
                                                    if not self.data.pids_enable
                                                    else "block"
                                                ),
                                                "backgroundColor": color[
                                                    "backgroundcolor"
                                                ],
                                            },
                                        ),
                                    ]
                                ),
                            ],
                            style={
                                "width": "20%",
                                "padding-left": "30px",
                                "padding-right": "30px",
                            },
                        ),
                        html.Div(
                            [
                                html.H4(
                                    children="Global data /proc/(*)",
                                    style={
                                        "textAlign": results_parser_config.textAlign,
                                        "display": (
                                            "none"
                                            if not self.data.result_tags_g_source_files_proc_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                dcc.Graph(
                                    id="graph_proc",
                                    config=results_parser_config.graph_config,
                                    style={
                                        "display": (
                                            "none"
                                            if not self.data.result_tags_g_source_files_proc_enable
                                            else "block"
                                        ),
                                        "width": "90%",
                                        "height": self.graph_height,
                                        "backgroundColor": color["backgroundcolor"],
                                    },
                                ),
                                html.H4(
                                    children="Global NUMA node data nodeX/sys/(*)",
                                    style={
                                        "textAlign": results_parser_config.textAlign,
                                        "display": (
                                            "none"
                                            if not self.data.result_tags_g_source_files_nodex_sys_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                dcc.Graph(
                                    id="graph_sys",
                                    config=results_parser_config.graph_config,
                                    style={
                                        "display": (
                                            "none"
                                            if not self.data.result_tags_g_source_files_nodex_sys_enable
                                            else "block"
                                        ),
                                        "width": "90%",
                                        "height": self.graph_height,
                                        "backgroundColor": color["backgroundcolor"],
                                    },
                                ),
                                html.H4(
                                    children="Pid data /proc/<pid>/(*)",
                                    style={
                                        "textAlign": results_parser_config.textAlign,
                                        "display": (
                                            "none"
                                            if not self.data.pids_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                dcc.Graph(
                                    id="graph_p_proc",
                                    config=results_parser_config.graph_config,
                                    style={
                                        "display": (
                                            "none"
                                            if not self.data.pids_enable
                                            else "block"
                                        ),
                                        "width": "90%",
                                        "height": self.graph_height,
                                        "backgroundColor": "",
                                    },
                                ),
                            ],
                            style={"flex-grow": "1"},
                        ),
                    ],
                    style={"display": "flex", "height": "100%"},
                ),
            ],
            style={"backgroundColor": color["backgroundcolor"]},
        )
        output_callback_list = [
            Output("graph_proc", "figure"),
            Output("graph_sys", "figure"),
        ]
        input_callback_list = []

        if self.data.pids_enable:
            output_callback_list.append(Output("graph_p_proc", "figure"))
            input_callback_list.append(Input("tag_p_proc", "value"))
        input_callback_list.extend(
            [Input("tag_sys", "value"), Input("tag_proc", "value")]
        )
        if self.data.pids_enable:
            input_callback_list.append(Input("tag_p_proc_metrics", "value"))
        input_callback_list.extend(
            [Input("tag_sys_metrics", "value"), Input("tag_proc_metrics", "value")]
        )

        @self.app.callback(
            [
                Output("tag_proc_metrics", "options"),
                Output("tag_sys_metrics", "options"),
                Output("tag_p_proc_metrics", "options"),
            ],
            [
                Input("tag_proc", "value"),
                Input("tag_sys", "value"),
                Input("tag_p_proc", "value"),
            ],
        )
        def update_dropdown(tag_proc, tag_sys, tag_p_proc):
            tag_proc_list = []
            for j in tag_proc:
                for i in self.data.result_tags_g_source_files_proc[j]:
                    tag_proc_list.append(i)

            tag_sys_list = []
            for j in tag_sys:
                for i in self.data.result_tags_g_source_files_nodex_sys[j]:
                    tag_sys_list.append(i)
            tag_p_proc_list = []
            for j in tag_p_proc:
                for i in self.data.result_tags_p_files[j]:
                    tag_p_proc_list.append(i)

            return tag_proc_list, tag_sys_list, tag_p_proc_list

        @self.app.callback(output=output_callback_list, inputs=input_callback_list)
        def update_line_chart(
            tag_p_proc="NA",
            tag_sys="NA",
            tag_proc="NA",
            tag_p_proc_metrics="NA",
            tag_sys_metrics="NA",
            tag_proc_metrics="NA",
        ):
            if not self.data.pids_enable:
                tag_sys_metrics = tag_proc
                tag_proc = tag_sys
                tag_sys = tag_p_proc
                tag_proc_metrics = tag_p_proc_metrics
                tag_p_proc = "NA"
                tag_p_proc_metrics = "NA"

            _time = []
            for i in range(0, len(self.data.timestamps)):
                value = int(i * self.sample_period)
                _time.append(value)

            metric_list_proc = []
            metric_list_sys = []
            metric_list_p_proc = []
            self.proc[global_vars.timestamps] = _time
            self.sys[global_vars.timestamps] = _time
            self.p_proc[global_vars.timestamps] = _time

            title_tag_proc = ""
            for _tag in tag_proc:
                title_tag_proc = title_tag_proc + " " + str(_tag)
                if tag_proc_metrics != None:
                    for metric in tag_proc_metrics:
                        if (
                            metric
                            in self.data.result_tags_g_source_files_proc[_tag].keys()
                        ):
                            self.data.get_metric_values_g_source_files_proc(
                                _tag, metric
                            )
                            self.proc[
                                metric
                            ] = self.data.result_tags_g_source_files_proc[_tag][metric]
                            metric_list_proc.append(metric)
            try:
                fig1 = px.line(
                    self.proc,
                    x=global_vars.timestamps,
                    y=metric_list_proc,
                    labels={
                        global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                    },
                ).update_layout(
                    title=title_tag_proc,
                    hovermode="x",
                    legend=dict(y=-0.5, x=0),
                )
                fig1.update_traces(legendwidth=1000)
            except ValueError as e:
                print("Selected Values of different datatypes")
                metric_list_proc.pop()
                fig1 = px.line(
                    self.proc,
                    x=global_vars.timestamps,
                    y=metric_list_proc,
                    labels={
                        global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                    },
                ).update_layout(
                    title=title_tag_proc,
                    hovermode="x",
                    legend=dict(y=-0.5, x=0),
                )
                fig1.update_traces(legendwidth=1000)
            except Exception as e:
                pass

            title_tag_sys = ""
            for _tag in tag_sys:
                title_tag_sys = title_tag_sys + " " + str(_tag)
                if tag_sys_metrics != None:
                    for metric in tag_sys_metrics:
                        if (
                            metric
                            in self.data.result_tags_g_source_files_nodex_sys[
                                _tag
                            ].keys()
                        ):
                            self.data.get_metric_values_g_source_files_nodex_sys(
                                _tag, metric
                            )
                            self.sys[
                                metric
                            ] = self.data.result_tags_g_source_files_nodex_sys[_tag][
                                metric
                            ]
                            metric_list_sys.append(metric)
            try:
                fig2 = px.line(
                    self.sys,
                    x=global_vars.timestamps,
                    y=metric_list_sys,
                    labels={
                        global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                    },
                ).update_layout(
                    title=title_tag_sys, hovermode="x", legend=dict(y=-0.5, x=0)
                )
                fig2.update_traces(legendwidth=1000)
            except ValueError as e:
                print("Selected Values of different datatypes")
                metric_list_sys.pop()
                fig2 = px.line(
                    self.sys,
                    x=global_vars.timestamps,
                    y=metric_list_sys,
                    labels={
                        global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                    },
                ).update_layout(
                    title=title_tag_sys, hovermode="x", legend=dict(y=-0.5, x=0)
                )
                fig2.update_traces(legendwidth=1000)
            except Exception as e:
                pass

            if self.data.pids_enable:
                title_tag_p_proc = ""
                if tag_p_proc_metrics != None:
                    for _tag in tag_p_proc:
                        title_tag_p_proc = title_tag_p_proc + " " + str(_tag)
                        for metric in tag_p_proc_metrics:
                            if metric in self.data.result_tags_p_files[_tag].keys():
                                self.data.get_metric_values_p_files(_tag, metric)
                                self.p_proc[metric] = self.data.result_tags_p_files[
                                    _tag
                                ][metric]
                                metric_list_p_proc.append(metric)
                try:
                    fig3 = px.line(
                        self.p_proc,
                        x=global_vars.timestamps,
                        y=metric_list_p_proc,
                        labels={
                            global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                        },
                    ).update_layout(
                        title=title_tag_p_proc,
                        hovermode="x",
                        legend=dict(y=-0.5, x=0),
                    )
                    fig3.update_traces(legendwidth=1000)
                except ValueError as e:
                    print("Selected Values of different datatypes")
                    metric_list_p_proc.pop()
                    try:

                        fig3 = px.line(
                            self.p_proc,
                            x=global_vars.timestamps,
                            y=metric_list_p_proc,
                            labels={
                                global_vars.timestamps: f"{results_parser_config.xaxisLabel}"
                            },
                        ).update_layout(
                            title=title_tag_p_proc,
                            hovermode="x",
                            legend=dict(y=-0.5, x=0),
                        )
                        fig3.update_traces(legendwidth=1000)
                    except Exception as e:
                        pass

                except Exception as e:
                    pass

            if self.data.pids_enable:
                return fig1, fig2, fig3
            else:
                return fig1, fig2

        public_ip = get_IPaddr()
        port = get_port(public_ip)
        self.app.run_server(host=public_ip, port=port, debug=False)


def main(params=None, *args):
    analyzer = Analyzer()
    try:
        analyzer.main(params, args)
    except NameError as e:
        analyzer.main()


if __name__ == "__main__":
    main()
