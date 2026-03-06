import json
import os
import re
from datetime import datetime


def save_report(report, config):
    report["project_name"] = config["project_name"]
    project_dir = os.path.join(
        os.path.expanduser(config["reports_dir"]),
        _safe_filename(config["project_name"])
    )
    os.makedirs(project_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = report.get("build_target", "Unknown")
    filename = f"{timestamp}_{target}.json"
    filepath = os.path.join(project_dir, filename)

    with open(filepath, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved: {filepath}")
    return filepath


def load_report(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def list_reports(config):
    project_dir = os.path.join(
        os.path.expanduser(config["reports_dir"]),
        _safe_filename(config["project_name"])
    )
    if not os.path.exists(project_dir):
        return []

    reports = []
    for filename in sorted(os.listdir(project_dir), reverse=True):
        if filename.endswith(".json"):
            filepath = os.path.join(project_dir, filename)
            with open(filepath, "r") as f:
                data = json.load(f)
            reports.append({
                "filename": filename,
                "filepath": filepath,
                "build_time": data.get("build_time", ""),
                "build_target": data.get("build_target", ""),
                "build_hash": data.get("build_hash", ""),
                "analyzed_at": data.get("analyzed_at", ""),
                "summary": data.get("summary", {}),
            })
    return reports


def get_latest_report(config):
    reports = list_reports(config)
    if not reports:
        return None
    return load_report(reports[0]["filepath"])


def _safe_filename(name):
    return re.sub(r'[^\w\-.]', '_', name)
