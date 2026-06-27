"""公開済み記事の同期。"""
from __future__ import annotations

from datetime import datetime, timezone

from config_loader import load_yaml, load_json, save_json
from wordpress.client import WordPressClient


def sync_posts() -> dict:
    client = WordPressClient()
    site = load_yaml("site.yaml")
    base = site["site"]["url"].rstrip("/")

    posts_out = []
    for post in client.list_posts():
        slug = post.get("slug", "")
        title = post.get("title", {})
        if isinstance(title, dict):
            title = title.get("rendered", "")
        link = post.get("link", f"{base}/{slug}/")
        cats = []
        embedded = post.get("_embedded", {})
        for term_group in embedded.get("wp:term", []):
            for term in term_group:
                if term.get("taxonomy") == "category":
                    cats.append(term.get("name", ""))
        posts_out.append({
            "id": post["id"],
            "slug": slug,
            "title": title,
            "url": link,
            "categories": cats,
            "keywords": [title],
        })

    data = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "posts": posts_out,
    }
    save_json("published.json", data)
    print(f"Synced {len(posts_out)} posts")
    return data
