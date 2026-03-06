from datetime import datetime


def generate_report(parsed_data):
    bundles = []
    for group in parsed_data["groups"]:
        for bundle in group["bundles"]:
            bundles.append(bundle)

    total_size = sum(b["size"] for b in bundles)
    total_assets = sum(b["asset_count"] for b in bundles)
    remote_bundles = [b for b in bundles if b["is_remote"]]
    local_bundles = [b for b in bundles if not b["is_remote"]]

    remote_names = {b["name"] for b in remote_bundles}
    local_names = {b["name"] for b in local_bundles}
    bundle_lookup = {b["name"]: b for b in bundles}

    cross_deps = []
    warnings = []

    for bundle in bundles:
        for dep in bundle.get("dependencies", []):
            dep_name = dep["bundle_name"]
            dep_bundle = bundle_lookup.get(dep_name, {})
            dep_is_remote = dep_bundle.get("is_remote", False)

            # Remote → Remote: only warn if DIFFERENT groups
            if bundle["is_remote"] and dep_is_remote:
                dep_group = _find_group_for_bundle(parsed_data["groups"], dep_name)
                cross_deps.append({
                    "from_bundle": bundle["name"],
                    "from_group": bundle["group"],
                    "to_bundle": dep_name,
                    "to_group": dep_group,
                    "efficiency": dep["efficiency"],
                })
                # Same group dependencies are normal (PackSeparately bundles)
                if bundle["group"] != dep_group:
                    warnings.append({
                        "severity": "high",
                        "type": "remote_to_remote",
                        "title": "Remote depends on Remote",
                        "description": f"Remote bundle depends on a different remote group's bundle. "
                                       f"If both download concurrently, cache race condition "
                                       f"can cause 'Couldn\\'t move cache data' crashes.",
                        "from_bundle": bundle["name"],
                        "from_group": bundle["group"],
                        "to_bundle": dep_name,
                        "to_group": dep_group,
                })

            # Local → Remote: local can't load until remote is downloaded
            if not bundle["is_remote"] and dep_is_remote:
                warnings.append({
                    "severity": "medium",
                    "type": "local_to_remote",
                    "title": "Local depends on Remote",
                    "description": f"Local bundle has a dependency on a remote bundle. "
                                   f"This local bundle cannot load until the remote "
                                   f"bundle is downloaded, defeating the purpose of being local.",
                    "from_bundle": bundle["name"],
                    "from_group": bundle["group"],
                    "to_bundle": dep_name,
                    "to_group": _find_group_for_bundle(parsed_data["groups"], dep_name),
                })

    # Deduplicate warnings by (from_group, to_group, type) — show group-level, not per-bundle
    seen_group_warnings = set()
    grouped_warnings = []
    for w in warnings:
        key = (w["from_group"], w["to_group"], w["type"])
        if key not in seen_group_warnings:
            seen_group_warnings.add(key)
            # Count how many bundle-level entries share this group pair
            count = sum(1 for w2 in warnings
                        if w2["from_group"] == w["from_group"]
                        and w2["to_group"] == w["to_group"]
                        and w2["type"] == w["type"])
            w["count"] = count
            grouped_warnings.append(w)

    # Sort: high severity first, then by count
    grouped_warnings.sort(key=lambda w: (0 if w["severity"] == "high" else 1, -w["count"]))

    warning_counts = {
        "high": sum(1 for w in grouped_warnings if w["severity"] == "high"),
        "medium": sum(1 for w in grouped_warnings if w["severity"] == "medium"),
    }

    return {
        "project_name": "",
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
            "warning_count": len(grouped_warnings),
            "warning_high": warning_counts["high"],
            "warning_medium": warning_counts["medium"],
        },
        "bundles": sorted(bundles, key=lambda b: b["size"], reverse=True),
        "duplicates": parsed_data["duplicates"],
        "cross_dependencies": cross_deps,
        "warnings": grouped_warnings,
    }


def _find_group_for_bundle(groups, bundle_name):
    for group in groups:
        for bundle in group["bundles"]:
            if bundle["name"] == bundle_name:
                return group["name"]
    return "Unknown"
