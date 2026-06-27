"""Flux による画像生成（アイキャッチ + 本文0〜1枚）。"""
from __future__ import annotations

from typing import Any

from config_loader import load_yaml
from images.flux_client import generate_image_bytes


def _image_limits() -> tuple[int, str, str]:
    cfg = load_yaml("site.yaml").get("content", {})
    body_count = max(0, min(int(cfg.get("body_images", 0)), 1))
    featured_size = cfg.get("featured_image_size", "1792x1024")
    body_size = cfg.get("body_image_size", "1024x1024")
    return body_count, featured_size, body_size


def process_images(article: dict[str, Any], keyword: str) -> tuple[list[dict], str]:
    """Returns list of {bytes, filename, alt} and updated HTML body."""
    from content.generator import markdown_to_html

    max_body, featured_size, body_size = _image_limits()
    html = markdown_to_html(article.get("markdown_body", ""))
    images: list[dict] = []
    prompts = article.get("image_prompts") or []

    feat = prompts[0] if prompts else {}
    feat_prompt = feat.get("prompt") or f"Conceptual illustration about {keyword}, fintech, no text"
    feat_alt = feat.get("alt", keyword)
    images.append({
        "bytes": generate_image_bytes(feat_prompt, size=featured_size, role="featured"),
        "filename": "featured.png",
        "alt": feat_alt,
        "role": "featured",
    })

    for i, item in enumerate(prompts[1 : 1 + max_body], start=1):
        placeholder = item.get("placeholder", f"[IMAGE:{i}]")
        img_bytes = generate_image_bytes(item.get("prompt", keyword), size=body_size, role="body")
        alt = item.get("alt", keyword)
        filename = f"body-{i}.png"
        images.append({"bytes": img_bytes, "filename": filename, "alt": alt, "role": "body"})

        figure = (
            f'<figure class="wp-block-image">'
            f'<img src="BODY_IMAGE_{i}" alt="{alt}" />'
            f'<figcaption>※イメージ図</figcaption></figure>'
        )
        if placeholder in html:
            html = html.replace(placeholder, figure)
        else:
            html += figure

    return images, html
