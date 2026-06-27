"""設定・データファイルの読み込み。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

AUTOMATION_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = AUTOMATION_ROOT / "config"
DATA_DIR = AUTOMATION_ROOT / "data"


def load_env() -> None:
    load_dotenv(AUTOMATION_ROOT / ".env")


def load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(name: str, data: dict[str, Any]) -> None:
    path = DATA_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_wp_credentials() -> tuple[str, str, str]:
    load_env()
    url = os.environ.get("WP_URL", "").rstrip("/")
    user = os.environ.get("WP_USER", "")
    password = os.environ.get("WP_APP_PASSWORD", "").replace(" ", "")
    if not all([url, user, password]):
        raise RuntimeError("WP_URL, WP_USER, WP_APP_PASSWORD を .env または環境変数に設定してください")
    return url, user, password


def get_anthropic_api_key() -> str:
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY を設定してください")
    return key


def get_fal_api_key() -> str:
    load_env()
    key = os.environ.get("FAL_KEY", "")
    if not key:
        raise RuntimeError("FAL_KEY を設定してください（fal.ai の API キー）")
    return key
