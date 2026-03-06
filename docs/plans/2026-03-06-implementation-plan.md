# Addressable Build Report Analyzer - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A zero-dependency Python web tool that parses Unity Addressables `buildlayout.json`, shows duplicates/dependencies/sizes, and tracks build history for diffing.

**Architecture:** Python backend parses the rid-based JSON into flat structures, saves snapshots, serves a vanilla HTML/JS frontend via built-in http.server. All data flows through JSON API endpoints.

**Tech Stack:** Python 3.8+ (stdlib only), vanilla HTML/CSS/JS, Chart.js via CDN

---

### Task 1: Project Skeleton + Config

**Files:**
- Create: `run.py`
- Create: `analyzer/__init__.py`
- Create: `analyzer/config.py`
- Create: `.gitignore`

**Step 1: Create .gitignore**

```
__pycache__/
*.pyc
.DS_Store
config.json
```

**Step 2: Create analyzer/config.py**

```python
import json
import os

DEFAULT_CONFIG = {
    "project_name": "",
    "buildlayout_path": "Library/com.unity.addressables/buildlayout.json",
    "reports_dir": os.path.expanduser("~/.addressable-analyzer/reports"),
    "port": 8080
}

CONFIG_FILE = "config.json"


def load_config(project_dir=None):
    """Load config, create default if missing. CLI args override."""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config.update(json.load(f))

    # Auto-detect project name from Unity ProjectSettings
    if not config["project_name"]:
        config["project_name"] = _detect_project_name(project_dir or os.getcwd())

    # Resolve buildlayout_path relative to project_dir
    if project_dir and not os.path.isabs(config["buildlayout_path"]):
        config["buildlayout_path"] = os.path.join(project_dir, config["buildlayout_path"])

    return config


def save_default_config():
    """Save default config.json if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)


def _detect_project_name(project_dir):
    """Try to read project name from Unity ProjectSettings."""
    settings_path = os.path.join(project_dir, "ProjectSettings", "ProjectSettings.asset")
    if os.path.exists(settings_path):
        with open(settings_path, "r", errors="ignore") as f:
            for line in f:
                if "productName:" in line:
                    return line.split("productName:")[-1].strip()
    return os.path.basename(project_dir)
```

**Step 3: Create run.py (minimal entry point)**

```python
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

    # Parser and server will be added in next tasks
    from analyzer.parser import parse_build_layout
    from analyzer.report import generate_report
    from analyzer.storage import save_report, get_latest_report
    from analyzer.server import start_server

    report = generate_report(parse_build_layout(layout_path))
    save_report(report, config)
    start_server(config)


if __name__ == "__main__":
    main()
```

**Step 4: Create analyzer/__init__.py**

Empty file.

**Step 5: Commit**

```bash
git add -A
git commit -m "[Added] Project skeleton with config and entry point"
```

---

### Task 2: Parser - Resolve rid References

**Files:**
- Create: `analyzer/parser.py`

The buildlayout.json uses a `references.RefIds` array where objects link via `{"rid": N}`. We need a two-pass parser:

**Step 1: Create analyzer/parser.py**

