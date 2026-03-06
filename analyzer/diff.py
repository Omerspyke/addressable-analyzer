def diff_reports(old_report, new_report):
    if not old_report or not new_report:
        return None

    old_summary = old_report.get("summary", {})
    new_summary = new_report.get("summary", {})

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
