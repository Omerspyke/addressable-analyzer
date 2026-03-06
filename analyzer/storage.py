import json
import os
import re
from datetime import datetime


def save_report(report, config):
    """Save report. Skip if same build_hash already saved."""
    report["project_name"] = config["project_name"]
    project_dir = _project_dir(config)
    os.makedirs(project_dir, exist_ok=True)

    # Don't save duplicate builds (match by hash, or by time+target if no hash)
    build_hash = report.get("build_hash", "")
    build_time = report.get("build_time", "")
    build_target = report.get("build_target", "")
    for filename in os.listdir(project_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(project_dir, filename)
            try:
                with open(filepath, "r") as f:
                    existing = json.load(f)
                if build_hash and existing.get("build_hash") == build_hash:
                    print(f"Report already saved: {filepath}")
                    return None
                if not build_hash and build_time and \
                   existing.get("build_time") == build_time and \
                   existing.get("build_target") == build_target:
                    print(f"Report already saved: {filepath}")
                    return None
            except (json.JSONDecodeError, OSError):
                pass

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = report.get("build_target", "Unknown")
    filename = f"{timestamp}_{target}.json"
    filepath = os.path.join(project_dir, filename)

    with open(filepath, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved: {filepath}")
    return filepath


def import_build_reports(config):
    """Import Unity's BuildReports into our storage (skips already imported)."""
    project_dir_path = os.path.dirname(config["buildlayout_path"])
    reports_dir = os.path.join(project_dir_path, "BuildReports")

    if not os.path.exists(reports_dir):
        return 0

    from analyzer.parser import parse_build_layout
    from analyzer.report import generate_report

    imported = 0
    for filename in sorted(os.listdir(reports_dir)):
        if filename.startswith("buildlayout_") and filename.endswith(".json"):
            filepath = os.path.join(reports_dir, filename)
            try:
                report = generate_report(parse_build_layout(filepath))
                # Skip editor/standalone builds — only import mobile targets
                target = report.get("build_target", "")
                if "Standalone" in target:
                    continue
                report["project_name"] = config["project_name"]
                result = save_report(report, config)
                if result is not None:
                    imported += 1
            except Exception as e:
                print(f"Skipping {filename}: {e}")

    if imported > 0:
        print(f"Imported {imported} build reports from Unity BuildReports/")
    return imported


def load_report(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def list_reports(config):
    project_dir = _project_dir(config)
    if not os.path.exists(project_dir):
        return []

    reports = []
    seen_hashes = set()
    for filename in sorted(os.listdir(project_dir), reverse=True):
        if filename.endswith(".json"):
            filepath = os.path.join(project_dir, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # Deduplicate by build_hash
            build_hash = data.get("build_hash", "")
            if build_hash in seen_hashes:
                continue
            if build_hash:
                seen_hashes.add(build_hash)

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


def _project_dir(config):
    return os.path.join(
        os.path.expanduser(config["reports_dir"]),
        _safe_filename(config["project_name"])
    )


def _safe_filename(name):
    return re.sub(r'[^\w\-.]', '_', name)
