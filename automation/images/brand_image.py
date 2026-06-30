"""公式ロゴ＋記事テーマ写真のハイブリッド画像（アイキャッチ・本文）。"""
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

BRAND_PATTERNS: list[tuple[str, str, int]] = [
    # pattern, brand_key, weight
    ("microsoft 365 copilot", "microsoft_365", 15),
    ("microsoft copilot", "microsoft_365", 12),
    ("github copilot", "github_copilot", 14),
    ("github-copilot", "github_copilot", 14),
    ("visual studio code", "vscode", 12),
    ("vs code", "vscode", 12),
    ("vs-code", "vscode", 12),
    ("vscode", "vscode", 9),
    ("bitradex", "bitradex", 15),
    ("cursor", "cursor", 12),
    ("claude code", "claude", 14),
    ("anthropic", "claude", 10),
    ("claude", "claude", 9),
]

SLUG_PREFIX_BOOSTS: list[tuple[str, str, int]] = [
    ("vscode-", "vscode", 10),
    ("cursor-", "cursor", 10),
    ("github-copilot-", "github_copilot", 10),
    ("bitradex-", "bitradex", 10),
    ("claude-", "claude", 10),
]

COMPARISON_MARKERS = ("の違い", "比較", " vs ", "対決", "どっち", "どちら")


def _normalize_match_text(*parts: str) -> str:
    combined = " ".join(p for p in parts if p).lower()
    return combined.replace("-", " ").replace("_", " ")


def resolve_brand_key(
    keyword: str,
    title: str = "",
    category: str = "",
    slug: str = "",
) -> str | None:
    """記事の主題に最も関連する brand_key をスコアリングで決定。"""
    slug_l = (slug or keyword).lower()
    text = _normalize_match_text(keyword, title, category, slug_l)
    scores: dict[str, int] = {}

    for pattern, key, weight in BRAND_PATTERNS:
        norm_pattern = pattern.replace("-", " ")
        if norm_pattern in text or pattern in slug_l:
            scores[key] = scores.get(key, 0) + weight

    for prefix, key, boost in SLUG_PREFIX_BOOSTS:
        if slug_l.startswith(prefix):
            scores[key] = scores.get(key, 0) + boost

    # 「copilot」単体: VS Code 文脈なら vscode を優先、GitHub 文脈なら github_copilot
    if "copilot" in text or "copilot" in slug_l.replace("-", " "):
        if scores.get("vscode", 0) > 0 or slug_l.startswith("vscode"):
            scores["vscode"] = scores.get("vscode", 0) + 6
        if "github" in text or "github" in slug_l:
            scores["github_copilot"] = scores.get("github_copilot", 0) + 5
        elif scores.get("github_copilot", 0) == 0:
            scores["github_copilot"] = scores.get("github_copilot", 0) + 3

    # 比較記事: タイトル先頭のブランドを優先（CursorとVSCodeの違い → cursor）
    title_l = (title or keyword).lower()
    for marker in COMPARISON_MARKERS:
        if marker in title_l:
            head = title_l.split(marker, 1)[0]
            for pattern, key, weight in BRAND_PATTERNS:
                norm_pattern = pattern.replace("-", " ")
                if norm_pattern in _normalize_match_text(head):
                    scores[key] = scores.get(key, 0) + weight
            break

    # Copilot 料金・プラン・機能比較は GitHub Copilot 製品が主題
    product_focus = ("プラン", "料金", "機能比較", "plan", "pricing", "free", "pro", "business")
    if any(token in text for token in product_focus) and (
        scores.get("github_copilot", 0) > 0 or "copilot" in text
    ):
        scores["github_copilot"] = scores.get("github_copilot", 0) + 8

    if not scores:
        return None
    return max(scores, key=scores.get)


def pick_brand_key(keyword: str, title: str = "", category: str = "", slug: str = "") -> str | None:
    return resolve_brand_key(keyword, title, category, slug)


def _load_brands() -> dict[str, dict[str, Any]]:
    if not BRAND_ASSETS_PATH.exists():
        return {}
    data = yaml.safe_load(BRAND_ASSETS_PATH.read_text(encoding="utf-8")) or {}
    return data.get("brands", {})


