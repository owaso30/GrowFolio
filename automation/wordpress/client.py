"""WordPress REST API クライアント。"""
from __future__ import annotations

import base64
import mimetypes
from typing import Any

import requests

from config_loader import get_wp_credentials


class WordPressClient:
    def __init__(self) -> None:
        self.base_url, self.user, self.password = get_wp_credentials()
        self.api = f"{self.base_url}/wp-json/wp/v2"
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "User-Agent": "GrowfolioAutomation/1.0",
        }

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = requests.get(f"{self.api}/{path}", headers=self.headers, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict, files: dict | None = None) -> Any:
        headers = dict(self.headers)
        if files:
            headers.pop("Content-Type", None)
            r = requests.post(f"{self.api}/{path}", headers=headers, data=data, files=files, timeout=120)
        else:
            headers["Content-Type"] = "application/json"
            r = requests.post(f"{self.api}/{path}", headers=headers, json=data, timeout=120)
        r.raise_for_status()
        return r.json()

    def list_posts(self, status: str = "publish", per_page: int = 100) -> list[dict]:
        posts: list[dict] = []
        page = 1
        while True:
            batch = self._get("posts", {"status": status, "per_page": per_page, "page": page, "_embed": 1})
            if not batch:
                break
            posts.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return posts

    def get_categories(self) -> list[dict]:
        cats: list[dict] = []
        page = 1
        while True:
            batch = self._get("categories", {"per_page": 100, "page": page})
            if not batch:
                break
            cats.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return cats

    def ensure_category(self, name: str) -> int:
        for cat in self.get_categories():
            if cat.get("name") == name:
                return int(cat["id"])
        created = self._post("categories", {"name": name})
        return int(created["id"])

    def upload_media(self, file_bytes: bytes, filename: str, alt_text: str) -> int:
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "image/png"
        files = {"file": (filename, file_bytes, mime)}
        data = {"alt_text": alt_text, "title": alt_text}
        result = self._post("media", data, files=files)
        return int(result["id"])

    def create_post(
        self,
        title: str,
        content: str,
        slug: str,
        category_id: int,
        status: str,
        featured_media: int | None,
        meta_title: str,
        meta_description: str,
    ) -> dict:
        payload: dict[str, Any] = {
            "title": title,
            "content": content,
            "slug": slug,
            "status": status,
            "categories": [category_id],
            "meta": {
                "_ssp_meta_title": meta_title,
                "_ssp_meta_description": meta_description,
            },
        }
        if featured_media:
            payload["featured_media"] = featured_media
        return self._post("posts", payload)
