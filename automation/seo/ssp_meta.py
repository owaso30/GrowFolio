"""SEO SIMPLE PACK 用メタ（REST 書き込み）。"""
from __future__ import annotations

from typing import Any

# プラグイン本体 class/metabox.php の POST_META_KEYS と一致（先頭 _ なし）
SSP_META_TITLE = "ssp_meta_title"
SSP_META_DESCRIPTION = "ssp_meta_description"


def build_featured_alt(article: dict[str, Any], keyword: str) -> str:
    """アイキャッチ用 alt（日本語・記事内容に沿う）。"""
    prompts = article.get("image_prompts") or []
    if prompts and str(prompts[0].get("alt", "")).strip():
        alt = str(prompts[0]["alt"]).strip()
    else:
        alt = str(article.get("title") or keyword).strip()
    return alt[:100] if alt else keyword[:100]


def build_ssp_meta(article: dict[str, Any]) -> dict[str, str]:
    """投稿ごとの SEO SIMPLE PACK タイトル・ディスクリプション。"""
    title = str(article.get("title", "")).strip()
    description = str(article.get("meta_description", "")).strip()
    return {
        SSP_META_TITLE: title,
        SSP_META_DESCRIPTION: description,
    }


def ensure_featured_alt_in_prompts(article: dict[str, Any], keyword: str) -> None:
    """image_prompts[0].alt が空なら記事タイトルベースで補完。"""
    alt = build_featured_alt(article, keyword)
    prompts = list(article.get("image_prompts") or [])
    if not prompts:
        prompts.append({"prompt": "", "alt": alt})
    else:
        if not str(prompts[0].get("alt", "")).strip():
            prompts[0] = {**prompts[0], "alt": alt}
    article["image_prompts"] = prompts
