"""Amazon・A8 アフィリエイトCTAのHTML生成と記事内配置。"""
from __future__ import annotations

import os
import re
from html import escape
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
SLOT_LIMITS = {"intro": 1, "mid": 1, "end": 1}


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


def amazon_search_url(query: str) -> str | None:
    load_env()
    program = resolve_program("amazon_search") or {}
    tag = os.environ.get(program.get("tag_env", "AMAZON_AFFILIATE_TAG"), "")
    template = program.get("url_template") or ""
    if not tag or not template:
        return None
    return template.format(query=quote(query), tag=tag)


def rakuten_search_url(query: str) -> str:
    """承認済み楽天アフィリエイトIDで、モール検索へ飛ばす。"""
    cfg = _affiliates_cfg().get("rakuten") or {}
    hgc = cfg.get(
        "hgc_path",
        "0ea62065.34400275.0ea62066.204f04c0/a26062729741_4B65SJ_5O7P9U_2HOM_6C1VM",
    )
    prefix = cfg.get(
        "a8_prefix",
        "https://rpx.a8.net/svt/ejp?a8mat=4B65SJ+5O7P9U+2HOM+6C1VM&rakuten=y&a8ejpredirect=",
    )
    landing = "https://search.rakuten.co.jp/search/mall/" + quote(query) + "/"
    hb = (
        f"http://hb.afl.rakuten.co.jp/hgc/{hgc}"
        f"?pc={quote(landing, safe='')}&m={quote(landing, safe='')}"
    )
    return prefix + quote(hb, safe="")


def render_shop_pair(
    query: str,
    note: str = "",
    heading: str = "",
    image_url: str = "",
    image_alt: str = "",
) -> str:
    """Amazon と楽天を同じ枠に並べる。CTA は価格・在庫の確認。"""
    query = query.strip()
    note = note.strip()
    heading = heading.strip() or "価格と在庫を確認する"
    image_url = image_url.strip()
    image_alt = image_alt.strip() or f"{query}の商品画像"
    amazon = amazon_search_url(query)
    rakuten = rakuten_search_url(query)
    btn = (
        "display:block;padding:.9em .6em;color:#fff !important;font-weight:700;"
        "text-decoration:none;border-radius:8px;text-align:center;line-height:1.45;"
    )
    cells = []
    if amazon:
        cells.append(
            "<td style=\"width:50%;vertical-align:top;\">"
            f"<a href=\"{escape(amazon, quote=True)}\" style=\"{btn}background:#c2410c;\" "
            "rel=\"nofollow sponsored noopener\" target=\"_blank\">Amazonで価格・在庫を確認</a></td>"
        )
    cells.append(
        "<td style=\"width:50%;vertical-align:top;\">"
        f"<a href=\"{escape(rakuten, quote=True)}\" style=\"{btn}background:#bf0000;\" "
        "rel=\"nofollow sponsored noopener\" target=\"_blank\">楽天市場で価格・在庫を確認</a></td>"
    )
    note_html = f"<p style=\"margin:0 0 .9em;font-size:.95em;line-height:1.75;color:#334155;\">{escape(note)}</p>" if note else ""
    image_html = ""
    if image_url:
        image_html = (
            '<p style="margin:0 0 1em;text-align:center;">'
            f'<img src="{escape(image_url, quote=True)}" alt="{escape(image_alt)}" '
            'style="max-width:360px;width:100%;height:auto;background:#fff;" />'
            "</p>"
        )
    return (
        "<aside class=\"growfolio-shops\" role=\"complementary\" "
        "style=\"margin:2em 0;padding:1.25em 1.35em;border:2px solid #d6d3d1;"
        "border-radius:14px;background:#fff;box-shadow:0 4px 14px rgba(15,23,42,.06);\">"
        "<p style=\"margin:0 0 .35em;font-size:.78em;font-weight:700;letter-spacing:.04em;color:#78716c;\">"
        "広告・アフィリエイト</p>"
        f"<h3 style=\"margin:0 0 .6em;font-size:1.08em;line-height:1.55;color:#0f172a;\">{escape(heading)}</h3>"
        f"<p style=\"margin:0 0 .8em;font-size:.95em;line-height:1.75;color:#334155;\">"
        f"今回の記事で触れているのは「{escape(query)}」の検索です。"
        "同シリーズでも長さ・硬さ・番手が異なるため、購入前に仕様を確認してください。</p>"
        f"{image_html}"
        f"{note_html}"
        "<table style=\"width:100%;border-collapse:separate;border-spacing:12px 0;margin:0;\">"
        f"<tr>{''.join(cells)}</tr></table>"
        "</aside>"
    )


