# Addressable Build Report Analyzer - Design

## Problem

Unity Addressables build reports (`buildlayout.json`) contain critical information about duplicate assets, cross-group dependencies, and bundle sizes. But at ~43MB of raw JSON with a `rid`-based reference system, they're impractical to read manually. Teams need a way to:

- Quickly spot duplicate assets wasting bundle size
- Identify dangerous cross-group dependencies (especially remote-to-remote)
- Track how builds change over time
- Share insights across team members

## Solution

A local Python web tool that parses `buildlayout.json`, generates an interactive HTML report, and tracks build history for diffing.

## How It Works

1. Run `python run.py` from any Unity project directory
2. Tool reads `Library/com.unity.addressables/buildlayout.json` (or configured path)
3. Parses the `rid`-based reference graph into a flat, queryable structure
4. Saves analysis snapshot to `~/.addressable-analyzer/reports/<project>/`
5. Serves interactive web UI at `localhost:8080`

## Configuration

First run auto-creates `config.json` in tool directory:

```json
{
  "project_name": "Cube Busters",
  "buildlayout_path": "Library/com.unity.addressables/buildlayout.json",
  "reports_dir": "~/.addressable-analyzer/reports",
  "port": 8080
}
```

- `buildlayout_path`: relative to the Unity project root (CWD), or absolute
- `reports_dir`: centralized storage, organized by project name
- Users override by passing CLI args: `python run.py --path /path/to/buildlayout.json --project "Other Game"`

## Data Model

### buildlayout.json Structure

The file uses a `references.RefIds` array where everything links via `rid` integers:

| Type | Count (Cube Busters) | Contains |
|------|------|----------|
| Group | 45 | Name, Guid, PackingMode, Bundles[] |
| Bundle | 221 | Name, FileSize, BundleDependencies[], Hash, LoadPath |
| File | 222 | Bundle ref, Assets[], OtherAssets[] |
| ExplicitAsset | 1,643 | AddressableName, Guid, SerializedSize, StreamedSize |
| DataFromOtherAsset | 3,206 | Implicit dependencies |
| SubFile | 437 | Sub-file entries |

Additionally, top-level `DuplicatedAssets` (77 entries) lists assets appearing in multiple bundles.

### Saved Report Format

Each analysis snapshot saved as JSON:

```json
{
  "project_name": "Cube Busters",
  "build_target": "iOS",
  "build_time": "2026-03-06T09:51:52",
  "unity_version": "2022.3.69f1",
  "addressables_version": "1.28.0",
  "summary": {
    "total_groups": 45,
    "total_bundles": 221,
    "total_assets": 1643,
    "total_size_bytes": 123456789,
    "duplicate_count": 77,
    "estimated_waste_bytes": 5678900
  },
  "bundles": [
    {
      "name": "remotebullseyeleague_assets_all.bundle",
      "group": "RemoteBullseyeLeague",
      "size": 234567,
      "asset_count": 5,
      "dependency_size": 345678,
      "dependencies": ["localsharedtextures_...", "default_assets_all..."],
      "is_remote": true
    }
  ],
  "duplicates": [
    {
      "asset_guid": "90fd7564...",
      "asset_name": "SomeSprite",
      "asset_path": "Assets/Spyke/...",
      "total_waste_bytes": 12345,
      "found_in_bundles": ["bundle_a", "bundle_b", "bundle_c"]
    }
  ],
  "cross_dependencies": [
    {
      "from_bundle": "remotebullseyeleague_assets_all.bundle",
      "to_bundle": "remotetnt_assets_all.bundle",
      "from_group": "RemoteBullseyeLeague",
      "to_group": "RemoteTnt",
      "type": "remote_to_remote",
      "assets": ["SpriteDraw3DAlways"]
    }
  ]
}
```

## Web UI Tabs

### 1. Dashboard

Overview cards + summary:
- Total bundles, total size, total assets
- Duplicate count + estimated waste
- Top 5 largest bundles
- If previous build exists: delta summary (new duplicates, resolved, size change)

### 2. Duplicates

Table with columns:
- Asset name / path
- Times duplicated
- Estimated waste (bytes)
- Bundle names where it appears
- Sortable by waste size (default), count, name

Severity color coding:
- Red: appears in 5+ bundles
- Orange: appears in 3-4 bundles
- Yellow: appears in 2 bundles

### 3. Dependencies

Two views:
- **Table view**: Bundle -> dependency bundle list, filterable
- **Highlight**: Remote-to-remote dependencies shown in red (these cause the cache race condition crashes)

Filter options:
- Show all / Remote only / Cross-group only
- Search by bundle or group name

### 4. Bundle Sizes

- Bar chart (Chart.js) showing top 30 bundles by size
- Full table: bundle name, group, size, asset count, dependency size, remote/local
- Sortable columns

### 5. Build Diff

- Dropdown to select two builds to compare
- Sections:
  - New duplicates (didn't exist before)
  - Resolved duplicates (existed before, now gone)
  - Size changes per bundle (sorted by delta)
  - Added/removed bundles
  - Dependency changes

## Project Structure

```
addressable-analyzer/
  run.py                    # Entry point: parse + serve
  config.json               # Auto-created on first run
  analyzer/
    __init__.py
    parser.py               # Parse buildlayout.json, resolve rid references
    report.py               # Generate analysis report from parsed data
    storage.py              # Save/load report snapshots
    diff.py                 # Compare two reports
    server.py               # HTTP server + API endpoints
  web/
    index.html              # Single page app with tabs
    style.css               # Styling
    app.js                  # Tab switching, data fetching, table rendering
    chart.js (CDN)          # Charts
  docs/
    plans/
      2026-03-06-addressable-analyzer-design.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve index.html |
| GET | `/api/report` | Current build analysis |
| GET | `/api/reports` | List of saved reports |
| GET | `/api/diff?a=<id>&b=<id>` | Diff between two reports |
| POST | `/api/reload` | Re-parse buildlayout.json and save new snapshot |

## Parser Strategy

The `rid`-based reference system requires a two-pass approach:

1. **Pass 1**: Build `rid -> data` lookup dict from `references.RefIds`
2. **Pass 2**: Resolve all `{"rid": N}` references recursively to build the full object graph

This turns 43MB of cross-referenced JSON into a flat, queryable structure.

## Tech Stack

- **Python 3.8+** (no external dependencies for core)
- **Built-in `http.server`** for serving
- **Vanilla HTML/CSS/JS** for frontend
- **Chart.js via CDN** for charts
- Zero `pip install` required
