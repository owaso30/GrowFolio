"""記事テーマに合わせた Flux 用の実写プロンプト。旧ブランドロゴ合成は使わない。"""
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
import yaml
from PIL import Image, ImageDraw

from config_loader import AUTOMATION_ROOT

ASSETS_DIR = AUTOMATION_ROOT / "assets" / "logos"
BRAND_ASSETS_PATH = AUTOMATION_ROOT / "config" / "brand_assets.yaml"


def resolve_brand_key(
    keyword: str,
    title: str = "",
    category: str = "",
    slug: str = "",
) -> str | None:
    """アイキャッチは Flux の実写にする。旧記事のブランドロゴは使わない。"""
    del keyword, title, category, slug
    return None


def pick_brand_key(keyword: str, title: str = "", category: str = "", slug: str = "") -> str | None:
    return resolve_brand_key(keyword, title, category, slug)


def _load_brands() -> dict[str, dict[str, Any]]:
    if not BRAND_ASSETS_PATH.exists():
        return {}
    data = yaml.safe_load(BRAND_ASSETS_PATH.read_text(encoding="utf-8")) or {}
    return data.get("brands", {})


def _hybrid_featured_layout() -> dict[str, float]:
    if not BRAND_ASSETS_PATH.exists():
        return {
            "panel_width_ratio": 0.36,
            "logo_max_width_ratio_of_panel": 0.78,
            "logo_max_height_ratio_of_canvas": 0.34,
        }
    data = yaml.safe_load(BRAND_ASSETS_PATH.read_text(encoding="utf-8")) or {}
    defaults = {
        "panel_width_ratio": 0.36,
        "logo_max_width_ratio_of_panel": 0.78,
        "logo_max_height_ratio_of_canvas": 0.34,
    }
    cfg = data.get("hybrid_featured", {}) or {}
    return {**defaults, **cfg}


def _hybrid_logo_bounds(width: int, height: int) -> tuple[int, int, int]:
    """左パネル幅とロゴの最大枠（幅・高さ）を返す。"""
    layout = _hybrid_featured_layout()
    panel_w = int(width * float(layout["panel_width_ratio"]))
    max_w = int(panel_w * float(layout["logo_max_width_ratio_of_panel"]))
    max_h = int(height * float(layout["logo_max_height_ratio_of_canvas"]))
    return panel_w, max_w, max_h


def _trim_transparent(logo: Image.Image) -> Image.Image:
    """透明余白を除去。"""
    logo = logo.convert("RGBA")
    bbox = logo.split()[-1].getbbox()
    return logo.crop(bbox) if bbox else logo


