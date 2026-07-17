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
    llm_brand = str(item.get("brand_key", "")).strip()
    scene_prompt = str(item.get("scene_prompt", "") or item.get("prompt", "")).strip()
    # 主題検出を最優先（LLMが誤って claude 等を付けても ChatGPT 記事は chatgpt にする）
    detected = pick_brand_key(keyword, title, slug=slug) or ""
    brand_key = detected or llm_brand
    resolved_brand = brand_key

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

    prompt = scene_prompt or _editorial_flux_prompt(keyword, title, resolved_brand, slug)
    return generate_image_bytes(prompt, size=size, role=role), "※参考イメージ"


def process_images(article: dict[str, Any], keyword: str) -> tuple[list[dict], str]:
    """Returns list of {bytes, filename, alt} and updated HTML body."""
    from content.generator import markdown_to_html

    max_body, featured_size, body_size = _image_limits()
    html = markdown_to_html(article.get("markdown_body", ""))
    images: list[dict] = []
    prompts = article.get("image_prompts") or []
    title = str(article.get("title", ""))
    slug = str(article.get("slug", ""))

    feat = prompts[0] if prompts else {}
    feat_alt = build_featured_alt(article, keyword)
    feat_bytes, _ = _image_bytes(
        feat, keyword=keyword, title=title, slug=slug, size=featured_size, role="featured"
    )
    images.append({
        "bytes": feat_bytes,
        "filename": "featured.png",
        "alt": feat_alt,
        "role": "featured",
    })

    for i, item in enumerate(prompts[1 : 1 + max_body], start=1):
        placeholder = item.get("placeholder", f"[IMAGE:{i}]")
        img_bytes, caption = _image_bytes(
            item, keyword=keyword, title=title, slug=slug, size=body_size, role="body"
        )
        alt = item.get("alt", keyword)
        filename = f"body-{i}.png"
        images.append({"bytes": img_bytes, "filename": filename, "alt": alt, "role": "body"})

        figure = (
            f'<figure class="wp-block-image">'
            f'<img src="BODY_IMAGE_{i}" alt="{alt}" />'
            f"<figcaption>{caption}</figcaption></figure>"
        )
        if placeholder in html:
            html = html.replace(placeholder, figure)
        else:
            html += figure

    return images, html
