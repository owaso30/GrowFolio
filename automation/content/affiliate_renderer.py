"""一般・BitradeX・A8 アフィリエイトCTAのHTML生成と記事内配置。"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, NavigableString, Tag

import yaml

from config_loader import AUTOMATION_ROOT, load_env
from content.affiliate_catalog import (
    all_program_ids,
    is_a8_program,
    list_all_programs,
    pick_program_by_keyword,
    program_configured,
    resolve_program,
)

VALID_SLOTS = ("intro", "mid", "end")
SLOT_LIMITS = {"intro": 1, "mid": 2, "end": 1}


def _affiliates_cfg() -> dict:
    path = AUTOMATION_ROOT / "config" / "affiliates.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _build_url(program: dict, placement: dict) -> str:
    if program.get("program_type") == "a8":
        return (program.get("url") or "").strip()
    if program.get("url_template"):
        tag = os.environ.get(program.get("tag_env", ""), "")
        query = quote(placement.get("query", placement.get("anchor", "")))
        return program["url_template"].format(query=query, tag=tag, anchor=quote(placement.get("anchor", "")))
    url_env = program.get("url_env", "")
    return os.environ.get(url_env, program.get("default_url", ""))


def _style_for_program(prog_id: str, program: dict) -> dict[str, str]:
    cfg = _affiliates_cfg().get("affiliate_banners", {})
    styles = cfg.get("styles", {})
    key = program.get("style_key", "a8" if is_a8_program(prog_id) else "default")
    return styles.get(key, styles.get("default", {}))


def _banner_shell(
    *,
    slot: str,
    heading: str,
    teaser: str,
    cta_html: str,
    extra_html: str,
    prog_id: str,
    program: dict,
) -> str:
    cfg = _affiliates_cfg().get("affiliate_banners", {})
    labels = cfg.get("slot_labels", {})
    note = cfg.get("disclaimer_note", "")
    style = _style_for_program(prog_id, program)
    label = labels.get(slot, "PR")
    badge = style.get("badge", program.get("name", "PR"))
    border = style.get("border", "#475569")
    accent = style.get("accent", "#334155")
    bg = style.get("bg", "#f8fafc")

    btn_style = (
        f"display:inline-block;margin-top:.25em;padding:.85em 1.4em;"
        f"background:{accent};color:#fff !important;font-weight:700;text-decoration:none;"
        f"border-radius:8px;line-height:1.4;"
    )
    cta_html = cta_html.replace('class="growfolio-affiliate__btn"', f'style="{btn_style}"', 1)

    return (
        f'<aside class="growfolio-affiliate growfolio-affiliate--{slot}" role="complementary" '
        f'style="margin:2.2em 0;padding:1.35em 1.5em;border:2px solid {border};'
        f'border-radius:14px;background:{bg};box-shadow:0 4px 14px rgba(15,23,42,.06);">'
        f'<p style="margin:0 0 .45em;font-size:.82em;font-weight:700;color:{accent};letter-spacing:.04em;">'
        f'{label}</p>'
        f'<p style="display:inline-block;margin:0 0 .65em;padding:.15em .55em;font-size:.72em;'
        f'font-weight:700;color:{accent};border:1px solid {border};border-radius:999px;">{badge}</p>'
        f'<h3 style="margin:0 0 .65em;font-size:1.12em;line-height:1.55;color:#0f172a;">{heading}</h3>'
        f'<p style="margin:0 0 1em;font-size:.95em;line-height:1.75;color:#334155;">{teaser}</p>'
        f'{cta_html}'
        f'{extra_html or ""}'
        f'<p style="margin:1em 0 0;font-size:.78em;line-height:1.6;color:#64748b;">{note}</p>'
        f"</aside>"
    )


def _render_one(prog_id: str, placement: dict, guide_url: str) -> str | None:
    if prog_id not in all_program_ids():
        return None

    program = resolve_program(prog_id)
    if not program:
        return None

    url = _build_url(program, placement)
    if prog_id == "amazon_search" and (not url or "tag=&" in url or url.endswith("tag=")):
        return None
    if prog_id == "bitradex" and not url:
        return None
    if is_a8_program(prog_id) and not url:
        return None

    slot = placement.get("slot", "mid")
    if slot not in VALID_SLOTS:
        slot = "mid"

    cfg = _affiliates_cfg().get("affiliate_banners", {})
    default_headings = cfg.get("slot_default_headings", {})
    anchor = placement.get("anchor") or program.get("default_anchor") or program.get("name", "詳細はこちら")
    heading = placement.get("heading") or program.get("default_heading") or default_headings.get(slot, anchor)
    teaser = placement.get("teaser") or program.get("default_teaser") or program.get("description", "")

    template = program.get("cta_template") or _affiliates_cfg().get("a8_cta_template", "")
    if not template:
        return None

    cta_html = template.format(url=url, anchor=anchor, guide_url=guide_url)
    extra = program.get("extra_html", "")
    if extra:
        extra = extra.format(url=url, anchor=anchor, guide_url=guide_url)

    return _banner_shell(
        slot=slot,
        heading=heading,
        teaser=teaser,
        cta_html=cta_html,
        extra_html=extra,
        prog_id=prog_id,
        program=program,
    )


def _auto_slot(index: int) -> str:
    order = ["intro", "mid", "mid", "end"]
    return order[min(index, len(order) - 1)]


def normalize_affiliate_placements(
    placements: list[dict] | None,
    keyword: str,
) -> list[dict]:
    """スロット正規化・不足分の自動補完（intro 1 / mid 1-2 / end 1）。"""
    load_env()
    valid = all_program_ids()
    configured = [p for p in list_all_programs(configured_only=True)]
    if not configured:
        return []

    normalized: list[dict] = []
    seen_programs: set[str] = set()

    for raw in placements or []:
        prog_id = raw.get("program", "")
        if prog_id == "a8":
            prog_id = pick_program_by_keyword(keyword) or ""
        if not prog_id or prog_id not in valid or prog_id in seen_programs:
            continue
        if not program_configured(prog_id):
            continue
        slot = raw.get("slot") if raw.get("slot") in VALID_SLOTS else _auto_slot(len(normalized))
        normalized.append({**raw, "program": prog_id, "slot": slot})
        seen_programs.add(prog_id)
        if len(normalized) >= 4:
            break

    bucket: dict[str, list[dict]] = {"intro": [], "mid": [], "end": []}
    overflow: list[dict] = []
    for item in normalized:
        slot = item["slot"]
        if len(bucket[slot]) < SLOT_LIMITS[slot]:
            bucket[slot].append(item)
        else:
            overflow.append(item)

    for item in overflow:
        for slot in ("mid", "end", "intro"):
            if len(bucket[slot]) < SLOT_LIMITS[slot]:
                item = {**item, "slot": slot}
                bucket[slot].append(item)
                break

    def _fill_slot(slot: str) -> None:
        if bucket[slot]:
            return
        for candidate in configured:
            prog_id = candidate["id"]
            if prog_id in seen_programs or not program_configured(prog_id):
                continue
            prog = resolve_program(prog_id) or {}
            bucket[slot].append({
                "program": prog_id,
                "slot": slot,
                "anchor": prog.get("default_anchor", "詳細はこちら"),
                "heading": prog.get("default_heading", ""),
                "teaser": prog.get("default_teaser", prog.get("description", "")),
                **({"query": keyword} if prog_id == "amazon_search" else {}),
            })
            seen_programs.add(prog_id)
            return

    _fill_slot("intro")
    if not bucket["mid"]:
        _fill_slot("mid")
    _fill_slot("end")

    result: list[dict] = []
    for slot in ("intro", "mid", "end"):
        result.extend(bucket[slot][:SLOT_LIMITS[slot]])
    return result[:4]


def render_affiliate_blocks(
    placements: list[dict] | None,
    site_url: str = "",
    keyword: str = "",
) -> str:
    """後方互換: 末尾結合用（非推奨）。"""
    load_env()
    guide_url = f"{site_url.rstrip('/')}/bitradex-invite-code/" if site_url else ""
    blocks: list[str] = []
    for placement in normalize_affiliate_placements(placements, keyword):
        html = _render_one(placement["program"], placement, guide_url)
        if html:
            blocks.append(html)
    return "\n".join(blocks)


def _find_h2(soup: BeautifulSoup, fragment: str) -> Tag | None:
    for h2 in soup.find_all("h2"):
        if fragment in h2.get_text(strip=True):
            return h2
    return None


def _insert_after(node: Tag | None, html: str) -> None:
    if not node or not html:
        return
    fragment = BeautifulSoup(html, "html.parser")
    aside = fragment.find("aside") or fragment
    node.insert_after(aside)


def _insert_before(node: Tag | None, html: str) -> None:
    if not node or not html:
        return
    fragment = BeautifulSoup(html, "html.parser")
    aside = fragment.find("aside") or fragment
    node.insert_before(aside)


def _intro_anchor(soup: BeautifulSoup) -> Tag | None:
    blockquote = soup.find("blockquote")
    if blockquote:
        target = blockquote
        for sib in blockquote.next_siblings:
            if isinstance(sib, NavigableString) and not str(sib).strip():
                continue
            if isinstance(sib, Tag) and sib.name == "p":
                return sib
            break
        return blockquote
    first_p = soup.find("p")
    return first_p


def inject_affiliates_into_html(
    html: str,
    placements: list[dict] | None,
    *,
    site_url: str = "",
    keyword: str = "",
    fact_heading: str = "いま起きていること（事実）",
    opinion_heading: str = "筆者の考察・見解",
    source_heading: str = "参考・関連情報",
) -> str:
    """記事 HTML に intro / mid / end スロットでバナーを分散配置。"""
    load_env()
    guide_url = f"{site_url.rstrip('/')}/bitradex-invite-code/" if site_url else ""
    items = normalize_affiliate_placements(placements, keyword)
    if not items:
        return html

    rendered: dict[str, list[str]] = {"intro": [], "mid": [], "end": []}
    for placement in items:
        block = _render_one(placement["program"], placement, guide_url)
        if block:
            rendered[placement["slot"]].append(block)

    if not any(rendered.values()):
        return html

    soup = BeautifulSoup(html, "html.parser")

    if rendered["intro"]:
        _insert_after(_intro_anchor(soup), rendered["intro"][0])

    opinion_h2 = _find_h2(soup, opinion_heading)
    fact_h2 = _find_h2(soup, fact_heading)
    source_h2 = _find_h2(soup, source_heading)

    if rendered["mid"]:
        if opinion_h2:
            _insert_before(opinion_h2, rendered["mid"][0])
        elif fact_h2:
            _insert_after(fact_h2, rendered["mid"][0])
        else:
            _insert_after(_intro_anchor(soup), rendered["mid"][0])

    if len(rendered["mid"]) > 1:
        if source_h2:
            _insert_before(source_h2, rendered["mid"][1])
        elif opinion_h2:
            _insert_after(opinion_h2, rendered["mid"][1])

    if rendered["end"]:
        if source_h2:
            _insert_before(source_h2, rendered["end"][0])
        else:
            last_h2 = soup.find_all("h2")
            if last_h2:
                _insert_before(last_h2[-1], rendered["end"][0])
            else:
                soup.append(BeautifulSoup(rendered["end"][0], "html.parser"))

    return str(soup)
