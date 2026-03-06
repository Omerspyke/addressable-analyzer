import os
import re
import zipfile


CATEGORIES = {
    "assets/": "Assets (Addressables, StreamingAssets)",
    "lib/": "Native Libraries (lib/)",
    "classes": "Code (DEX)",
    "res/": "Resources (res/)",
    "resources.arsc": "Resource Table",
    "META-INF/": "Signing & Metadata",
    "kotlin/": "Kotlin Metadata",
    "AndroidManifest.xml": "Manifest",
}

# Pattern to match bundle hash: _<32 hex chars>.bundle
_BUNDLE_HASH_RE = re.compile(r'_[a-f0-9]{32}\.bundle$')


def compare_apks(old_path, new_path):
    old_files = _read_zip(old_path)
    new_files = _read_zip(new_path)

    old_total = sum(old_files.values())
    new_total = sum(new_files.values())

    # Normalize bundle names (strip hash) to match across builds
    old_normalized = {_normalize_name(k): k for k in old_files}
    new_normalized = {_normalize_name(k): k for k in new_files}

    all_keys = sorted(set(old_normalized) | set(new_normalized))

    changes = []
    for key in all_keys:
        old_real = old_normalized.get(key)
        new_real = new_normalized.get(key)
        old_size = old_files.get(old_real, 0) if old_real else 0
        new_size = new_files.get(new_real, 0) if new_real else 0
        delta = new_size - old_size

        if not old_real:
            status = "added"
        elif not new_real:
            status = "removed"
        elif delta != 0:
            status = "changed"
        else:
            status = "unchanged"

        if status != "unchanged":
            display_name = new_real or old_real
            changes.append({
                "name": display_name,
                "display_name": key,
                "old_size": old_size,
                "new_size": new_size,
                "delta": delta,
                "status": status,
                "category": _categorize(key),
            })

    changes.sort(key=lambda c: abs(c["delta"]), reverse=True)

    # Category summary
    categories = {}
    for key in all_keys:
        cat = _categorize(key)
        if cat not in categories:
            categories[cat] = {"old_size": 0, "new_size": 0}
        old_real = old_normalized.get(key)
        new_real = new_normalized.get(key)
        categories[cat]["old_size"] += old_files.get(old_real, 0) if old_real else 0
        categories[cat]["new_size"] += new_files.get(new_real, 0) if new_real else 0

    category_summary = []
    for cat, sizes in sorted(categories.items(), key=lambda x: abs(x[1]["new_size"] - x[1]["old_size"]), reverse=True):
        category_summary.append({
            "category": cat,
            "old_size": sizes["old_size"],
            "new_size": sizes["new_size"],
            "delta": sizes["new_size"] - sizes["old_size"],
        })

    return {
        "old_name": os.path.basename(old_path),
        "new_name": os.path.basename(new_path),
        "old_total": old_total,
        "new_total": new_total,
        "total_delta": new_total - old_total,
        "total_files_old": len(old_files),
        "total_files_new": len(new_files),
        "added": sum(1 for c in changes if c["status"] == "added"),
        "removed": sum(1 for c in changes if c["status"] == "removed"),
        "changed": sum(1 for c in changes if c["status"] == "changed"),
        "categories": category_summary,
        "changes": changes,
    }


def _read_zip(path):
    files = {}
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if not info.is_dir():
                files[info.filename] = info.file_size
    return files


def _normalize_name(name):
    """Strip bundle hash so same bundle matches across builds."""
    return _BUNDLE_HASH_RE.sub('.bundle', name)


def _categorize(name):
    for prefix, label in CATEGORIES.items():
        if prefix == "classes":
            if name.startswith("classes") and name.endswith(".dex"):
                return label
        elif name.startswith(prefix) or name == prefix:
            return label
    return "Other"