```python
import json
import os
from datetime import datetime


def parse_build_layout(path):
    """Parse buildlayout.json into a resolved data structure."""
    with open(path, "r") as f:
        raw = json.load(f)

    rid_map = _build_rid_map(raw["references"]["RefIds"])

    groups = []
    for group_ref in raw.get("Groups", []):
        group = _resolve_group(rid_map, group_ref["rid"])
        if group:
            groups.append(group)

    duplicates = _resolve_duplicates(raw.get("DuplicatedAssets", []), rid_map)

    return {
        "build_target": _target_name(raw.get("BuildTarget", 0)),
        "build_time": raw.get("BuildStartTime", ""),
        "duration": raw.get("Duration", 0),
        "unity_version": raw.get("UnityVersion", ""),
        "addressables_version": raw.get("PackageVersion", ""),
        "build_hash": raw.get("BuildResultHash", ""),
        "groups": groups,
        "duplicates": duplicates,
        "file_size": os.path.getsize(path),
    }


def _build_rid_map(ref_ids):
    """Pass 1: Build rid -> {type, data} lookup."""
    return {r["rid"]: r for r in ref_ids}


def _resolve_group(rid_map, group_rid):
    """Resolve a Group and its Bundles."""
    entry = rid_map.get(group_rid)
    if not entry or entry.get("type", {}).get("class") != "BuildLayout/Group":
        return None

    data = entry["data"]
    bundles = []
    for bundle_ref in data.get("Bundles", []):
        bundle = _resolve_bundle(rid_map, bundle_ref["rid"])
        if bundle:
            bundle["group"] = data["Name"]
            bundles.append(bundle)

    return {
        "name": data["Name"],
        "guid": data.get("Guid", ""),
        "packing_mode": data.get("PackingMode", ""),
        "bundles": bundles,
    }


def _resolve_bundle(rid_map, bundle_rid):
    """Resolve a Bundle with its dependencies and assets."""
    entry = rid_map.get(bundle_rid)
    if not entry or entry.get("type", {}).get("class") != "BuildLayout/Bundle":
        return None

    data = entry["data"]

    # Resolve bundle dependencies
    dependencies = []
    for dep in data.get("BundleDependencies", []):
        dep_bundle_rid = dep.get("DependencyBundle", {}).get("rid")
        dep_entry = rid_map.get(dep_bundle_rid, {})
        dep_data = dep_entry.get("data", {})
        if dep_data:
            dependencies.append({
                "bundle_name": dep_data.get("Name", ""),
                "efficiency": dep.get("Efficiency", 0),
            })

    # Determine if remote
    load_path = data.get("LoadPath", "")
    is_remote = "http" in load_path or "{Remote" in load_path

    return {
        "name": data.get("Name", ""),
        "internal_name": data.get("InternalName", ""),
        "size": data.get("FileSize", 0),
        "asset_count": data.get("AssetCount", 0),
        "dependency_size": data.get("DependencyFileSize", 0),
        "compression": data.get("Compression", ""),
        "hash": data.get("Hash", {}).get("Hash", ""),
        "load_path": load_path,
        "is_remote": is_remote,
        "dependencies": dependencies,
    }


def _resolve_duplicates(duplicated_assets, rid_map):
    """Resolve DuplicatedAssets with asset names and bundle names."""
    result = []
    for dup in duplicated_assets:
        guid = dup["AssetGuid"]

        # Find asset path from DataFromOtherAsset or ExplicitAsset entries
        asset_path = _find_asset_path(guid, rid_map)

        bundle_names = set()
        for obj in dup.get("DuplicatedObjects", []):
            for file_ref in obj.get("IncludedInBundleFiles", []):
                file_entry = rid_map.get(file_ref["rid"], {})
                file_data = file_entry.get("data", {})
                bundle_rid = file_data.get("Bundle", {}).get("rid")
                if bundle_rid:
                    bundle_entry = rid_map.get(bundle_rid, {})
                    bundle_name = bundle_entry.get("data", {}).get("Name", "")
                    if bundle_name:
                        bundle_names.add(bundle_name)

        result.append({
            "asset_guid": guid,
            "asset_path": asset_path,
            "asset_name": os.path.basename(asset_path) if asset_path else guid[:12],
            "bundle_count": len(bundle_names),
            "bundles": sorted(bundle_names),
        })

    # Sort by bundle_count descending
    result.sort(key=lambda x: x["bundle_count"], reverse=True)
    return result


def _find_asset_path(guid, rid_map):
    """Find asset path by GUID from resolved references."""
    for entry in rid_map.values():
        data = entry.get("data", {})
        if data.get("AssetGuid") == guid or data.get("Guid") == guid:
            path = data.get("AssetPath", "")
            if path:
                return path
    return ""


def _target_name(target_id):
    """Convert BuildTarget int to name."""
    targets = {
        9: "iOS",
        13: "Android",
        19: "StandaloneWindows64",
        2: "StandaloneOSX",
    }
    return targets.get(target_id, f"Unknown({target_id})")
```

**Step 2: Test parser manually**

```bash
cd ~/Projects/cube-busters-client
python3 -c "
import sys; sys.path.insert(0, '../addressable-analyzer')
from analyzer.parser import parse_build_layout
data = parse_build_layout('Library/com.unity.addressables/buildlayout.json')
print(f'Groups: {len(data[\"groups\"])}')
print(f'Duplicates: {len(data[\"duplicates\"])}')
total_bundles = sum(len(g['bundles']) for g in data['groups'])
print(f'Total bundles: {total_bundles}')
print(f'Top 3 duplicates:')
for d in data['duplicates'][:3]:
    print(f'  {d[\"asset_name\"]} in {d[\"bundle_count\"]} bundles')
"
```