def _trim_uniform_border(logo: Image.Image, tolerance: int = 22) -> Image.Image:
    """角と同色の余白（favicon 等の白・ベージュ枠）を除去。"""
    logo = logo.convert("RGBA")
    w, h = logo.size
    if w < 4 or h < 4:
        return logo

    pixels = logo.load()
    ref = pixels[0, 0][:3]

    def is_border(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        if a < 16:
            return True
        return all(abs(channel - ref_channel) <= tolerance for channel, ref_channel in zip((r, g, b), ref))

    top = 0
    while top < h and all(is_border(x, top) for x in range(w)):
        top += 1
    bottom = h - 1
    while bottom >= top and all(is_border(x, bottom) for x in range(w)):
        bottom -= 1
    left = 0
    while left < w and all(is_border(left, y) for y in range(top, bottom + 1)):
        left += 1
    right = w - 1
    while right >= left and all(is_border(right, y) for y in range(top, bottom + 1)):
        right -= 1

    if left < right and top < bottom:
        return logo.crop((left, top, right + 1, bottom + 1))
    return logo


def _prepare_logo_for_hybrid(logo: Image.Image) -> Image.Image:
    """ハイブリッド左パネル用に余白を除去。"""
    logo = _trim_transparent(logo)
    logo = _trim_uniform_border(logo)
    return logo


def _fit_logo_for_hybrid_panel(logo: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """ロゴを左パネル枠に収め、ITキャリア記事と同じ見た目の大きさに揃える。"""
    logo = _prepare_logo_for_hybrid(logo.copy())
    if logo.width <= 0 or logo.height <= 0:
        return logo

    # vscode / Copilot / Cursor と同じ正方形スロット（辺長 max_h）に収める
    box = max_h
    logo.thumbnail((box, box), Image.Resampling.LANCZOS)

    long_edge = max(logo.width, logo.height)
    if long_edge < box:
        scale = box / long_edge
        new_w = min(int(round(logo.width * scale)), box)
        new_h = min(int(round(logo.height * scale)), box)
        if new_w > 0 and new_h > 0:
            logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

    return logo


def normalize_image_prompts(
    prompts: list[dict] | None,
    *,
    keyword: str,
    title: str = "",
    category: str = "",
    slug: str = "",
    species: str = "",
    max_body: int = 1,
) -> list[dict]:
    """アイキャッチは可能なら brand、本文は brand または控えめな flux。"""
    brand_key = pick_brand_key(keyword, title, category, slug)
    normalized: list[dict] = []

    for i, raw in enumerate(prompts or []):
        item = dict(raw)
        source = str(item.get("source", "")).strip().lower()
        if i == 0:
            if source not in ("brand", "flux"):
                source = "brand" if brand_key else "flux"
            # 検出できた主題ブランドは LLM 指定より優先（誤ロゴ防止）
            if brand_key:
                item["brand_key"] = brand_key
                source = "brand"
        else:
            if source not in ("brand", "flux"):
                source = "flux"
            body_brand = pick_brand_key(keyword, title, category, slug)
            if source == "brand" and body_brand:
                item["brand_key"] = body_brand
        item["source"] = source
        normalized.append(item)
        if len(normalized) >= 1 + max_body:
            break

    if not normalized:
        normalized.append(
            {
                "source": "brand" if brand_key else "flux",
                "brand_key": brand_key or "",
                "prompt": _editorial_flux_prompt(keyword, title, brand_key or "", slug),
                "alt": title or keyword,
            }
        )
    elif brand_key:
        normalized[0]["source"] = "brand"
        normalized[0]["brand_key"] = brand_key
    if normalized[0].get("source") == "flux" and not (
        normalized[0].get("prompt") or normalized[0].get("scene_prompt")
    ):
        normalized[0]["prompt"] = _editorial_flux_prompt(keyword, title, brand_key or "", slug)

    if max_body >= 1:
        who = species or title or keyword
        catch = {
            "source": "flux",
            "role": "catch",
            "scene_prompt": (
                f"One fish just landed, matching this article: {who}. "
                "A modest catch, not a trophy. Lying on wet gray tetrapod concrete "
                "at a Japanese harbor breakwater in the evening, warm low sun, harbor blurred. "
                "Wet scales, mouth slightly open. No people, no hands, no text, no packaging, no lure."
            ),
            "alt": f"{who}が釣れた状態"[:100],
            "caption": "この日の釣果です。",
            "placeholder": "[IMAGE:1]",
        }
        if len(normalized) == 1:
            normalized.append(catch)
        else:
            normalized[1] = catch
        normalized = normalized[:2]

    return normalized


BRAND_PALETTE_HINTS: dict[str, str] = {}
BRAND_FALLBACK_SCENES: dict[str, str] = {}


ILLUSTRATION_STYLE = (
    "Photorealistic quiet photo for a weekend lure-fishing blog. "
    "The tackle subject sits in the lower-left third, tack-sharp. "
    "A Japanese rocky shore or small harbor is softly blurred behind it. "
    "Camera at standing height, cool blue-gray water, warm low sun on the tackle. "
    "No text, no logos, no borders, no faces."
)


def _brand_palette_hint(brand_key: str) -> str:
    if brand_key in BRAND_PALETTE_HINTS:
        return BRAND_PALETTE_HINTS[brand_key]
    brands = _load_brands()
    accent = brands.get(brand_key, {}).get("accent_color", "#334155")
    return f"brand accent {accent}"


def _article_topic_label(keyword: str, title: str, slug: str) -> str:
    return (title or keyword or slug.replace("-", " ")).strip()


def build_article_scene_prompt(
    keyword: str = "",
    title: str = "",
    slug: str = "",
    brand_key: str = "",
) -> str:
    """週末のルアー釣りに直結した実写プロンプト。"""
    topic = _article_topic_label(keyword, title, slug)
    palette = _brand_palette_hint(brand_key)
    scene = BRAND_FALLBACK_SCENES.get(
        brand_key,
        f"quiet realistic photo of weekend shore lure fishing related to {topic}, natural light, practical tackle",
    )
    return (
        f"{ILLUSTRATION_STYLE} "
        f"Article topic: {topic}. "
        f"Scene: {scene} "
        f"Color palette: {palette}. "
        "No readable text, no watermarks, no official logos in the scene."
    )


def _editorial_flux_prompt(
    keyword: str = "",
    title: str = "",
    brand_key: str = "",
    slug: str = "",
) -> str:
    return build_article_scene_prompt(keyword, title, slug, brand_key)


def _parse_size(size: str) -> tuple[int, int]:
    if "x" in size.lower():
        w, h = size.lower().split("x", 1)
        return int(w), int(h)
    return 1024, 1024


def _hex_color(value: str, fallback: str = "#f8fafc") -> str:
    value = (value or fallback).strip()
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


def _fetch_logo(url: str) -> Image.Image:
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "GrowfolioAutomation/1.0"},
    )
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" in content_type:
        raise ValueError(f"URL returned HTML instead of an image: {url}")
    return Image.open(BytesIO(response.content)).convert("RGBA")


