"""キーワードの安全性・編集方針フィルタ。"""
from __future__ import annotations

import re

from config_loader import load_yaml

_KATAKANA = re.compile(r"^[ァ-ヶー]{2,10}$")
_HIRAGANA = re.compile(r"^[ぁ-ん]{2,8}$")
_LATIN_BRAND = re.compile(r"^[a-zA-Z0-9]{2,12}$")


def _safety_config() -> dict:
    return load_yaml("content_policy.yaml").get("keyword_safety", {})


def _words(keyword: str) -> list[str]:
    return [w for w in re.split(r"[\s　]+", keyword.strip()) if w]


def _contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(t.lower() in lower for t in terms)


def _trusted_entities() -> list[str]:
    cfg = _safety_config()
    trusted = list(cfg.get("trusted_entities", []))
    trusted.extend(load_yaml("content_policy.yaml").get("auto_publish", {}).get("topic_keywords", []))
    return trusted


def _is_trusted_token(token: str) -> bool:
    t = token.lower()
    return any(tr.lower() in t or t in tr.lower() for tr in _trusted_entities())


def _person_like_token(token: str) -> bool:
    if _is_trusted_token(token):
        return False
    if _KATAKANA.match(token) or _HIRAGANA.match(token):
        return True
    if _LATIN_BRAND.match(token) and not _is_trusted_token(token):
        # 短い英字ブランド（取引所名等）は trusted 以外は個人・チャンネル指名の可能性
        return True
    return False


def is_person_target_keyword(keyword: str) -> bool:
    """個人・インフルエンサー名指しの評判・批判系 KW。"""
    cfg = _safety_config()
    kw = (keyword or "").strip()
    if not kw:
        return False

    blocked_names = cfg.get("blocked_names", [])
    if _contains_any(kw, blocked_names):
        return True

    reputation_mods = cfg.get("reputation_modifiers", [])
    if not _contains_any(kw, reputation_mods):
        return False

    for word in _words(kw):
        if _person_like_token(word):
            return True

    return False


def is_reputation_framing_keyword(keyword: str) -> bool:
    """評判・口コミ・怪しい等の口コミ系フレーミング（自動投稿では原則除外）。"""
    cfg = _safety_config()
    if cfg.get("block_all_reputation_keywords", True):
        return _contains_any(keyword, cfg.get("reputation_modifiers", []))
    return is_person_target_keyword(keyword)


def is_procedure_keyword(keyword: str) -> bool:
    """手順・やり方・設定系（画像依存が高い）KW。"""
    cfg = _safety_config()
    return _contains_any(keyword, cfg.get("procedure_modifiers", []))


def is_trend_focus_keyword(keyword: str) -> bool:
    """ニュース・制度・規制・動向など話題性のある KW。"""
    cfg = _safety_config()
    mods = cfg.get("trend_focus_modifiers", [])
    if _contains_any(keyword, mods):
        return True
    return bool(re.search(r"20\d{2}", keyword))


def is_news_focus_keyword(keyword: str) -> bool:
    """後方互換: トレンド寄り KW 判定（手順系は含めない）。"""
    return is_trend_focus_keyword(keyword)


def has_specific_entity(keyword: str) -> bool:
    """特定サービス・技術・制度名を含むか。"""
    cfg = _safety_config()
    entities = cfg.get("specific_entities", []) + cfg.get("trusted_entities", [])
    if _contains_any(keyword, entities):
        return True
    for word in _words(keyword):
        if _LATIN_BRAND.match(word) and len(word) >= 3:
            return True
    return bool(re.search(r"20\d{2}", keyword))


def is_generic_keyword(keyword: str) -> bool:
    """特定感のない汎用ロングテール（学習おすすめ等）。"""
    if has_specific_entity(keyword):
        return False
    cfg = _safety_config()
    if not _contains_any(keyword, cfg.get("generic_modifiers", [])):
        return False
    heads = load_yaml("content_policy.yaml").get("blue_ocean", {}).get("head_terms", [])
    return _contains_any(keyword, heads) or len(_words(keyword)) <= 3


def is_desired_for_auto(keyword: str) -> bool:
    """キューに載せたい KW か（手順系・汎用語を除外）。"""
    kw = (keyword or "").strip()
    if not kw:
        return False
    if is_procedure_keyword(kw):
        return False
    if is_generic_keyword(kw):
        return False
    return True


def is_blocked_topic_keyword(keyword: str) -> bool:
    cfg = _safety_config()
    if _contains_any(keyword, cfg.get("blocked_topics", [])):
        return True
    if _contains_any(keyword, cfg.get("low_quality_modifiers", [])):
        return True
    return False


def is_safe_for_auto(keyword: str) -> bool:
    kw = (keyword or "").strip()
    if not kw:
        return False
    if is_blocked_topic_keyword(kw):
        return False
    if is_person_target_keyword(kw):
        return False
    if is_reputation_framing_keyword(kw):
        return False
    return True
