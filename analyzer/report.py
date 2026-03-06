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
        },
        "bundles": sorted(bundles, key=lambda b: b["size"], reverse=True),
        "duplicates": parsed_data["duplicates"],
        "cross_dependencies": cross_deps,
    }


def _find_group_for_bundle(groups, bundle_name):
    for group in groups:
        for bundle in group["bundles"]:
            if bundle["name"] == bundle_name:
                return group["name"]
    return "Unknown"
