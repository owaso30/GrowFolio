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

    mid_target = _resolve_mid_target(
        soup,
        fact_heading=fact_heading,
        opinion_heading=opinion_heading,
    )
    if rendered["mid"]:
        _apply_insert(soup, mid_target, rendered["mid"][0])

    if len(rendered["mid"]) > 1:
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


def bitradex_affiliate_placements(slug: str, title: str = "") -> list[dict]:
    """BitradeX系記事の intro / mid / end 配置（記事ごとに Amazon・A8・BitradeX を分散）。"""
    s = slug.lower()
    text = f"{slug} {title}".lower()

    def _b(
        program: str,
        slot: str,
        *,
        heading: str,
        teaser: str,
        anchor: str,
        query: str = "",
    ) -> dict:
        item = {
            "program": program,
            "slot": slot,
            "heading": heading,
            "teaser": teaser,
            "anchor": anchor,
        }
        if query:
            item["query"] = query
        return item

    if "tax" in s:
        return [
            _b(
                "amazon_search",
                "intro",
                query="仮想通貨 税金 確定申告 初心者",
                heading="仮想通貨の税金・確定申告を学ぶなら",
                teaser="暗号資産の損益計算や申告の基礎が分かる入門書を、記事の内容とあわせてAmazonで探せます。",
                anchor="仮想通貨の税金入門書をAmazonで探す",
            ),
            _b(
                "a8_楽天アフィリエイト",
                "mid",
                heading="副業収入の資産化も視野に入れる",
                teaser="運用益の管理と並行して、副業・アフィリエイトで収入源を増やす選択肢もあります。",
                anchor="楽天アフィリエイトで副業を始める",
            ),
            _b(
                "bitradex",
                "end",
                heading="AI運用の公式情報もあわせて確認",
                teaser="税金の話とセットで、BitradeXの運用ルールや出金の流れも押さえておきましょう。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
        ]

    if "affiliate" in s or "referral" in s:
        return [
            _b(
                "bitradex",
                "intro",
                heading="BitradeXの紹介報酬を本気で狙うなら",
                teaser="招待コード・報酬体系・集客のコツまで、公式情報で最新条件を確認できます。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "a8_楽天アフィリエイト",
                "mid",
                heading="アフィリエイトの基礎を固めるなら",
                teaser="紹介報酬を伸ばすには、ASPの仕組み理解も重要です。楽天アフィリエイトから始めるのも一手です。",
                anchor="楽天アフィリエイトに登録する",
            ),
            _b(
                "a8_お名前_com",
                "end",
                heading="紹介用のサイト・ブログを立ち上げる",
                teaser="独自ドメインを取って発信基盤を作れば、紹介リンクの信頼感も高まります。",
                anchor="お名前.comでドメインを取得する",
            ),
        ]

    if "risk" in s or "who-should" in s or "review" in s:
        return [
            _b(
                "amazon_search",
                "intro",
                query="仮想通貨 投資 リスク 本",
                heading="リスクを理解してから判断する",
                teaser="暗号資産の仕組みとリスク管理の基礎が学べる書籍を、Amazonでまとめて探せます。",
                anchor="仮想通貨リスクの入門書をAmazonで探す",
            ),
            _b(
                "bitradex",
                "mid",
                heading="公式の運用ルール・プランを再確認",
                teaser="評判記事だけでなく、AIプランや手数料など一次情報もあわせて確認して判断材料にしましょう。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "a8_dmm証券",
                "end",
                heading="リスク分散の選択肢：つみたて投資も",
                teaser="仮想通貨だけに集中せず、NISAなど堅実な資産形成を並行する考え方もあります。",
                anchor="DMM証券で口座開設を申し込む",
            ),
        ]

    if "withdraw" in s or "network" in s or "kyc" in s:
        return [
            _b(
                "bitradex",
                "intro",
                heading="出金・入金の前に公式手順を確認",
                teaser="ネットワーク設定やKYC、出金先の指定は公式の最新案内が確実です。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "amazon_search",
                "mid",
                query="仮想通貨 ウォレット 入門",
                heading="送金・保管の基礎知識を補強",
                teaser="ネットワークやウォレットの基礎が分かる入門書で、ミス送金のリスクを下げられます。",
                anchor="仮想通貨入門書をAmazonで探す",
            ),
            _b(
                "a8_dmm証券",
                "end",
                heading="国内口座での資産管理も検討",
                teaser="海外サービスと国内証券口座を使い分ける運用設計も、長期的には有効です。",
                anchor="DMM証券で口座開設を申し込む",
            ),
        ]

    if "invite" in s:
        return [
            _b(
                "bitradex",
                "intro",
                heading="招待コードは公式から取得",
                teaser="コードの場所や入力タイミングは変更されることもあるため、公式の案内を優先しましょう。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "amazon_search",
                "mid",
                query="仮想通貨 始め方 本",
                heading="始める前に基礎を押さえる",
                teaser="招待コードを使う前に、暗号資産の基礎知識を入門書で固めておくと安心です。",
                anchor="仮想通貨入門書をAmazonで探す",
            ),
            _b(
                "a8_お名前_com",
                "end",
                heading="紹介記事を書くならドメインから",
                teaser="自分のメディアで紹介する場合、独自ドメインがあると信頼感が増します。",
                anchor="お名前.comでドメインを取得する",
            ),
        ]

    if "ai-plan" in s:
        return [
            _b(
                "bitradex",
                "intro",
                heading="AI運用プランは公式で比較",
                teaser="Daily・30D・90Dなど各プランの条件は、公式の最新情報で確認するのが確実です。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "amazon_search",
                "mid",
                query="AI 投資 自動化 本",
                heading="AI運用の考え方を深掘り",
                teaser="アルゴリズム運用やリスク管理の考え方が学べる書籍をAmazonで探せます。",
                anchor="AI投資の入門書をAmazonで探す",
            ),
            _b(
                "a8_dmm証券",
                "end",
                heading="攻めと守りのポートフォリオ設計",
                teaser="AI運用と並行して、NISAで長期資産を組み合わせる選択肢もあります。",
                anchor="DMM証券で口座開設を申し込む",
            ),
        ]

    if "start" in s or "guide" in s or "smartphone" in s:
        return [
            _b(
                "bitradex",
                "intro",
                heading="BitradeXを始めるなら公式から",
                teaser="登録・入金・AI運用開始まで、最新の手順と招待コードの要否を公式で確認できます。",
                anchor="BitradeXの公式サイトで詳細を見る",
            ),
            _b(
                "amazon_search",
                "mid",
                query="仮想通貨 初心者 本 2026",
                heading="始める前に入門書で基礎固め",
                teaser="仕組みとリスクを理解してから始められるよう、初心者向けの書籍をAmazonで探しましょう。",
                anchor="仮想通貨入門書をAmazonで探す",
            ),
            _b(
                "a8_エックスサーバー_5",
                "end",
                heading="運用記録・発信ブログを作るなら",
                teaser="自分の投資メモや実践記を残すブログ基盤は、エックスサーバーからすぐ始められます。",
                anchor="エックスサーバーでレンタルサーバーを申し込む",
            ),
        ]

    # フォールバック（BitradeX系のその他）
    return [
        _b(
            "bitradex",
            "intro",
            heading="BitradeXの最新情報は公式で",
            teaser="プラン・手数料・キャンペーンは変更されるため、都度公式サイトで確認しましょう。",
            anchor="BitradeXの公式サイトで詳細を見る",
        ),
        _b(
            "amazon_search",
            "mid",
            query="仮想通貨 BitradeX" if "bitradex" in text else "仮想通貨 初心者",
            heading="関連書籍で理解を深める",
            teaser="記事のテーマに合う仮想通貨・投資の入門書をAmazonでまとめて探せます。",
            anchor="関連書籍をAmazonで探す",
        ),
        _b(
            "a8_vps",
            "end",
            heading="副業・発信基盤を整えるなら",
            teaser="投資ノートやアフィリエイトサイトを運用するなら、VPSで本格的な環境を構築できます。",
            anchor="エックスサーバーVPSを申し込む",
        ),
    ]


def it_career_affiliate_placements(*, intro_query: str = "AI コーディング エディタ 開発 入門") -> list[dict]:
    """ITキャリア系記事の intro / mid / end 配置（id=266 準拠）。"""
    return [
        {
            "program": "amazon_search",
            "slot": "intro",
            "query": intro_query,
            "heading": "AI開発・エディタ活用の基礎を書籍で固める",
            "teaser": "CopilotやVSCodeを使いこなすための開発スキル・プロンプト設計の入門書をAmazonでまとめて探せます。",
            "anchor": "AI開発入門書をAmazonで探す",
        },
        {
            "program": "a8_お名前_com",
            "slot": "mid",
            "heading": "開発ポートフォリオ・技術ブログを始めるなら",
            "teaser": "ITキャリアアップには自分の技術発信が有効です。ドメイン取得から始めてポートフォリオサイトを構築しましょう。",
            "anchor": "お名前.comでドメインを取得する",
        },
        {
            "program": "a8_楽天アフィリエイト",
            "slot": "end",
            "heading": "開発スキルで稼ぐ×資産形成を同時に進める",
            "teaser": "ITスキルで副業収入を増やしながら、楽天経済圏を活用した資産形成も検討してみましょう。",
            "anchor": "楽天アフィリエイトで副業を始める",
        },
    ]


def reapply_affiliates_to_html(
    html: str,
    placements: list[dict] | None,
    *,
    site_url: str = "",
    keyword: str = "",
    fact_heading: str = "いま起きていること（事実）",
    opinion_heading: str = "筆者の考察・見解",
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