Expected: Groups: 45, Duplicates: 77, Total bundles: ~221

**Step 3: Commit**

```bash
cd ~/Projects/addressable-analyzer
git add -A
git commit -m "[Added] buildlayout.json parser with rid resolution"
```

---

### Task 3: Report Generator

**Files:**
- Create: `analyzer/report.py`

**Step 1: Create analyzer/report.py**

```python
from datetime import datetime


def generate_report(parsed_data):
    """Generate analysis report from parsed build layout data."""
    bundles = []
    for group in parsed_data["groups"]:
        for bundle in group["bundles"]:
            bundles.append(bundle)

    total_size = sum(b["size"] for b in bundles)
    total_assets = sum(b["asset_count"] for b in bundles)
    remote_bundles = [b for b in bundles if b["is_remote"]]
    local_bundles = [b for b in bundles if not b["is_remote"]]

    # Find cross-dependencies (remote -> remote)
    remote_names = {b["name"] for b in remote_bundles}
    cross_deps = []
    for bundle in bundles:
        for dep in bundle.get("dependencies", []):
            dep_name = dep["bundle_name"]
            if bundle["is_remote"] and dep_name in remote_names:
                cross_deps.append({
                    "from_bundle": bundle["name"],
                    "from_group": bundle["group"],
                    "to_bundle": dep_name,
                    "to_group": _find_group_for_bundle(parsed_data["groups"], dep_name),
                    "efficiency": dep["efficiency"],
                })

    return {
        "project_name": "",  # Set by caller
        "build_target": parsed_data["build_target"],
        "build_time": parsed_data["build_time"],
        "build_hash": parsed_data["build_hash"],
        "duration": parsed_data["duration"],
        "unity_version": parsed_data["unity_version"],
        "addressables_version": parsed_data["addressables_version"],
        "analyzed_at": datetime.now().isoformat(),
        "summary": {
            "total_groups": len(parsed_data["groups"]),
            "total_bundles": len(bundles),
            "total_assets": total_assets,
            "total_size": total_size,
            "remote_bundles": len(remote_bundles),
            "local_bundles": len(local_bundles),
            "remote_size": sum(b["size"] for b in remote_bundles),
            "local_size": sum(b["size"] for b in local_bundles),
            "duplicate_count": len(parsed_data["duplicates"]),
            "cross_dependency_count": len(cross_deps),
        },
        "bundles": sorted(bundles, key=lambda b: b["size"], reverse=True),
        "duplicates": parsed_data["duplicates"],
        "cross_dependencies": cross_deps,
    }


def _find_group_for_bundle(groups, bundle_name):
    """Find which group a bundle belongs to."""
    for group in groups:
        for bundle in group["bundles"]:
            if bundle["name"] == bundle_name:
                return group["name"]
    return "Unknown"
```

**Step 2: Commit**

```bash
git add -A
git commit -m "[Added] Report generator with cross-dependency detection"
```

---

### Task 4: Storage - Save/Load Reports

**Files:**
- Create: `analyzer/storage.py`

**Step 1: Create analyzer/storage.py**

```python
import json
import os
import re
from datetime import datetime


def save_report(report, config):
    """Save report snapshot to reports directory."""
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
    """Load a saved report."""
    with open(filepath, "r") as f:
        return json.load(f)


def list_reports(config):
    """List all saved reports for the current project."""
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
            # Read just the summary for listing
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
    """Get the most recent saved report."""
    reports = list_reports(config)
    if not reports:
        return None
    return load_report(reports[0]["filepath"])


def _safe_filename(name):
    """Convert project name to safe directory name."""
    return re.sub(r'[^\w\-.]', '_', name)
```

**Step 2: Commit**

```bash
git add -A
git commit -m "[Added] Report storage with save/load/list"
```

---

### Task 5: Diff Engine

**Files:**
- Create: `analyzer/diff.py`

**Step 1: Create analyzer/diff.py**

