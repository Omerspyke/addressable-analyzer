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
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config.update(json.load(f))
    if not config["project_name"]:
        config["project_name"] = _detect_project_name(project_dir or os.getcwd())
    if project_dir and not os.path.isabs(config["buildlayout_path"]):
        config["buildlayout_path"] = os.path.join(project_dir, config["buildlayout_path"])
    return config


def save_default_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)


def _detect_project_name(project_dir):
    settings_path = os.path.join(project_dir, "ProjectSettings", "ProjectSettings.asset")
    if os.path.exists(settings_path):
        with open(settings_path, "r", errors="ignore") as f:
            for line in f:
                if "productName:" in line:
                    return line.split("productName:")[-1].strip()
    return os.path.basename(project_dir)
