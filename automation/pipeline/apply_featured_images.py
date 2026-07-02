"""公開済み記事のアイキャッチをハイブリッド画像（ロゴ＋テーマ写真）へ一括更新。"""
from __future__ import annotations

from images.brand_image import compose_hybrid_brand_image, pick_brand_key
from images.generator import _image_limits
from seo.ssp_meta import build_featured_alt
from wordpress.client import WordPressClient


def _post_title(post: dict) -> str:
    title = post.get("title") or {}
    if isinstance(title, dict):
        return title.get("rendered") or title.get("raw") or ""
    return str(title)


def _category_names(post: dict) -> str:
    names: list[str] = []
    for term_group in (post.get("_embedded") or {}).get("wp:term", []):
        for term in term_group:
            if term.get("taxonomy") == "category":
                names.append(str(term.get("name", "")))
    return " ".join(names)


def _is_bitradex_post(slug: str) -> bool:
    return str(slug).lower().startswith("bitradex")


def apply_featured_images_to_posts(
    *,
    dry_run: bool = False,
    slug: str | None = None,
    post_id: int | None = None,
) -> list[dict]:
    client = WordPressClient()
    _, featured_size, _ = _image_limits()
    results: list[dict] = []

    for post in client.list_posts(context="edit"):
        pid = int(post["id"])
        post_slug = post.get("slug", "")
        if post_id and pid != post_id:
            continue
        if slug and post_slug != slug:
            continue

        if _is_bitradex_post(post_slug):
            results.append({
                "id": pid,
                "slug": post_slug,
                "skipped": True,
                "reason": "bitradex featured image preserved",
            })
            continue

        title = _post_title(post)
        category = _category_names(post)
        keyword = title
        brand_key = pick_brand_key(keyword, title, category, post_slug)
        if not brand_key:
            results.append({
                "id": pid,
                "slug": post_slug,
                "skipped": True,
                "reason": "brand_key not detected",
            })
            continue

        alt = build_featured_alt({"title": title, "image_prompts": [{"alt": title}]}, keyword)
        entry = {"id": pid, "slug": post_slug, "brand_key": brand_key, "alt": alt}

        if dry_run:
            entry["dry_run"] = True
            results.append(entry)
            continue

        img_bytes = compose_hybrid_brand_image(
            brand_key,
            keyword=keyword,
            title=title,
            slug=post_slug,
            size=featured_size,
        )
        media_id = client.upload_media(img_bytes, f"featured-{post_slug}.png", alt)
        client.update_post(pid, {"featured_media": media_id})
        entry["featured_media"] = media_id
        results.append(entry)
        print(f"Updated featured image: {post_slug} (media #{media_id})")

    return results
