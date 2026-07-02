"""公開済み記事のアフィリエイト配置を intro / mid / end バナー形式へ更新。"""
from __future__ import annotations

from config_loader import load_yaml
from content.affiliate_renderer import (
    bitradex_affiliate_placements,
    it_career_affiliate_placements,
    reapply_affiliates_to_html,
)
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


def _is_bitradex_post(post: dict) -> bool:
    return str(post.get("slug", "")).startswith("bitradex")


def _is_it_career_post(post: dict) -> bool:
    slug = str(post.get("slug", "")).lower()
    return any(
        token in slug
        for token in ("copilot", "cursor", "vscode", "claude", "it-career")
    )


def _intro_query_for_post(post: dict, keyword: str) -> str:
    slug = post.get("slug", "")
    if "copilot" in slug or "copilot" in keyword.lower():
        return "GitHub Copilot AI開発 エンジニア"
    if "cursor" in slug or "vscode" in slug:
        return "AI コーディング エディタ 開発 入門"
    return keyword or "AI コーディング エディタ 開発 入門"


def apply_affiliates_to_posts(
    *,
    dry_run: bool = False,
    slug: str | None = None,
    post_id: int | None = None,
    bitradex_only: bool = False,
    all_posts: bool = False,
) -> list[dict]:
    """公開済み記事に intro / mid / end バナーを配置・更新。"""
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

        is_bitradex = _is_bitradex_post(post)
        is_it = _is_it_career_post(post)

        if all_posts:
            pass
        elif bitradex_only and not is_bitradex:
            continue
        elif not bitradex_only and not slug and not post_id:
            if not is_bitradex and not is_it:
                continue

        content = _post_content(post)
        if not content:
            continue

        keyword = post_slug.replace("-", " ")
        if is_bitradex:
            placements = bitradex_affiliate_placements(post_slug, _post_title(post))
        elif is_it:
            placements = it_career_affiliate_placements(
                intro_query=_intro_query_for_post(post, keyword)
            )
        else:
            placements = []

        new_content = reapply_affiliates_to_html(
            content,
            placements,
            site_url=site_url,
            keyword=keyword,
            fact_heading=editorial.get("fact_section_heading", "いま起きていること（事実）"),
            opinion_heading=editorial.get("opinion_section_heading", "筆者の考察・見解"),
            source_heading=editorial.get("source_section_heading", "参考・関連情報"),
        )

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
