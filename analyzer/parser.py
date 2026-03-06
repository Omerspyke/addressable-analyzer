import json
import os


def parse_build_layout(path):
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
    return {r["rid"]: r for r in ref_ids}


def _resolve_group(rid_map, group_rid):
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
    entry = rid_map.get(bundle_rid)
    if not entry or entry.get("type", {}).get("class") != "BuildLayout/Bundle":
        return None

    data = entry["data"]

    dependencies = []
    for dep in data.get("BundleDependencies", []):
        dep_bundle_rid = dep.get("DependencyBundle", {}).get("rid")
        dep_entry = rid_map.get(dep_bundle_rid, {})
        dep_data = dep_entry.get("data", {})
        if dep_data:
            asset_deps = []
            for ad in dep.get("AssetDependencies", []):
                root_data = rid_map.get(ad["rootAsset"]["rid"], {}).get("data", {})
                dep_asset_data = rid_map.get(ad["dependencyAsset"]["rid"], {}).get("data", {})
                asset_deps.append({
                    "root_asset": root_data.get("AssetPath", ""),
                    "dependency_asset": dep_asset_data.get("AssetPath", ""),
                })
            dependencies.append({
                "bundle_name": dep_data.get("Name", ""),
                "efficiency": dep.get("Efficiency", 0),
                "asset_dependencies": asset_deps,
            })

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
    result = []
    for dup in duplicated_assets:
        guid = dup["AssetGuid"]
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

    result.sort(key=lambda x: x["bundle_count"], reverse=True)
    return result


def _find_asset_path(guid, rid_map):
    for entry in rid_map.values():
        data = entry.get("data", {})
        if data.get("AssetGuid") == guid or data.get("Guid") == guid:
            path = data.get("AssetPath", "")
            if path:
                return path
    return ""


def _target_name(target_id):
    targets = {
        9: "iOS",
        13: "Android",
        19: "StandaloneWindows64",
        2: "StandaloneOSX",
    }
    return targets.get(target_id, f"Unknown({target_id})")