```python
def diff_reports(old_report, new_report):
    """Compare two reports and return differences."""
    if not old_report or not new_report:
        return None

    old_summary = old_report.get("summary", {})
    new_summary = new_report.get("summary", {})

    # Summary deltas
    summary_diff = {}
    for key in new_summary:
        old_val = old_summary.get(key, 0)
        new_val = new_summary.get(key, 0)
        if isinstance(new_val, (int, float)):
            summary_diff[key] = {
                "old": old_val,
                "new": new_val,
                "delta": new_val - old_val,
            }

    # Bundle size changes
    old_bundles = {b["name"]: b for b in old_report.get("bundles", [])}
    new_bundles = {b["name"]: b for b in new_report.get("bundles", [])}

    added_bundles = [new_bundles[n] for n in new_bundles if n not in old_bundles]
    removed_bundles = [old_bundles[n] for n in old_bundles if n not in new_bundles]

    size_changes = []
    for name in new_bundles:
        if name in old_bundles:
            old_size = old_bundles[name]["size"]
            new_size = new_bundles[name]["size"]
            delta = new_size - old_size
            if delta != 0:
                size_changes.append({
                    "name": name,
                    "group": new_bundles[name].get("group", ""),
                    "old_size": old_size,
                    "new_size": new_size,
                    "delta": delta,
                })
    size_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Duplicate changes
    old_dup_guids = {d["asset_guid"] for d in old_report.get("duplicates", [])}
    new_dup_guids = {d["asset_guid"] for d in new_report.get("duplicates", [])}

    new_duplicates = [
        d for d in new_report.get("duplicates", [])
        if d["asset_guid"] not in old_dup_guids
    ]
    resolved_duplicates = [
        d for d in old_report.get("duplicates", [])
        if d["asset_guid"] not in new_dup_guids
    ]

    # Cross-dependency changes
    old_cross = {(d["from_bundle"], d["to_bundle"]) for d in old_report.get("cross_dependencies", [])}
    new_cross = {(d["from_bundle"], d["to_bundle"]) for d in new_report.get("cross_dependencies", [])}

    new_cross_deps = [
        d for d in new_report.get("cross_dependencies", [])
        if (d["from_bundle"], d["to_bundle"]) not in old_cross
    ]
    resolved_cross_deps = [
        d for d in old_report.get("cross_dependencies", [])
        if (d["from_bundle"], d["to_bundle"]) not in new_cross
    ]

    return {
        "old_build_time": old_report.get("build_time", ""),
        "new_build_time": new_report.get("build_time", ""),
        "old_build_hash": old_report.get("build_hash", ""),
        "new_build_hash": new_report.get("build_hash", ""),
        "summary_diff": summary_diff,
        "added_bundles": added_bundles,
        "removed_bundles": removed_bundles,
        "size_changes": size_changes,
        "new_duplicates": new_duplicates,
        "resolved_duplicates": resolved_duplicates,
        "new_cross_dependencies": new_cross_deps,
        "resolved_cross_dependencies": resolved_cross_deps,
    }
```

**Step 2: Commit**

```bash
git add -A
git commit -m "[Added] Diff engine for comparing build reports"
```

---

### Task 6: HTTP Server + API

**Files:**
- Create: `analyzer/server.py`

**Step 1: Create analyzer/server.py**

