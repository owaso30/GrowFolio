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
    previous = {
        int(item["id"]): item
        for item in load_json("published.json").get("posts", [])
        if item.get("id")
    }
    for post in client.list_posts():
        slug = post.get("slug", "")
        title = post.get("title", {})
        if isinstance(title, dict):
            title = title.get("rendered", "")
        link = post.get("link", f"{base}/{slug}/")
        cats = []
        tags = []
        embedded = post.get("_embedded", {})
        for term_group in embedded.get("wp:term", []):
            for term in term_group:
                if term.get("taxonomy") == "category":
                    cats.append(term.get("name", ""))
                elif term.get("taxonomy") == "post_tag":
                    tags.append(term.get("name", ""))
        prev = previous.get(int(post["id"]), {})
        posts_out.append({
            "id": post["id"],
            "slug": slug,
            "title": title,
            "url": link,
            "categories": cats or prev.get("categories") or [],
            "tags": tags or prev.get("tags") or [],
            "keywords": prev.get("keywords") or [title],
            "recap": prev.get("recap") or "",
            "source": prev.get("source") or "sync",
            "cluster": prev.get("cluster") or "",
            "published_at": prev.get("published_at") or post.get("date_gmt") or "",
        })

    data = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "posts": posts_out,
    }
    save_json("published.json", data)
    print(f"Synced {len(posts_out)} posts")
    return data
