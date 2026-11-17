"""Settings stored as JSON in the user's profile folder."""
from __future__ import annotations

import copy
import json
import os
import sys

APP_NAME = "myDB"
# When packaged as myDB.app (PyInstaller) bundled files live in sys._MEIPASS.
PROJECT_DIR = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG = {
    "hotkey": "<ctrl>+<shift>+s",
    "auto_paste": False,        # paste into the previous window after copying
    "all_info_format": "lines",  # lines | tsv | json
    "max_results": 500,
    "databases": [
        {
            "name": "Simple (sample)",
            "path": os.path.join(PROJECT_DIR, "data", "sample_simple.csv"),
            "part_number_column": "",
            "price_column": "",
        },
        {
            "name": "Enhanced (sample)",
            "path": os.path.join(PROJECT_DIR, "data", "sample_enhanced.csv"),
            "part_number_column": "",
            "price_column": "",
        },
    ],
}


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    return os.environ.get("MYDB_CONFIG") or os.path.join(config_dir(), "config.json")


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    path = config_path()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    return cfg


def save_config(cfg: dict) -> None:
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