_SHOP_TOKEN = re.compile(
    r"\[\[SHOP\|([^|\]]+)(?:\|([^|\]]*))?(?:\|([^|\]]*))?(?:\|([^|\]]*))?\]\]"
)


def prepare_shop_image_placeholders(md: str) -> tuple[str, list[dict[str, str]]]:
    """画像URLが無い購入枠に、あとから差し替える印を付ける。"""
    jobs: list[dict[str, str]] = []

    def repl(match: re.Match[str]) -> str:
        query = match.group(1).strip()
        note = (match.group(2) or "").strip()
        image_url = (match.group(3) or "").strip()
        image_alt = (match.group(4) or "").strip() or f"{query}の商品画像"
        if image_url.startswith("http"):
            return match.group(0)
        placeholder = f"SHOP_IMAGE_{len(jobs) + 1}"
        jobs.append({"placeholder": placeholder, "query": query, "alt": image_alt})
        return f"[[SHOP|{query}|{note}|{placeholder}|{image_alt}]]"

    return _SHOP_TOKEN.sub(repl, md), jobs


def expand_shop_tokens(md: str) -> str:
    """本文中の [[SHOP|検索語|補足|画像URL|画像alt]] を、商品画像と購入ボタンに変える。"""

    def repl(match: re.Match[str]) -> str:
        query = match.group(1).strip()
        note = (match.group(2) or "").strip()
        image_url = (match.group(3) or "").strip()
        image_alt = (match.group(4) or "").strip()
        return "\n\n" + render_shop_pair(
            query,
            note,
            image_url=image_url,
            image_alt=image_alt,
        ) + "\n\n"

    return _SHOP_TOKEN.sub(repl, md)


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
        f"</aside>"
    )


def _render_one(prog_id: str, placement: dict, guide_url: str) -> str | None:
    if prog_id not in all_program_ids():
        return None

    program = resolve_program(prog_id)
    if not program:
        return None

    if prog_id == "amazon_search":
        query = str(placement.get("query") or placement.get("anchor") or "").strip()
        if not query or not amazon_search_url(query):
            return None
        return render_shop_pair(
            query,
            str(placement.get("teaser") or ""),
            heading=str(placement.get("heading") or ""),
        )

    url = _build_url(program, placement)
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
    """スロット正規化・不足分の自動補完（intro 1 / mid 1 / end 1）。"""
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
    guide_url = ""
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


def _content_h2s(soup: BeautifulSoup) -> list[Tag]:
    """関連記事リンク以外の本文 h2。"""
    h2s: list[Tag] = []
    for h2 in soup.find_all("h2"):
        text = h2.get_text(strip=True)
        if "関連記事" in text:
            continue
        h2s.append(h2)
    return h2s


def _resolve_mid_target(
    soup: BeautifulSoup,
    *,
    fact_heading: str,
    opinion_heading: str,
) -> tuple[str, Tag] | None:
    """mid バナーの挿入位置（before/after, 基準ノード）。"""
    opinion_h2 = _find_h2(soup, opinion_heading)
    if opinion_h2:
        return ("before", opinion_h2)

    fact_h2 = _find_h2(soup, fact_heading)
    if fact_h2:
        return ("after", fact_h2)

    h2s = _content_h2s(soup)
    if len(h2s) >= 4:
        return ("before", h2s[3])
    if len(h2s) >= 3:
        return ("before", h2s[2])
    if len(h2s) >= 2:
        return ("before", h2s[1])
    if h2s:
        return ("after", h2s[0])
    return None


def _resolve_second_mid_target(
    soup: BeautifulSoup,
    *,
    opinion_heading: str,
    fact_heading: str,
) -> tuple[str, Tag] | None:
    """2件目の mid 用。記事末（FAQ・参考）の直前ではなく、考察セクション内へ寄せる。"""
    opinion_h2 = _find_h2(soup, opinion_heading)
    h2s = _content_h2s(soup)
    for h2 in h2s:
        text = h2.get_text(strip=True)
        if any(key in text for key in ("FAQ", "よくある質問", "まとめ", "参考")):
            if opinion_h2:
                return ("before", h2)
            break
    if opinion_h2:
        return ("after", opinion_h2)
    return _resolve_mid_target(
        soup,
        fact_heading=fact_heading,
        opinion_heading=opinion_heading,
    )


