import os
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


def compare_apks(old_path, new_path):
    old_files = _read_zip(old_path)
    new_files = _read_zip(new_path)

    old_total = sum(old_files.values())
    new_total = sum(new_files.values())

    all_names = sorted(set(old_files) | set(new_files))

    # Per-file diff
    changes = []
    for name in all_names:
        old_size = old_files.get(name, 0)
        new_size = new_files.get(name, 0)
        delta = new_size - old_size
        if old_size == 0:
            status = "added"
        elif new_size == 0:
            status = "removed"
        elif delta != 0:
            status = "changed"
        else:
            status = "unchanged"

        if status != "unchanged":
            changes.append({
                "name": name,
                "old_size": old_size,
                "new_size": new_size,
                "delta": delta,
                "status": status,
                "category": _categorize(name),
            })

    changes.sort(key=lambda c: abs(c["delta"]), reverse=True)

    # Category summary
    categories = {}
    for name in all_names:
        cat = _categorize(name)
        if cat not in categories:
            categories[cat] = {"old_size": 0, "new_size": 0}
        categories[cat]["old_size"] += old_files.get(name, 0)
        categories[cat]["new_size"] += new_files.get(name, 0)

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


def _categorize(name):
    for prefix, label in CATEGORIES.items():
        if prefix == "classes":
            if name.startswith("classes") and name.endswith(".dex"):
                return label
        elif name.startswith(prefix) or name == prefix:
            return label
    return "Other"
