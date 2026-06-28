"""公開済み記事の本文に強調装飾（cap_box / mark）を一括適用。"""
from __future__ import annotations

from content.emphasis import apply_emphasis_html, needs_emphasis
from wordpress.client import WordPressClient


def _post_content(post: dict) -> str:
    content = post.get("content") or {}
    if isinstance(content, dict):
        return content.get("raw") or content.get("rendered") or ""
    return str(content)


def _post_title(post: dict) -> str:
    title = post.get("title") or {}
    if isinstance(title, dict):
        return title.get("rendered") or title.get("raw") or ""
    return str(title)


def apply_emphasis_to_posts(
    *,
    dry_run: bool = False,
    slug: str | None = None,
) -> list[dict]:
    """公開済み記事の HTML 本文で強調ショートコードを SWELL 装飾に変換して更新。"""
    client = WordPressClient()
    results: list[dict] = []

    for post in client.list_posts(context="edit"):
        post_slug = post.get("slug", "")
        if slug and post_slug != slug:
            continue

        content = _post_content(post)
        if not needs_emphasis(content):
            continue

        new_content = apply_emphasis_html(content)
        if new_content == content:
            continue

        post_id = int(post["id"])
        entry = {
            "id": post_id,
            "slug": post_slug,
            "title": _post_title(post),
            "updated": not dry_run,
        }
        results.append(entry)

        if dry_run:
            print(f"  [dry-run] would update: {post_slug} (id={post_id})")
            continue

        client.update_post(post_id, {"content": new_content})
        print(f"  updated: {post_slug} (id={post_id})")

    print(f"{'Would update' if dry_run else 'Updated'} {len(results)} post(s)")
    return results
