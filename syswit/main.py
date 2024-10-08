#!/usr/bin/python3
# SPDX-License-Identifier: MIT License
# Copyright (C) 2024 Advanced Micro Devices, Inc.
#
# Author: Ayush Jain <ayush.jain3@amd.com>

import argparse
import syswit.collector as collector
import syswit.analyzer as analyzer
import syswit.comparator as comparator
from syswit.collector import main as collector_main
from syswit.analyzer import main as analyzer_main
from syswit.comparator import main as comparator_main
from syswit import collector_config as config


def main():
    parser = argparse.ArgumentParser(
        description="syswit", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Components of syswit")

    parser_collector = subparsers.add_parser(
        "collect",
        help="E.g., syswit collect -p 234 -n 10 -s 1",
    )
    parser_collector.set_defaults(func=collector_main)
    collector.collector().add_arguments(parser=parser_collector)

    parser_analyzer = subparsers.add_parser(
        "analyze", help="E.g., syswit analyze -f '/logs/results.json' "
    )
    parser_analyzer.set_defaults(func=analyzer_main)
    analyzer.Analyzer().add_arguments(parser=parser_analyzer)

    parser_comparator = subparsers.add_parser(
        "compare",
        help="E.g., syswit compare -f '/logs/results1.json, /logs/results2.json'",
    )
    parser_comparator.set_defaults(func=comparator_main)
    comparator.comparator().add_arguments(parser=parser_comparator)

    args = parser.parse_args()

    if args.subcommand == "collect":
        collector_main(args)
    elif args.subcommand == "analyze":
        analyzer_main(args)
    elif args.subcommand == "compare":
        comparator_main(args)


if __name__ == "__main__":
    main()
