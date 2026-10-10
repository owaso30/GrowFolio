"""Flux による画像生成（アイキャッチ + 本文0〜1枚）。"""
from __future__ import annotations

from typing import Any

from config_loader import load_yaml
from images.brand_image import (
    _editorial_flux_prompt,
    brand_caption,
    compose_brand_image,
    compose_hybrid_brand_image,
    pick_brand_key,
)
from images.flux_client import generate_image_bytes
from seo.ssp_meta import build_featured_alt


def _image_limits() -> tuple[int, str, str]:
    cfg = load_yaml("site.yaml").get("content", {})
    body_count = max(0, min(int(cfg.get("body_images", 0)), 1))
    featured_size = cfg.get("featured_image_size", "1792x1024")
    body_size = cfg.get("body_image_size", "1024x1024")
    return body_count, featured_size, body_size


def _image_bytes(
    item: dict[str, Any],
    *,
    keyword: str,
    title: str,
    slug: str = "",
    size: str,
    role: str = "featured",
) -> tuple[bytes, str]:
    """Returns (png bytes, figcaption)."""
    source = str(item.get("source", "flux")).lower()
    scene_prompt = str(item.get("scene_prompt", "") or item.get("prompt", "")).strip()
    brand_key = pick_brand_key(keyword, title, slug=slug) or ""

    if source == "brand" and brand_key:
        try:
            if role == "featured":
                return (
                    compose_hybrid_brand_image(
                        brand_key,
                        keyword=keyword,
                        title=title,
                        slug=slug,
                        scene_prompt=scene_prompt,
                        size=size,
                    ),
                    brand_caption(brand_key, hybrid=True),
                )
            return compose_brand_image(brand_key, size), brand_caption(brand_key)
        except Exception:
            pass

    prompt = scene_prompt or _editorial_flux_prompt(keyword, title, brand_key, slug)
    return generate_image_bytes(prompt, size=size, role=role), "※参考イメージ"


def process_images(article: dict[str, Any], keyword: str) -> tuple[list[dict], str]:
    """Returns list of {bytes, filename, alt} and updated HTML body."""
    from html import escape

    from content.affiliate_renderer import prepare_shop_image_placeholders
    from content.generator import markdown_to_html

    _max_body, featured_size, _body_size = _image_limits()
    markdown, shop_jobs = prepare_shop_image_placeholders(article.get("markdown_body", ""))
    html = markdown_to_html(markdown)
    images: list[dict] = []
    prompts = article.get("image_prompts") or []
    title = str(article.get("title", ""))
    slug = str(article.get("slug", ""))

    feat = prompts[0] if prompts else {}
    feat_alt = build_featured_alt(article, keyword)
    feat_bytes, _ = _image_bytes(
        feat, keyword=keyword, title=title, slug=slug, size=featured_size, role="featured"
    )
    from images.featured_frame import compose_featured_bytes

    feat_bytes = compose_featured_bytes(
        title=title,
        category=str(article.get("category") or ""),
        tags=list(article.get("tags") or []),
        caption=str(feat.get("caption") or ""),
        inner_bytes=feat_bytes,
    )
    images.append({
        "bytes": feat_bytes,
        "filename": "featured.png",
        "alt": feat_alt,
        "role": "featured",
    })

    catch_prompts = [item for item in prompts[1:] if item.get("role") == "catch"][:1]
    for i, item in enumerate(catch_prompts, start=1):
        prompt = str(item.get("scene_prompt") or item.get("prompt") or title)
        img_bytes = generate_image_bytes(prompt, size="1792x1024", role="catch")
        alt = str(item.get("alt") or keyword)[:100]
        caption = str(item.get("caption") or "この日の釣果です。")
        ext = "jpg" if img_bytes[:3] == b"\xff\xd8\xff" else "png"
        filename = f"body-{i}.{ext}"
        images.append({"bytes": img_bytes, "filename": filename, "alt": alt, "role": "body"})
        placeholder = str(item.get("placeholder") or f"[IMAGE:{i}]")
        figure = (
            '<figure style="margin:1.2em 0;">'
            f'<img src="BODY_IMAGE_{i}" alt="{escape(alt)}" style="max-width:100%;height:auto;" />'
            f'<figcaption style="font-size:.85em;line-height:1.6;color:#666;">{escape(caption)}</figcaption>'
            "</figure>"
        )
        if placeholder in html:
            html = html.replace(placeholder, figure)
        else:
            html += figure

    for job in shop_jobs:
        prompt = (
            f"The exact fishing product named: {job['query']}. "
            "Show that one product, not a different lure and not a fish."
        )
        img_bytes = generate_image_bytes(prompt, size="1024x1024", role="shop")
        ext = "jpg" if img_bytes[:3] == b"\xff\xd8\xff" else "png"
        images.append({
            "bytes": img_bytes,
            "filename": f"{job['placeholder'].lower()}.{ext}",
            "alt": job["alt"][:100],
            "role": "shop",
            "placeholder": job["placeholder"],
        })

    return images, html
