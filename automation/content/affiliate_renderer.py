"""一般・BitradeX・A8 アフィリエイトCTAのHTML生成。"""
from __future__ import annotations

import os
from urllib.parse import quote

from config_loader import load_env
from content.affiliate_catalog import (
    all_program_ids,
    is_a8_program,
    pick_program_by_keyword,
    program_configured,
    resolve_program,
)


def _build_url(program: dict, placement: dict) -> str:
    if program.get("program_type") == "a8":
        return (program.get("url") or "").strip()
    if program.get("url_template"):
        tag = os.environ.get(program.get("tag_env", ""), "")
        query = quote(placement.get("query", placement.get("anchor", "")))
        return program["url_template"].format(query=query, tag=tag, anchor=quote(placement.get("anchor", "")))
    url_env = program.get("url_env", "")
    return os.environ.get(url_env, program.get("default_url", ""))


def _render_one(prog_id: str, placement: dict, guide_url: str) -> str | None:
    if prog_id not in all_program_ids():
        return None

    program = resolve_program(prog_id)
    if not program or not program.get("cta_template"):
        return None

    url = _build_url(program, placement)
    if prog_id == "amazon_search" and (not url or "tag=&" in url or url.endswith("tag=")):
        return None
    if prog_id == "bitradex" and not url:
        return None
    if is_a8_program(prog_id) and not url:
        return None

    anchor = placement.get("anchor") or program.get("default_anchor") or program.get("name", "詳細はこちら")
    return program["cta_template"].format(url=url, anchor=anchor, guide_url=guide_url)


def render_affiliate_blocks(
    placements: list[dict] | None,
    site_url: str = "",
    keyword: str = "",
) -> str:
    load_env()
    blocks: list[str] = []
    guide_url = f"{site_url.rstrip('/')}/bitradex-invite-code/" if site_url else ""

    items = list(placements or [])
    seen_programs: set[str] = set()
    for placement in items[:2]:
        prog_id = placement.get("program", "")
        if prog_id in seen_programs:
            continue
        html = _render_one(prog_id, placement, guide_url)
        if html:
            blocks.append(html)
            seen_programs.add(prog_id)

    if not any(is_a8_program(p) for p in seen_programs) and keyword:
        fallback_id = pick_program_by_keyword(keyword, a8_only=True)
        if fallback_id and program_configured(fallback_id):
            prog = resolve_program(fallback_id) or {}
            placement = {
                "program": fallback_id,
                "anchor": prog.get("default_anchor", ""),
            }
            html = _render_one(fallback_id, placement, guide_url)
            if html and len(blocks) < 2:
                blocks.append(html)

    return "\n".join(blocks)