def _resolve_end_target(soup: BeautifulSoup, *, source_heading: str) -> tuple[str, Tag] | None:
    """end バナーの挿入位置。"""
    source_h2 = _find_h2(soup, source_heading)
    if source_h2:
        return ("before", source_h2)

    h2s = _content_h2s(soup)
    for h2 in reversed(h2s):
        text = h2.get_text(strip=True)
        if any(key in text for key in ("まとめ", "FAQ", "よくある質問")):
            return ("before", h2)
    if h2s:
        return ("before", h2s[-1])
    return None


def _apply_insert(soup: BeautifulSoup, target: tuple[str, Tag] | None, html: str) -> None:
    if not target or not html:
        return
    mode, node = target
    if mode == "before":
        _insert_before(node, html)
    else:
        _insert_after(node, html)


def inject_affiliates_into_html(
    html: str,
    placements: list[dict] | None,
    *,
    site_url: str = "",
    keyword: str = "",
    fact_heading: str = "現場の条件（事実）",
    opinion_heading: str = "週末にやるなら（判断）",
    source_heading: str = "参考・関連情報",
) -> str:
    """記事 HTML に intro / mid / end スロットでバナーを分散配置。"""
    if "growfolio-shops" in html:
        return html
    load_env()
    guide_url = ""
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

    mid_target = _resolve_mid_target(
        soup,
        fact_heading=fact_heading,
        opinion_heading=opinion_heading,
    )
    if rendered["mid"]:
        _apply_insert(soup, mid_target, rendered["mid"][0])

    if len(rendered["mid"]) > 1:
        # end スロットがある場合、2件目の mid を記事末に置かない（末尾は end 1件のみ）
        if rendered["end"]:
            second_mid_target = _resolve_second_mid_target(
                soup,
                opinion_heading=opinion_heading,
                fact_heading=fact_heading,
            )
        else:
            end_target = _resolve_end_target(soup, source_heading=source_heading)
            second_mid_target = end_target or mid_target
        _apply_insert(soup, second_mid_target, rendered["mid"][1])

    end_target = _resolve_end_target(soup, source_heading=source_heading)
    if rendered["end"]:
        if end_target:
            _apply_insert(soup, end_target, rendered["end"][0])
        else:
            soup.append(BeautifulSoup(rendered["end"][0], "html.parser"))

    return str(soup)


_LEGACY_AFFILIATE_RE = re.compile(
    r'<aside class="growfolio-affiliate[^>]*>.*?</aside>\s*'
    r'|<p class="affiliate-cta">.*?</p>\s*'
    r'|<div class="swell-block-button[^>]*>.*?</div>\s*',
    re.DOTALL,
)
_INLINE_SPONSORED_AMAZON_RE = re.compile(
    r'<a href="[^"]*amazon\.co\.jp[^"]*"[^>]*rel="[^"]*sponsored[^"]*"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)


def strip_legacy_affiliate_html(html: str) -> str:
    """末尾CTA・SWELLボタン・旧バナーを除去。インラインの sponsored Amazon リンクもテキスト化。"""
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for aside in soup.find_all("aside", class_="growfolio-affiliate"):
        aside.decompose()
    for tag in soup.find_all(True):
        if tag.name == "aside":
            continue
        classes = tag.get("class")
        if not classes:
            continue
        cleaned = [cls for cls in classes if not cls.startswith("growfolio-affiliate")]
        if cleaned:
            tag["class"] = cleaned
        elif "class" in tag.attrs:
            del tag["class"]
    html = str(soup)
    html = _LEGACY_AFFILIATE_RE.sub("", html)
    html = _INLINE_SPONSORED_AMAZON_RE.sub(r"\1", html)
    # FAQ 内など tag なし Amazon リンクも除去（バナー intro に集約）
    html = re.sub(
        r'<a href="[^"]*amazon\.co\.jp[^"]*">([^<]+)</a>',
        r"\1",
        html,
        flags=re.IGNORECASE,
    )
    return html


def reapply_affiliates_to_html(
    html: str,
    placements: list[dict] | None,
    *,
    site_url: str = "",
    keyword: str = "",
    fact_heading: str = "現場の条件（事実）",
    opinion_heading: str = "週末にやるなら（判断）",
    source_heading: str = "参考・関連情報",
) -> str:
    """旧アフィリエイトを除去してから intro / mid / end バナーを再配置。"""
    cleaned = strip_legacy_affiliate_html(html)
    return inject_affiliates_into_html(
        cleaned,
        placements,
        site_url=site_url,
        keyword=keyword,
        fact_heading=fact_heading,
        opinion_heading=opinion_heading,
        source_heading=source_heading,
    )

