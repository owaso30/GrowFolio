"""Google API 認証（サービスアカウント）。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2 import service_account

from config_loader import load_env

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def get_credentials():
    """GOOGLE_SERVICE_ACCOUNT_JSON（生JSON）または GOOGLE_APPLICATION_CREDENTIALS（パス）から認証。"""
    load_env()
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path and Path(path).is_file():
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    raise RuntimeError(
        "Google認証がありません。"
        "GOOGLE_SERVICE_ACCOUNT_JSON（JSON文字列）または "
        "GOOGLE_APPLICATION_CREDENTIALS（鍵ファイルパス）を設定してください。"
    )
