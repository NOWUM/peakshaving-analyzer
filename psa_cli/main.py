# !/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
import logging
import sys
from pathlib import Path

import argcomplete


def cli():
    parser = argparse.ArgumentParser(description="Peak Shaving Analyzer CLI")
    parser.add_argument("-c", "--config", type=str, required=True, help="Path to the configuration YAML file")
    parser.add_argument("-o", "--output", type=str, default="std", help="Path to save results (yaml, json or std)")
    parser.add_argument("--solver", type=str, default="appsi_highs", help="Solver to use (optional)")
    parser.add_argument(
        "--output-timeseries",
        type=str,
        default=None,
        help="Path to save resulting timeseries to (not saving if not provided)",
    )
    parser.add_argument("-v", "--verbose", help="Whether to print progress or not", action="store_true")

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    from peakshaving_analyzer.input import load_yaml_config
    from peakshaving_analyzer.PSA import PeakShavingAnalyzer

    if args.verbose:
        level = logging.INFO
    else:
        level = logging.ERROR
    logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", level=level, datefmt="%Y-%m-%d %H:%M:%S")

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    config = load_yaml_config(config_path)

    # Run optimization
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize(solver=args.solver)

    print("---------------------------------------------------------")

    # Output results
    if args.output.endswith(".yaml") or args.output.endswith(".yml"):
        results.to_yaml(args.output)
        print(f"Results saved to {args.output} (YAML)")

    elif args.output.endswith(".json"):
        results.to_json(args.output)
        print(f"Results saved to {args.output} (JSON)")
    else:
        results.print(include_timeseries=args.output_timeseries)

    if args.output_timeseries:
        if args.output_timeseries.endswith(".csv"):
            results.timeseries_to_csv(args.output_timeseries)
        elif args.output_timeseries.endswith(".json"):
            results.timeseries_to_json(args.output_timeseries)
        else:
            raise NotImplementedError


if __name__ == "__main__":
    cli()
