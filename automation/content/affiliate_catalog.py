"""アフィリエイト案件カタログ（LLM用・URL解決）。"""
from __future__ import annotations

import os
import re
from typing import Any

import yaml

from config_loader import AUTOMATION_ROOT, load_env

A8_PROGRAMS_PATH = AUTOMATION_ROOT / "config" / "a8_programs.yaml"
AFFILIATES_PATH = AUTOMATION_ROOT / "config" / "affiliates.yaml"


def _load_affiliates_cfg() -> dict:
    return yaml.safe_load(AFFILIATES_PATH.read_text(encoding="utf-8")) or {}


def _load_a8_raw() -> list[dict]:
    if not A8_PROGRAMS_PATH.exists():
        return []
    data = yaml.safe_load(A8_PROGRAMS_PATH.read_text(encoding="utf-8")) or {}
    programs = data.get("programs", [])
    if isinstance(programs, dict):
        return [_legacy_entry(k, v) for k, v in programs.items()]
    return [p for p in programs if isinstance(p, dict)]


def _legacy_entry(prog_id: str, prog: dict) -> dict:
    """旧形式との後方互換。"""
    return {
        "_legacy_id": prog_id,
        "url": prog.get("url", ""),
        "keywords": _parse_keywords(prog.get("keywords") or prog.get("topics", [])),
    }


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u3040-\u30ff\u4e00-\u9fff]+", "_", text.lower())
    return s.strip("_")[:24] or "item"


def _parse_keywords(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [str(k).strip() for k in raw if str(k).strip()]


def _auto_name(keywords: list[str]) -> str:
    return " / ".join(keywords[:3]) if keywords else "A8案件"


def _auto_id(entry: dict, index: int, used: set[str]) -> str:
    if entry.get("_legacy_id"):
        return entry["_legacy_id"]
    base = _slug(entry.get("keywords", ["item"])[0]) if entry.get("keywords") else f"item{index + 1}"
    prog_id = f"a8_{base}"
    if prog_id in used:
        prog_id = f"a8_{base}_{index + 1}"
    return prog_id


def _normalize_a8_entry(entry: dict, index: int, used_ids: set[str]) -> tuple[str, dict] | None:
    url = (entry.get("url") or "").strip()
    keywords = _parse_keywords(entry.get("keywords"))[:3]
    if not keywords:
        return None

    prog_id = _auto_id({"keywords": keywords, **entry}, index, used_ids)
    used_ids.add(prog_id)
    name = _auto_name(keywords)

    return prog_id, {
        "url": url,
        "keywords": keywords,
        "topics": keywords,
        "name": name,
        "default_anchor": "詳細はこちら",
        "program_type": "a8",
    }


def get_a8_programs() -> dict[str, dict]:
    used: set[str] = set()
    result: dict[str, dict] = {}
    for i, raw in enumerate(_load_a8_raw()):
        normalized = _normalize_a8_entry(raw, i, used)
        if normalized:
            prog_id, prog = normalized
            result[prog_id] = prog
    return result


def get_standard_programs() -> dict[str, dict]:
    return _load_affiliates_cfg().get("programs", {})


def is_a8_program(prog_id: str) -> bool:
    return prog_id.startswith("a8_") and prog_id in get_a8_programs()


def resolve_program(prog_id: str) -> dict | None:
    if is_a8_program(prog_id):
        prog = get_a8_programs()[prog_id]
        affiliates = _load_affiliates_cfg()
        merged = dict(prog)
        merged["cta_template"] = affiliates.get("a8_cta_template", "")
        merged["style_key"] = "a8"
        merged.setdefault("default_heading", f"{merged.get('name', '関連サービス')}がおすすめ")
        merged.setdefault("default_teaser", "記事のテーマに関連するサービスです。詳細は公式サイトでご確認ください。")
        return merged

    prog = get_standard_programs().get(prog_id)
    if prog:
        return {**prog, "program_type": "standard"}
    return None


def all_program_ids() -> set[str]:
    ids = set(get_standard_programs())
    ids.update(get_a8_programs())
    return ids


def program_configured(prog_id: str) -> bool:
    prog = resolve_program(prog_id)
    if not prog:
        return False

    if prog.get("program_type") == "a8":
        return bool((prog.get("url") or "").strip())

    load_env()
    if prog.get("url_template"):
        tag = os.environ.get(prog.get("tag_env", ""), "")
        return bool(tag)
    url_env = prog.get("url_env", "")
    return bool(os.environ.get(url_env, prog.get("default_url", "")))


def list_all_programs(configured_only: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for prog_id, prog in get_standard_programs().items():
        if configured_only and not program_configured(prog_id):
            continue
        result.append(_entry(prog_id, prog))

    for prog_id, prog in get_a8_programs().items():
        if configured_only and not program_configured(prog_id):
            continue
        result.append(_entry(prog_id, prog, is_a8=True))

    return result


def _entry(prog_id: str, prog: dict, is_a8: bool = False) -> dict[str, Any]:
    topics = prog.get("topics") or prog.get("keywords") or []
    return {
        "id": prog_id,
        "name": prog.get("name", prog_id),
        "description": prog.get("description", ""),
        "topics": topics,
        "default_anchor": prog.get("default_anchor", "詳細はこちら"),
        "needs_query": prog_id == "amazon_search",
        "is_a8": is_a8,
        "configured": program_configured(prog_id),
    }


def format_catalog_for_prompt() -> str:
    items = list_all_programs(configured_only=False)
    if not items:
        return "（affiliates.yaml / a8_programs.yaml に案件が未登録）"

    lines = []
    standard = [i for i in items if not i["is_a8"]]
    a8_items = [i for i in items if i["is_a8"]]

    if standard:
        lines.append("【BitradeX / Amazon】")
        for item in standard:
            lines.append(_format_line(item))

    if a8_items:
        lines.append("")
        lines.append("【A8.net — 記事に最も合う id を選び、anchor（リンク文言）も記事に合わせて生成】")
        for item in a8_items:
            lines.append(_format_a8_line(item))

    return "\n".join(lines)


def _format_line(item: dict[str, Any]) -> str:
    status = "URL設定済" if item["configured"] else "URL未設定（選んでもCTAはスキップ）"
    topics = "、".join(item["topics"][:6])
    note = " ※query も指定" if item["needs_query"] else ""
    return (
        f"- id: `{item['id']}` / {item['name']} / {item['description']} "
        f"/ 向き: {topics}{note} / [{status}]"
    )


def _format_a8_line(item: dict[str, Any]) -> str:
    status = "URL設定済" if item["configured"] else "url未入力（スキップ）"
    kws = "、".join(item["topics"][:3])
    return f"- id: `{item['id']}` / keywords: {kws} / [{status}]"


def pick_program_by_keyword(keyword: str, a8_only: bool = False) -> str | None:
    candidates = list_all_programs(configured_only=True)
    if a8_only:
        candidates = [c for c in candidates if c["is_a8"]]
    if not candidates:
        return None

    kw = keyword.lower()
    best_id = None
    best_score = -1
    for item in candidates:
        score = 0
        for topic in item.get("topics", []):
            t = topic.lower()
            if t in kw or kw in t:
                score += 3
            elif any(part in t for part in kw.split() if len(part) > 1):
                score += 1
        if score > best_score:
            best_score = score
            best_id = item["id"]
    return best_id or candidates[0]["id"]
