"""公開済み記事の「参考・関連情報」を文字リンク形式へ一括更新。"""
from __future__ import annotations

from content.source_links import format_source_section_html, needs_source_link_format
from seo.content_policy import get_editorial_policy
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


def apply_source_links_to_posts(
    *,
    dry_run: bool = False,
    slug: str | None = None,
    post_id: int | None = None,
) -> list[dict]:
    """参考・関連情報の裸URLを文字リンク化して WordPress を更新。"""
    client = WordPressClient()
    editorial = get_editorial_policy()
    source_h = editorial.get("source_section_heading", "参考・関連情報")
    results: list[dict] = []

    for post in client.list_posts(context="edit"):
        post_slug = post.get("slug", "")
        pid = int(post["id"])
        if slug and post_slug != slug:
            continue
        if post_id and pid != post_id:
            continue

        content = _post_content(post)
        if not needs_source_link_format(content, source_h):
            continue

        new_content = format_source_section_html(content, source_h)
        if new_content == content:
            continue

        entry = {
            "id": pid,
            "slug": post_slug,
            "title": _post_title(post),
            "updated": not dry_run,
        }
        results.append(entry)

        if dry_run:
            print(f"  [dry-run] would update: {post_slug} (id={pid})")
            continue

        client.update_post(pid, {"content": new_content})
        print(f"  updated: {post_slug} (id={pid})")

    print(f"{'Would update' if dry_run else 'Updated'} {len(results)} post(s)")
    return results
