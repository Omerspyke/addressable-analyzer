import json
import os

CONFIG_FILE = ".addressable-analyzer.json"

DEFAULTS = {
    "buildlayout_path": "Library/com.unity.addressables/buildlayout.json",
    "reports_dir": os.path.expanduser("~/.addressable-analyzer/reports"),
    "port": 8080,
}


def load_config(project_dir=None):
    project_dir = project_dir or os.getcwd()
    config = DEFAULTS.copy()
    config_path = os.path.join(project_dir, CONFIG_FILE)

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config.update(json.load(f))

    if not config.get("project_name"):
        config["project_name"] = _detect_project_name(project_dir)

    if not os.path.isabs(config["buildlayout_path"]):
        config["buildlayout_path"] = os.path.join(project_dir, config["buildlayout_path"])

    return config


def save_config(project_dir=None):
    """Create default config in Unity project dir if not exists."""
    project_dir = project_dir or os.getcwd()
    config_path = os.path.join(project_dir, CONFIG_FILE)
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            json.dump(DEFAULTS, f, indent=2)
        print(f"Config created: {config_path}")


def _detect_project_name(project_dir):
    settings_path = os.path.join(project_dir, "ProjectSettings", "ProjectSettings.asset")
    if os.path.exists(settings_path):
        with open(settings_path, "r", errors="ignore") as f:
            for line in f:
                if "productName:" in line:
                    return line.split("productName:")[-1].strip()
    return os.path.basename(project_dir)