def _load_logo(brand_key: str, brand: dict[str, Any]) -> Image.Image:
    for suffix in (".png", ".webp", ".jpg", ".jpeg", ".ico", ".svg"):
        local = ASSETS_DIR / f"{brand_key}{suffix}"
        if local.is_file() and local.stat().st_size > 512:
            img = Image.open(local)
            if suffix == ".svg":
                # cairosvg 等は未導入のため PNG 配置を推奨
                raise FileNotFoundError(
                    f"SVG logo requires PNG export: assets/logos/{brand_key}.png"
                )
            return img.convert("RGBA")
    url = (brand.get("logo_url") or "").strip()
    if url:
        img = _fetch_logo(url)
        if img.width < 32 and img.height < 32:
            raise ValueError(f"Logo too small from URL for {brand_key}")
        return img
    raise FileNotFoundError(
        f"Logo not found for brand: {brand_key}. Place assets/logos/{brand_key}.png"
    )


def compose_hybrid_brand_image(
    brand_key: str,
    *,
    keyword: str = "",
    title: str = "",
    slug: str = "",
    scene_prompt: str = "",
    size: str = "1792x1024",
) -> bytes:
    """記事テーマの近未来イラスト＋公式ロゴのハイブリッドアイキャッチ。"""
    from images.flux_client import generate_image_bytes

    brands = _load_brands()
    brand = brands.get(brand_key)
    if not brand:
        raise KeyError(f"Unknown brand_key: {brand_key}")

    width, height = _parse_size(size)
    bg = _hex_color(brand.get("bg_color", "#f8fafc"))
    accent = _hex_color(brand.get("accent_color", "#334155"), "#334155")

    base_prompt = build_article_scene_prompt(keyword, title, slug, brand_key)
    custom = (scene_prompt or "").strip()
    if custom and len(custom) > 40 and custom.lower() not in base_prompt.lower():
        prompt = f"{base_prompt} Extra detail: {custom}."
    else:
        prompt = base_prompt
    photo = Image.open(
        BytesIO(generate_image_bytes(prompt, size=size, role="featured"))
    ).convert("RGB")
    photo = photo.resize((width, height), Image.Resampling.LANCZOS)
    canvas = photo.copy()
    draw = ImageDraw.Draw(canvas)

    panel_w, max_w, max_h = _hybrid_logo_bounds(width, height)
    draw.rectangle([0, 0, panel_w, height], fill=bg)

    logo = _fit_logo_for_hybrid_panel(_load_logo(brand_key, brand), max_w, max_h)
    lx = (panel_w - logo.width) // 2
    ly = (height - logo.height) // 2 - height // 40
    canvas.paste(logo, (lx, ly), logo)

    divider = max(2, width // 640)
    draw.rectangle([panel_w, 0, panel_w + divider, height], fill=accent)

    bar_h = max(6, height // 120)
    draw.rectangle([0, height - bar_h, width, height], fill=accent)

    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def compose_brand_image(brand_key: str, size: str = "1792x1024") -> bytes:
    """公式ロゴのみのシンプルなサムネイル（本文画像向け）。"""
    brands = _load_brands()
    brand = brands.get(brand_key)
    if not brand:
        raise KeyError(f"Unknown brand_key: {brand_key}")

    width, height = _parse_size(size)
    bg = _hex_color(brand.get("bg_color", "#f8fafc"))
    accent = _hex_color(brand.get("accent_color", "#334155"), "#334155")

    canvas = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(canvas)
    bar_h = max(6, height // 120)
    draw.rectangle([0, height - bar_h, width, height], fill=accent)

    logo = _load_logo(brand_key, brand)
    max_w = int(width * 0.42)
    max_h = int(height * 0.38)
    logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = (width - logo.width) // 2
    y = (height - logo.height) // 2 - bar_h // 2
    canvas.paste(logo, (x, y), logo)

    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def brand_caption(brand_key: str, *, hybrid: bool = False) -> str:
    brands = _load_brands()
    name = brands.get(brand_key, {}).get("name") or brand_key
    if hybrid:
        return f"※{name} 公式ロゴ＋記事テーマの参考イメージ"
    return f"※{name} 公式ロゴ"