```python
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# These will be set by start_server()
_config = None
_current_report = None


class AnalyzerHandler(SimpleHTTPRequestHandler):
    """HTTP handler for API endpoints and static files."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_file("web/index.html", "text/html")
        elif path == "/style.css":
            self._serve_file("web/style.css", "text/css")
        elif path == "/app.js":
            self._serve_file("web/app.js", "application/javascript")
        elif path == "/api/report":
            self._json_response(_current_report)
        elif path == "/api/reports":
            from analyzer.storage import list_reports
            reports = list_reports(_config)
            self._json_response(reports)
        elif path == "/api/report/load":
            filepath = query.get("path", [None])[0]
            if filepath and os.path.exists(filepath):
                from analyzer.storage import load_report
                self._json_response(load_report(filepath))
            else:
                self._json_response({"error": "Report not found"}, 404)
        elif path == "/api/diff":
            self._handle_diff(query)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/reload":
            self._handle_reload()
        else:
            self.send_error(404)

    def _handle_diff(self, query):
        a_path = query.get("a", [None])[0]
        b_path = query.get("b", [None])[0]
        if not a_path or not b_path:
            self._json_response({"error": "Need both ?a=path&b=path"}, 400)
            return

        from analyzer.storage import load_report
        from analyzer.diff import diff_reports

        if not os.path.exists(a_path) or not os.path.exists(b_path):
            self._json_response({"error": "Report file not found"}, 404)
            return

        old = load_report(a_path)
        new = load_report(b_path)
        result = diff_reports(old, new)
        self._json_response(result)

    def _handle_reload(self):
        global _current_report
        from analyzer.parser import parse_build_layout
        from analyzer.report import generate_report
        from analyzer.storage import save_report

        layout_path = _config["buildlayout_path"]
        if not os.path.exists(layout_path):
            self._json_response({"error": f"File not found: {layout_path}"}, 404)
            return

        parsed = parse_build_layout(layout_path)
        _current_report = generate_report(parsed)
        _current_report["project_name"] = _config["project_name"]
        save_report(_current_report, _config)
        self._json_response({"status": "ok", "summary": _current_report["summary"]})

    def _serve_file(self, filepath, content_type):
        # Resolve relative to the analyzer package directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            self.send_error(404)
            return
        with open(full_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


def start_server(config, report=None):
    global _config, _current_report
    _config = config
    _current_report = report

    server = HTTPServer(("0.0.0.0", config["port"]), AnalyzerHandler)
    print(f"Server running at http://localhost:{config['port']}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
```

**Step 2: Update run.py to pass report to server**

Replace the last lines of `main()`:

```python
    report = generate_report(parse_build_layout(layout_path))
    report["project_name"] = config["project_name"]
    save_report(report, config)
    start_server(config, report)
```

**Step 3: Commit**

```bash
git add -A
git commit -m "[Added] HTTP server with API endpoints"
```

---

### Task 7: Frontend - HTML Shell + Dashboard

**Files:**
- Create: `web/index.html`
- Create: `web/style.css`
- Create: `web/app.js`

**Step 1: Create web/index.html**

Single-page app with tab navigation. Full content in implementation — includes:
- Header with project name + build info
- Tab bar: Dashboard | Duplicates | Dependencies | Bundle Sizes | Build Diff
- Content area per tab
- Chart.js CDN link

**Step 2: Create web/style.css**

Clean, professional dark theme suitable for dev tools. Key elements:
- Card-based dashboard layout
- Sortable table styles
- Severity color coding (red/orange/yellow for duplicates)
- Tab active states
- Responsive layout

**Step 3: Create web/app.js**

Main JS file handling:
- Tab switching
- Fetch data from `/api/report`
- Render dashboard cards with summary metrics
- Render duplicates table (sortable by count, name)
- Render dependencies table with remote-to-remote highlighting
- Render bundle sizes table + Chart.js bar chart
- Build diff tab: select two reports from `/api/reports`, fetch `/api/diff`, render changes
- Reload button calling `POST /api/reload`
- Format bytes helper (KB/MB)

**Step 4: Commit**

```bash
git add -A
git commit -m "[Added] Frontend with dashboard, duplicates, dependencies, sizes, and diff tabs"
```

---

### Task 8: Integration Test + Polish

**Step 1: End-to-end test**

```bash
cd ~/Projects/addressable-analyzer
python3 run.py --project-dir ~/Projects/cube-busters-client
```

Open `http://localhost:8080` and verify:
- Dashboard shows correct counts (45 groups, ~221 bundles, 77 duplicates)
- Duplicates tab lists all 77 with bundle names
- Dependencies tab shows cross-dependencies, remote-to-remote in red
- Bundle Sizes tab shows chart + sorted table
- Reload button works
- Build Diff tab works when 2+ reports saved

**Step 2: Fix any issues found**

**Step 3: Add README.md**

Quick start instructions:

```markdown
# Addressable Build Report Analyzer

Analyze Unity Addressables build reports — find duplicates, track dependencies, compare builds.

## Quick Start

```bash
cd your-unity-project/
python3 /path/to/addressable-analyzer/run.py
```

Opens at http://localhost:8080

## Options

- `--path PATH` — Custom buildlayout.json path
- `--project NAME` — Override project name
- `--project-dir DIR` — Unity project directory (default: cwd)
- `--port PORT` — Server port (default: 8080)
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "[Added] README and integration polish"
```
