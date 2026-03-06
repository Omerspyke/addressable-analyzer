#!/usr/bin/env python3
import argparse
import os
import sys

from analyzer.config import load_config, save_default_config


def main():
    parser = argparse.ArgumentParser(description="Addressable Build Report Analyzer")
    parser.add_argument("--path", help="Path to buildlayout.json")
    parser.add_argument("--project", help="Project name override")
    parser.add_argument("--project-dir", help="Unity project directory (default: cwd)")
    parser.add_argument("--port", type=int, help="Server port (default: 8080)")
    args = parser.parse_args()

    project_dir = args.project_dir or os.getcwd()
    save_default_config()
    config = load_config(project_dir)

    if args.path:
        config["buildlayout_path"] = args.path
    if args.project:
        config["project_name"] = args.project
    if args.port:
        config["port"] = args.port

    layout_path = config["buildlayout_path"]
    if not os.path.exists(layout_path):
        print(f"Error: buildlayout.json not found at: {layout_path}")
        print(f"Run an Addressables build first, or specify --path")
        sys.exit(1)

    print(f"Project: {config['project_name']}")
    print(f"Layout:  {layout_path}")
    print(f"Server:  http://localhost:{config['port']}")

    from analyzer.parser import parse_build_layout
    from analyzer.report import generate_report
    from analyzer.storage import save_report
    from analyzer.server import start_server

    report = generate_report(parse_build_layout(layout_path))
    report["project_name"] = config["project_name"]
    save_report(report, config)
    start_server(config, report)


if __name__ == "__main__":
    main()
