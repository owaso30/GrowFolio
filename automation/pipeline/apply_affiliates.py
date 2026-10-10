"""公開済み記事のアフィリエイト配置を intro / mid / end バナー形式へ更新。"""
from __future__ import annotations

from config_loader import load_yaml
from content.affiliate_renderer import reapply_affiliates_to_html
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


def _tackle_placements(title: str, slug: str) -> list[dict]:
    query = title or slug.replace("-", " ")
    return [
        {
            "program": "amazon_search",
            "slot": "mid",
            "query": query,
            "heading": "この記事で触れた道具を探す",
            "teaser": "全部買い直さず、記事で触れたタックルだけを確認できます。",
            "anchor": "関連タックルをAmazonで探す",
        }
    ]


def apply_affiliates_to_posts(
    *,
    dry_run: bool = False,
    slug: str | None = None,
    post_id: int | None = None,
) -> list[dict]:
    """公開済み記事に Amazon のタックル検索バナーを配置する。"""
    client = WordPressClient()
    site_url = load_yaml("site.yaml")["site"]["url"]
    editorial = get_editorial_policy()
    results: list[dict] = []

    for post in client.list_posts(context="edit"):
        post_slug = post.get("slug", "")
        pid = int(post["id"])
        if slug and post_slug != slug:
            continue
        if post_id and pid != post_id:
            continue
        if not slug and not post_id:
            continue

        content = _post_content(post)
        if not content:
            continue

        title = _post_title(post)
        new_content = reapply_affiliates_to_html(
            content,
            _tackle_placements(title, post_slug),
            site_url=site_url,
            keyword=title or post_slug.replace("-", " "),
            fact_heading=editorial.get("fact_section_heading", "現場の条件（事実）"),
            opinion_heading=editorial.get("opinion_section_heading", "週末にやるなら（判断）"),
            source_heading=editorial.get("source_section_heading", "参考・関連情報"),
        )
        if new_content == content:
            continue

        results.append({
            "id": pid,
            "slug": post_slug,
            "title": title,
            "updated": not dry_run,
        })
        if dry_run:
            print(f"  [dry-run] would update: {post_slug} (id={pid})")
            continue

        client.update_post(pid, {"content": new_content})
        print(f"  updated: {post_slug} (id={pid})")

    print(f"{'Would update' if dry_run else 'Updated'} {len(results)} post(s)")
    return results