def normalize_image_prompts(
    prompts: list[dict] | None,
    *,
    keyword: str,
    title: str = "",
    category: str = "",
    slug: str = "",
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
            if source == "brand" and brand_key:
                item["brand_key"] = brand_key
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
    elif normalized[0].get("source") == "brand" and brand_key:
        normalized[0]["brand_key"] = brand_key
    if normalized[0].get("source") == "flux" and not normalized[0].get("prompt"):
        normalized[0]["prompt"] = _editorial_flux_prompt(keyword, title, brand_key or "", slug)

    return normalized


BRAND_PALETTE_HINTS: dict[str, str] = {
    "vscode": "Visual Studio Code blue #007ACC, dark editor chrome #1E1E1E, soft cyan highlights",
    "github_copilot": "GitHub dark gray #24292f, Copilot purple-blue AI accents, clean developer UI tones",
    "cursor": "Cursor dark charcoal #0f172a, subtle silver UI chrome, focused minimal palette",
    "claude": "warm terracotta #c96442, cream paper tones, calm research palette",
    "microsoft_365": "Microsoft blue #0078d4, office productivity neutrals",
    "bitradex": "deep finance blue #1d4ed8, calm trust-building blues and soft whites",
}

BRAND_FALLBACK_SCENES: dict[str, str] = {
    "vscode": (
        "sleek code editor window floating in space with syntax-colored line blocks, "
        "file tree sidebar, developer-focused near-future UI illustration"
    ),
    "github_copilot": (
        "AI pair-programming scene: code panel with ghost-text suggestion blocks appearing inline, "
        "subtle sparkle motif, developer workflow illustration"
    ),
    "cursor": (
        "AI-native code editor with inline edit diff highlights and command palette overlay, "
        "fast iteration workflow, polished dark UI illustration"
    ),
    "claude": (
        "elegant chat-and-code hybrid workspace with document panel and reasoning thread, "
        "warm minimal interface illustration"
    ),
    "microsoft_365": (
        "productivity suite hub with document, spreadsheet and chat tiles connected by soft lines, "
        "enterprise workflow illustration"
    ),
    "bitradex": (
        "crypto portfolio dashboard with AI strategy graph and calm upward trend line, "
        "fintech trust aesthetic, clean data visualization panels"
    ),
}

# (slug/title キーワード群, 記事テーマ直結のイラスト内容)
ARTICLE_SCENE_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("plan", "pricing", "プラン", "料金", "機能比較", "free tier", "business", "enterprise"),
        "GitHub Copilot subscription plan comparison: three vertical plan cards "
        "(Free, Pro, Business) with feature rows and check icons, infographic layout, "
        "clear tier differences at a glance",
    ),
    (
        ("extension", "拡張", "plugin", "プラグイン"),
        "marketplace grid of extension tiles plugging into a code editor sidebar, "
        "modular add-on ecosystem illustration",
    ),
    (
        ("update", "release", "version", "アップデート", "最新", "バージョン", "1116"),
        "software version release: editor window with 'new' badge and changelog panel, "
        "fresh feature highlight glow on updated UI elements",
    ),
    (
        ("tax", "税金", "確定申告"),
        "tax filing workflow: calculator, annual report forms and crypto profit summary chart, "
        "organized fiscal dashboard illustration",
    ),
    (
        ("affiliate", "紹介", "アフィリエイト", "referral", "招待"),
        "referral network diagram: user nodes connected by reward links to a central platform hub, "
        "affiliate commission flow infographic",
    ),
    (
        ("risk", "危険", "リスク", "怪しい"),
        "risk assessment dashboard with warning meter, shield icon and balanced pros-cons panels, "
        "cautious fintech evaluation mood",
    ),
    (
        ("withdraw", "出金", "kyc", "入金", "始め方", "start", "guide", "ガイド"),
        "step-by-step onboarding flow: account setup arrows through wallet, verification and deposit screens, "
        "clean fintech tutorial illustration",
    ),
    (
        ("ai plan", "ai運用", "運用プラン", "daily", "90d", "180d"),
        "AI trading plan selector with timeline cards (Daily, 30D, 90D, 180D), "
        "return curve previews per plan, investment strategy picker UI",
    ),
    (
        ("review", "レビュー", "実残高", "運用"),
        "portfolio performance dashboard with balance display and AI strategy status panel, "
        "transparent results reporting illustration",
    ),
]

ILLUSTRATION_STYLE = (
    "Clean near-futuristic digital illustration for a premium technology blog hero image. "
    "Polished flat-vector with soft depth, crisp shapes, elegant gradients, controlled lighting, "
    "high-end product-design aesthetic. Clearly depicts the article topic. "
    "Not photorealistic, not stock photo, not painterly AI slop."
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
    """記事テーマに直結した近未来イラスト用プロンプト。"""
    haystack = _normalize_match_text(keyword, title, slug)
    palette = _brand_palette_hint(brand_key)
    topic = _article_topic_label(keyword, title, slug)

    def _format(scene: str) -> str:
        return (
            f"{ILLUSTRATION_STYLE} "
            f"Article topic: {topic}. "
            f"Scene: {scene} "
            f"Color palette: {palette}. "
            "No readable text, no watermarks, no official logos in the scene."
        )

    comparison_markers = ("違い", "difference", " vs ", "versus", "どっち", "比較")
    if (
        any(m in haystack for m in comparison_markers)
        and "cursor" in haystack
        and "vscode" in haystack
    ):
        return _format(
            "split-screen comparison: Cursor AI editor on the left versus VS Code on the right, "
            "contrasting UI chrome and AI features, versus layout with subtle divider"
        )

    if any(
        token in haystack
        for token in ("copilot chat", "copilot-chat", "chat builtin", "標準搭載", "builtin")
    ):
        return _format(
            "VS Code editor window with Copilot Chat panel built into the sidebar, "
            "chat bubbles beside code lines, built-in AI assistant clearly visible, "
            "version update launch mood"
        )

    for tokens, scene in ARTICLE_SCENE_RULES:
        if any(token in haystack for token in tokens):
            return _format(scene)

    fallback = BRAND_FALLBACK_SCENES.get(
        brand_key,
        f"modern technology concept illustration directly about {topic}, clean UI shapes and relevant icons",
    )
    return _format(fallback)


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
    return Image.open(BytesIO(response.content)).convert("RGBA")


def _load_logo(brand_key: str, brand: dict[str, Any]) -> Image.Image:
    local = ASSETS_DIR / f"{brand_key}.png"
    if local.is_file() and local.stat().st_size > 1024:
        return Image.open(local).convert("RGBA")
    url = (brand.get("logo_url") or "").strip()
    if url:
        return _fetch_logo(url)
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

    panel_w = int(width * 0.36)
    draw.rectangle([0, 0, panel_w, height], fill=bg)

    logo = _load_logo(brand_key, brand)
    max_w = int(panel_w * 0.78)
    max_h = int(height * 0.34)
    logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
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
