#!/usr/bin/env python3
import argparse
import os
import sys

from analyzer.config import load_config, save_config


def main():
    parser = argparse.ArgumentParser(description="Addressable Build Report Analyzer")
    parser.add_argument("--project-dir", help="Unity project directory (default: cwd)")
    parser.add_argument("--port", type=int, help="Server port (default: 8080)")
    args = parser.parse_args()

    project_dir = args.project_dir or os.getcwd()
    save_config(project_dir)
    config = load_config(project_dir)

    if args.port:
        config["port"] = args.port

    layout_path = config["buildlayout_path"]
    if not os.path.exists(layout_path):
        print(f"Error: buildlayout.json not found at: {layout_path}")
        print(f"Run an Addressables build first, or check --project-dir")
        sys.exit(1)

    print(f"Project: {config['project_name']}")
    print(f"Layout:  {layout_path}")
    print(f"Server:  http://localhost:{config['port']}")

    from analyzer.parser import parse_build_layout
    from analyzer.report import generate_report
    from analyzer.storage import save_report, import_build_reports
    from analyzer.server import start_server

    # Import any existing Unity BuildReports for history
    import_build_reports(config)

    report = generate_report(parse_build_layout(layout_path))
    report["project_name"] = config["project_name"]
    save_report(report, config)
    start_server(config, report)


if __name__ == "__main__":
    main()
