#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>


from dash import Dash, html, dcc, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
from syswit.utils import get_IPaddr, get_port, make_list_of_given_size
from syswit.result_parser import result_parser_helper
import argparse
import sys
import logging
from syswit import global_vars, results_parser_config


class comparator:
    """
    This module is used to view/compare multiple results collected by
    SYSWIT collector.
    """

    def __init__(self):
        log = logging.getLogger("werkzeug")
        log.disabled = True
        self.graph_height = "47%"
        self.name = "Comparator"

    def check_comparator_compatibility(self, timestamps_count, sampling_period, n):
        for i in range(1, n):
            if (
                sampling_period
                != getattr(self, "r" + str(i) + "_data").df[global_vars.sample_period][
                    0
                ]
            ):
                print(global_vars.sample_period, sampling_period)
                print(
                    getattr(self, "r" + str(i) + "_data").df[global_vars.sample_period][
                        0
                    ]
                )
                sys.exit(f"Sampling Period not equal check file number {i}")

    def add_arguments(self, parser=None):
        if parser is None:
            parser = argparse.ArgumentParser(
                description="E.g., python3 comparator.py -f '/logs/results1.json, /logs/results2.json'",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
        parser.add_argument(
            "-f",
            "--files",
            type=str,
            help="Path to results(json) of runs for comparison separated by `,`",
        )
        return parser

    def process_arguments(self, params):
        parser = self.add_arguments()

        if params is None:
            self.args = parser.parse_args()
        else:
            self.args = params

    def main(self, params=None, *args):
        """
        This takes care of handling UI for Comparator, parsing results from
        input file, callbacks for updating graphs.
        """
        self.process_arguments(params)

        if self.args.files is None:
            sys.exit(f"No input files provided")
        files = self.args.files.split(",")

        if len(files) < 2:
            sys.exit(f"less than two paths provided, can't run comparator")
        else:
            files_count = len(files)

        for i, path in enumerate(files):
            files[i] = path.strip()

        for i in range(1, files_count + 1):
            print(f"file {i}: {files[i-1]}")
            setattr(self, "r" + str(i) + "_tool_details_print", {})
            setattr(self, "r" + str(i) + "_sys_details_print", {})
            setattr(self, "r" + str(i) + "_proc", {})
            setattr(self, "r" + str(i) + "_sys", {})
            setattr(self, "r" + str(i) + "_file_path", files[i - 1])
            setattr(self, "r" + str(i) + "_data", result_parser_helper())
            getattr(self, "r" + str(i) + "_data").read_json(files[i - 1])

            for j in results_parser_config.sys_config_metrics:
                getattr(self, "r" + str(i) + "_sys_details_print")[j] = getattr(
                    self, "r" + str(i) + "_data"
                ).system_configuration[j]

            getattr(self, "r" + str(i) + "_tool_details_print")[
                f"{global_vars.sample_period}(s)"
            ] = getattr(self, "r" + str(i) + "_data").df[global_vars.sample_period][0]
            try:
                getattr(self, "r" + str(i) + "_tool_details_print")[
                    global_vars.nr_samples
                ] = getattr(self, "r" + str(i) + "_data").df[global_vars.nr_samples][0]
            except:
                getattr(self, "r" + str(i) + "_tool_details_print")[
                    "Parent PID"
                ] = getattr(self, "r" + str(i) + "_data").df[global_vars.all_pids][0][0]
            for _key, _value in getattr(
                self, "r" + str(i) + "_tool_details_print"
            ).items():
                print(f"{_key}: {_value}")

        first_file_timestamps_count = getattr(self, "r1_data").df[
            global_vars.timestamps
        ][0]
        self.sample_period = getattr(self, "r1_data").df[global_vars.sample_period][0]
        first_file_sampling_period_count = self.sample_period
        self.check_comparator_compatibility(
            first_file_timestamps_count,
            first_file_sampling_period_count,
            files_count + 1,
        )
        color = {"backgroundcolor": results_parser_config.background_color}

        # check for which source data is enabled in collection and show graphs accordingly
        self.r1_data.result_tags_g_source_files_proc_enable = False
        self.r1_data.result_tags_g_source_files_nodex_sys_enable = False
        display_graph_count = 0

        if self.r1_data.result_tags_g_source_files_proc == {}:
            self.r1_data.result_tags_g_source_files_proc_enable = False
            self.r1_data.result_tags_g_source_files_proc["NA"] = "'NA"
        else:
            self.r1_data.result_tags_g_source_files_proc_enable = True
            display_graph_count = display_graph_count + 1

        if self.r1_data.result_tags_g_source_files_nodex_sys == {}:
            self.r1_data.result_tags_g_source_files_nodex_sys_enable = False
            self.r1_data.result_tags_g_source_files_nodex_sys["NA"] = "'NA"
        else:
            self.r1_data.result_tags_g_source_files_nodex_sys_enable = True
            display_graph_count = display_graph_count + 1

        if display_graph_count == 1:
            self.graph_height = "85%"
        elif display_graph_count == 2:
            self.graph_height = "47%"
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
                                html.Table(
                                    [
                                        html.Tr(
                                            " System Details",
                                            style={
                                                "border": "1px solid black",
                                            },
                                        ),
                                        *[
                                            html.Tr(
                                                [
                                                    html.Td(
                                                        f"System {coll}",
                                                        style={
                                                            "border": "1px solid black",
                                                        },
                                                    ),
                                                    *[
                                                        html.Td(
                                                            [
                                                                html.P(col),
                                                                html.P(
                                                                    getattr(
                                                                        self,
                                                                        "r"
                                                                        + str(coll)
                                                                        + "_sys_details_print",
                                                                    )[col]
                                                                ),
                                                            ],
                                                            style={
                                                                "border": "1px solid black",
                                                            },
                                                        )
                                                        for col in getattr(
                                                            self,
                                                            "r"
                                                            + str(coll)
                                                            + "_sys_details_print",
                                                        ).keys()
                                                    ],
                                                ],
                                                style={"border-spacing": "1px"},
                                            )
                                            for coll in range(1, len(files) + 1)
                                        ],
                                    ]
                                ),
                                html.P(),
                                html.Table(
                                    [
                                        html.Tr(
                                            "Tool Details",
                                            style={
                                                "border": "1px solid black",
                                            },
                                        ),
                                        *[
                                            html.Tr(
                                                [
                                                    html.Td(
                                                        f"System {coll}",
                                                        style={
                                                            "border": "1px solid black",
                                                        },
                                                    ),
                                                    *[
                                                        html.Td(
                                                            [
                                                                html.P(col),
                                                                html.P(
                                                                    getattr(
                                                                        self,
                                                                        "r"
                                                                        + str(coll)
                                                                        + "_tool_details_print",
                                                                    )[col]
                                                                ),
                                                            ],
                                                            style={
                                                                "border": "1px solid black",
                                                            },
                                                        )
                                                        for col in getattr(
                                                            self,
                                                            "r"
                                                            + str(coll)
                                                            + "_tool_details_print",
                                                        ).keys()
                                                    ],
                                                ],
                                                style={"border-spacing": "1px"},
                                            )
                                            for coll in range(1, len(files) + 1)
                                        ],
                                    ],
                                    style={
                                        "border": "1px solid black",
                                        "border-collapse": "collapse",
                                        "white-space": "wrap",
                                        "text-align": results_parser_config.textAlign,
                                        "word-wrap": "break-word",
                                    },
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
                                                        self.r1_data.result_tags_g_source_files_proc.keys()
                                                    ),
                                                    value=[
                                                        list(
                                                            self.r1_data.result_tags_g_source_files_proc.keys()
                                                        )[0]
                                                    ],
                                                    multi=True,
                                                    maxHeight=300,
                                                    clearable=False,
                                                ),
                                                dcc.Dropdown(
                                                    id="tag_proc_metrics",
                                                    multi=True,
                                                    maxHeight=300,
                                                    placeholder="Select metrics for above tags",
                                                    style={
                                                        "display": (
                                                            "none"
                                                            if not self.r1_data.result_tags_g_source_files_proc_enable
                                                            else "block"
                                                        ),
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ],
                                                    },
                                                    clearable=False,
                                                ),
                                                html.Div(
                                                    id="update-container-proc-metrics",
                                                    children=[],
                                                    className="mt-4",
                                                ),
                                            ],
                                            style={
                                                "display": (
                                                    "none"
                                                    if not self.r1_data.result_tags_g_source_files_proc_enable
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
                                                        self.r1_data.result_tags_g_source_files_nodex_sys.keys()
                                                    ),
                                                    value=[
                                                        list(
                                                            self.r1_data.result_tags_g_source_files_nodex_sys.keys()
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
                                                        "display": (
                                                            "none"
                                                            if not self.r1_data.result_tags_g_source_files_nodex_sys_enable
                                                            else "block"
                                                        ),
                                                        "backgroundColor": color[
                                                            "backgroundcolor"
                                                        ],
                                                    },
                                                    clearable=False,
                                                ),
                                            ],
                                            style={
                                                "display": (
                                                    "none"
                                                    if not self.r1_data.result_tags_g_source_files_nodex_sys_enable
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
                                "width": "23%",
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
                                            if not self.r1_data.result_tags_g_source_files_proc_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                dcc.Graph(
                                    id="graph_proc",
                                    config=results_parser_config.graph_config,
                                    style={
                                        "width": "90%",
                                        "height": self.graph_height,
                                        "backgroundColor": color["backgroundcolor"],
                                        "display": (
                                            "none"
                                            if not self.r1_data.result_tags_g_source_files_proc_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                html.H4(
                                    children="Global NUMA node data nodeX/sys/(*)",
                                    style={
                                        "textAlign": results_parser_config.textAlign,
                                        "display": (
                                            "none"
                                            if not self.r1_data.result_tags_g_source_files_nodex_sys_enable
                                            else "block"
                                        ),
                                    },
                                ),
                                dcc.Graph(
                                    id="graph_sys",
                                    config=results_parser_config.graph_config,
                                    style={
                                        "width": "90%",
                                        "height": self.graph_height,
                                        "backgroundColor": color["backgroundcolor"],
                                        "display": (
                                            "none"
                                            if not self.r1_data.result_tags_g_source_files_nodex_sys_enable
                                            else "block"
                                        ),
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

        input_callback_list.extend(
            [Input("tag_sys", "value"), Input("tag_proc", "value")]
        )

        input_callback_list.extend(
            [Input("tag_sys_metrics", "value"), Input("tag_proc_metrics", "value")]
        )

        @self.app.callback(
            [
                Output("tag_proc_metrics", "options"),
                Output("tag_sys_metrics", "options"),
            ],
            [Input("tag_proc", "value"), Input("tag_sys", "value")],
        )
        def update_dropdown(tag_proc, tag_sys):

            tag_proc_list = []
            for _tag in tag_proc:
                for metric in self.r1_data.result_tags_g_source_files_proc[_tag]:
                    x = True
                    for i in range(1, files_count + 1):
                        if (
                            _tag
                            not in getattr(
                                self, "r" + str(i) + "_data"
                            ).result_tags_g_source_files_proc
                            or metric
                            not in getattr(
                                self, "r" + str(i) + "_data"
                            ).result_tags_g_source_files_proc[_tag]
                        ):
                            x = False
                    if x:
                        tag_proc_list.append(metric)

            tag_sys_list = []
            for _tag in tag_sys:
                for metric in self.r1_data.result_tags_g_source_files_nodex_sys[_tag]:
                    x = True
                    for i in range(1, files_count + 1):
                        if (
                            _tag
                            not in getattr(
                                self, "r" + str(i) + "_data"
                            ).result_tags_g_source_files_nodex_sys
                            or metric
                            not in getattr(
                                self, "r" + str(i) + "_data"
                            ).result_tags_g_source_files_nodex_sys[_tag]
                        ):
                            x = False
                    if x:
                        tag_sys_list.append(metric)

            return tag_proc_list, tag_sys_list

        @self.app.callback(output=output_callback_list, inputs=input_callback_list)
        def update_line_chart(
            tag_sys="NA",
            tag_proc="NA",
            tag_sys_metrics="NA",
            tag_proc_metrics="NA",
        ):

            max_timestamps = 0
            max_timestamps_file_name = ""
            max_timestamps_file_counter = ""
            for i in range(1, files_count + 1):
                setattr(self, "r" + str(i) + "_time", [])
                if max_timestamps < len(
                    getattr(self, "r" + str(i) + "_data").timestamps
                ):
                    max_timestamps = len(
                        getattr(self, "r" + str(i) + "_data").timestamps
                    )
                    max_timestamps_file_name = getattr(
                        self, "r" + str(i) + "_file_path"
                    )
                    max_timestamps_file_counter = i
                for j in range(0, max_timestamps):
                    value = int(j * self.sample_period)
                    getattr(self, "r" + str(i) + "_time").append(value)

                setattr(self, "r" + str(i) + "_metric_list_proc", [])
                setattr(self, "r" + str(i) + "_metric_list_sys", [])
                getattr(self, "r" + str(i) + "_proc")[global_vars.timestamps] = getattr(
                    self, "r" + str(i) + "_time"
                )
                getattr(self, "r" + str(i) + "_sys")[global_vars.timestamps] = getattr(
                    self, "r" + str(i) + "_time"
                )

            metric_final_proc = []
            metric_final_sys = []
            final_proc = {}
            final_sys = {}
            final_proc[global_vars.timestamps] = getattr(
                self, "r" + str(max_timestamps_file_counter) + "_time"
            )
            final_sys[global_vars.timestamps] = getattr(
                self, "r" + str(max_timestamps_file_counter) + "_time"
            )
            graph_title_tag_proc = ""
            for _tag in tag_proc:
                graph_title_tag_proc = graph_title_tag_proc + " " + str(_tag)
                if tag_proc_metrics != None:
                    for metric in tag_proc_metrics:
                        for k in range(1, files_count + 1):
                            if (
                                metric
                                in getattr(self, "r" + str(k) + "_data")
                                .result_tags_g_source_files_proc[_tag]
                                .keys()
                            ):
                                getattr(
                                    self, "r" + str(k) + "_data"
                                ).get_metric_values_g_source_files_proc(_tag, metric)
                                setattr(
                                    self,
                                    "_r" + str(k) + "_metric",
                                    "r" + str(k) + metric,
                                )
                                final_proc[
                                    getattr(self, "_r" + str(k) + "_metric")
                                ] = getattr(
                                    self, "r" + str(k) + "_data"
                                ).result_tags_g_source_files_proc[
                                    _tag
                                ][
                                    metric
                                ]
                                if k != max_timestamps_file_counter:
                                    final_proc[
                                        getattr(self, "_r" + str(k) + "_metric")
                                    ] = make_list_of_given_size(
                                        final_proc[
                                            getattr(self, "_r" + str(k) + "_metric")
                                        ],
                                        max_timestamps,
                                    )
                                getattr(
                                    self, "r" + str(k) + "_metric_list_proc"
                                ).append(getattr(self, "_r" + str(k) + "_metric"))
                            metric_final_proc += getattr(
                                self, "r" + str(k) + "_metric_list_proc"
                            )
            fig1 = px.line(
                final_proc,
                x=global_vars.timestamps,
                y=metric_final_proc,
                labels={global_vars.timestamps: f"{results_parser_config.xaxisLabel}"},
            ).update_layout(
                title=graph_title_tag_proc,
                hovermode="x",
                legend=dict(y=-0.5, x=0),
            )
            fig1.update_traces(legendwidth=1000)

            graph_title_tag_sys = ""
            for _tag in tag_sys:
                graph_title_tag_sys = graph_title_tag_sys + " " + str(_tag)
                if tag_sys_metrics != None:
                    for metric in tag_sys_metrics:
                        for k in range(1, files_count + 1):
                            if (
                                metric
                                in getattr(self, "r" + str(k) + "_data")
                                .result_tags_g_source_files_nodex_sys[_tag]
                                .keys()
                            ):
                                getattr(
                                    self, "r" + str(k) + "_data"
                                ).get_metric_values_g_source_files_nodex_sys(
                                    _tag, metric
                                )
                                setattr(
                                    self,
                                    "_r" + str(k) + "_metric",
                                    "r" + str(k) + metric,
                                )
                                getattr(self, "r" + str(k) + "_sys")[
                                    getattr(self, "_r" + str(k) + "_metric")
                                ] = getattr(
                                    self, "r" + str(k) + "_data"
                                ).result_tags_g_source_files_nodex_sys[
                                    _tag
                                ][
                                    metric
                                ]
                                if k != max_timestamps_file_counter:
                                    getattr(self, "r" + str(k) + "_sys")[
                                        getattr(self, "_r" + str(k) + "_metric")
                                    ] = make_list_of_given_size(
                                        getattr(self, "r" + str(k) + "_sys")[
                                            getattr(self, "_r" + str(k) + "_metric")
                                        ],
                                        max_timestamps,
                                    )
                                getattr(self, "r" + str(k) + "_metric_list_sys").append(
                                    getattr(self, "_r" + str(k) + "_metric")
                                )
                            final_sys |= getattr(self, "r" + str(k) + "_sys")

                            metric_final_sys += getattr(
                                self, "r" + str(k) + "_metric_list_sys"
                            )
            fig2 = px.line(
                final_sys,
                x=global_vars.timestamps,
                y=metric_final_sys,
                labels={global_vars.timestamps: f"{results_parser_config.xaxisLabel}"},
            ).update_layout(
                title=graph_title_tag_sys,
                hovermode="x",
                legend=dict(y=-0.5, x=0),
            )
            fig2.update_traces(legendwidth=1000)

            return fig1, fig2

        public_ip = get_IPaddr()
        port = get_port(public_ip)
        self.app.run_server(host=public_ip, port=port, debug=False)


def main(params=None, *args):
    comp = comparator()
    try:
        comp.main(params, args)
    except NameError as e:
        comp.main()


if __name__ == "__main__":
    main()
