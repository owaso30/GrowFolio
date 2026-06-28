"""公式ロゴを使ったアイキャッチ・本文画像（AI感を抑えた編集風レイアウト）。"""
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

BRAND_PATTERNS: list[tuple[str, str]] = [
    ("bitradex", "bitradex"),
    ("github copilot", "github_copilot"),
    ("microsoft 365 copilot", "microsoft_365"),
    ("copilot", "github_copilot"),
    ("cursor", "cursor"),
    ("visual studio code", "vscode"),
    ("vscode", "vscode"),
    ("claude code", "claude"),
    ("claude", "claude"),
]


def _load_brands() -> dict[str, dict[str, Any]]:
    if not BRAND_ASSETS_PATH.exists():
        return {}
    data = yaml.safe_load(BRAND_ASSETS_PATH.read_text(encoding="utf-8")) or {}
    return data.get("brands", {})


def pick_brand_key(keyword: str, title: str = "", category: str = "") -> str | None:
    text = f"{keyword} {title} {category}".lower()
    for pattern, key in BRAND_PATTERNS:
        if pattern in text:
            return key
    return None


def normalize_image_prompts(
    prompts: list[dict] | None,
    *,
    keyword: str,
    title: str = "",
    category: str = "",
    max_body: int = 1,
) -> list[dict]:
    """アイキャッチは可能なら brand、本文は brand または控えめな flux。"""
    brand_key = pick_brand_key(keyword, title, category)
    normalized: list[dict] = []

    for i, raw in enumerate(prompts or []):
        item = dict(raw)
        source = str(item.get("source", "")).strip().lower()
        if i == 0:
            if source not in ("brand", "flux"):
                source = "brand" if brand_key else "flux"
            if source == "brand" and not item.get("brand_key") and brand_key:
                item["brand_key"] = brand_key
        else:
            if source not in ("brand", "flux"):
                source = "flux"
        item["source"] = source
        normalized.append(item)
        if len(normalized) >= 1 + max_body:
            break

    if not normalized:
        normalized.append(
            {
                "source": "brand" if brand_key else "flux",
                "brand_key": brand_key or "",
                "prompt": _editorial_flux_prompt(keyword, title),
                "alt": title or keyword,
            }
        )
    elif normalized[0].get("source") == "brand" and not normalized[0].get("brand_key") and brand_key:
        normalized[0]["brand_key"] = brand_key
    if normalized[0].get("source") == "flux" and not normalized[0].get("prompt"):
        normalized[0]["prompt"] = _editorial_flux_prompt(keyword, title)

    return normalized


def _editorial_flux_prompt(keyword: str, title: str = "") -> str:
    topic = title or keyword
    return (
        f"Minimal editorial blog header photo related to {topic}. "
        "Clean desk, neutral background, soft natural light, subtle tech props. "
        "No logo, no text, no UI screenshot, no 3D render, no neon glow, no AI art style."
    )


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
    return Image.open(BytesIO(response.content)).convert("RGBA")


def _load_logo(brand_key: str, brand: dict[str, Any]) -> Image.Image:
    local = ASSETS_DIR / f"{brand_key}.png"
    if local.exists():
        return Image.open(local).convert("RGBA")
    url = (brand.get("logo_url") or "").strip()
    if url:
        return _fetch_logo(url)
    raise FileNotFoundError(f"Logo not found for brand: {brand_key}")


def compose_brand_image(brand_key: str, size: str = "1792x1024") -> bytes:
    """公式ロゴを中央配置したシンプルなサムネイル（AI生成風を避ける）。"""
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


def brand_caption(brand_key: str) -> str:
    brands = _load_brands()
    name = brands.get(brand_key, {}).get("name") or brand_key
    return f"※{name} 公式ロゴ"
