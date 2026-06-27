"""LLMによる記事生成（トレンド反映・事実/考察分離）。"""
from __future__ import annotations

import json
import re
from typing import Any

from config_loader import AUTOMATION_ROOT, load_yaml
from content.json_parse import parse_llm_json
from content.llm_client import complete_json
from content.affiliate_catalog import (
    all_program_ids,
    format_catalog_for_prompt,
    pick_program_by_keyword,
)
from seo.content_policy import get_auto_policy, get_editorial_policy
from seo.validator import apply_legal_filter, validate_meta, validate_title
from seo.ssp_meta import ensure_featured_alt_in_prompts

PROMPT_PATH = AUTOMATION_ROOT / "config" / "prompts" / "article_system.txt"

CRYPTO_HINTS = ("bitradex", "仮想通貨", "暗号資産", "ビットコイン", "btc", "eth", "defi", "自動売買")
BITRADEX_HINTS = ("bitradex", "ai360d")


def _system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    site = load_yaml("site.yaml")
    return f"あなたは「{site['site']['name']}」の編集者。{site['site']['concept']}"


def _topic_text(keyword: str, category: str, title: str = "") -> str:
    return f"{keyword} {category} {title}".lower()


def _needs_crypto_disclaimer(keyword: str, category: str, title: str = "") -> bool:
    text = _topic_text(keyword, category, title)
    return any(h in text for h in CRYPTO_HINTS) or category in ("始め方", "運用・実績", "出金・トラブル", "リスク・評判", "税金")


def _needs_fsa_disclaimer(keyword: str, category: str, title: str = "") -> bool:
    text = _topic_text(keyword, category, title)
    return any(h in text for h in BITRADEX_HINTS)


def _disclaimer_block(keyword: str, category: str, title: str = "") -> str:
    site = load_yaml("site.yaml")
    d = site.get("disclaimer", {})
    lines = [d.get("auto_article", d.get("affiliate", ""))]
    if _needs_crypto_disclaimer(keyword, category, title):
        if _needs_fsa_disclaimer(keyword, category, title):
            lines.append(d.get("fsa", ""))
        lines.append(d.get("crypto", ""))
    lines.append(d.get("general", ""))
    return "> " + " ".join(x for x in lines if x)


def _sanitize_affiliate_placements(
    placements: list[dict] | None,
    keyword: str,
) -> list[dict]:
    valid = all_program_ids()
    result: list[dict] = []
    seen: set[str] = set()

    for placement in placements or []:
        prog_id = placement.get("program", "")
        if prog_id == "a8":
            prog_id = pick_program_by_keyword(keyword) or ""
        if not prog_id or prog_id not in valid or prog_id in seen:
            continue
        result.append({**placement, "program": prog_id})
        seen.add(prog_id)
        if len(result) >= 2:
            break
    return result


def generate_article(
    keyword_item: dict[str, Any],
    internal_links: list[tuple[str, str]],
    trend_context: str = "",
) -> dict[str, Any]:
    keyword = keyword_item["keyword"]
    allowed_cats = get_auto_policy().get("allowed_categories", [])
    editorial = get_editorial_policy()
    body_images = int(load_yaml("site.yaml").get("content", {}).get("body_images", 0))

    link_hints = "\n".join(f"- {slug}: {url}" for slug, url in internal_links)
    fact_h = editorial.get("fact_section_heading", "いま起きていること（事実）")
    opinion_h = editorial.get("opinion_section_heading", "筆者の考察・見解")
    source_h = editorial.get("source_section_heading", "参考・関連情報")
    min_sources = editorial.get("min_reference_sources", 3)
    affiliate_catalog = format_catalog_for_prompt()

    user_prompt = f"""対策キーワード（トレンド起点）: {keyword}
意図カテゴリ: {keyword_item.get('intent', 'C')}

=== 直近ニュース・トレンド（記事に反映すること） ===
{trend_context or '（取得なし。業界の一般的動向を事実と考察に分けて記述）'}

=== 内部リンク候補（2〜3本自然に挿入） ===
{link_hints or '（なし）'}

=== アフィリエイト案件カタログ（記事内容に最も合う id を0〜2件選ぶ） ===
{affiliate_catalog}

=== 必須見出し（H2としてそのまま使用） ===
## {fact_h}
## {opinion_h}
## {source_h}

=== 情報収集フロー（執筆前に必ず実施） ===
1. 上記トレンドヘッドラインをすべて確認
2. 最低{min_sources}つ以上の独立情報源（公式・報道・公的機関等）を想定して事実を突合
3. 食い違いは【事実】で並記、不明は「要確認」
4. 参考情報源を「{source_h}」に{min_sources}件以上列挙

JSONのみ返してください:
{{
  "title": "SEOタイトル（全角32字前後。**特定サービス・制度・ニュース**を明示）",
  "slug": "english-slug-kebab-case",
  "meta_description": "120字前後のメタ（特定トピック＋読者メリット）",
  "category": "カテゴリ名（{'/'.join(allowed_cats)} のいずれか。記事内容に最も合うものを選ぶ）",
  "markdown_body": "記事本文（Markdown）。冒頭免責→結論→必須2セクション→FAQ/補足→{source_h}。事実は【事実】、考察は【考察】で区別。",
  "faq": [{{"question": "...", "answer": "..."}}],
  "affiliate_placements": [
    {{"program": "a8_nisa", "anchor": "SBI証券でNISA口座を開設する（記事に合わせた文言）"}},
    {{"program": "amazon_search", "query": "NISA 初心者 本", "anchor": "NISA入門書をAmazonで探す"}}
  ],
  "image_prompts": [
    {{"prompt": "英語 concept illustration for featured image. no text", "alt": "日本語alt"}},
    {{"placeholder": "[IMAGE:main]", "prompt": "英語 concept diagram. no text", "alt": "日本語alt"}}
  ]
}}

image_prompts:
- 1件目は必須（アイキャッチ）。2件目以降は最大{body_images}件まで（不要なら1件のみ）
- 本文は表・箇条書きを優先し、画像に頼りすぎない。UI操作の手順解説は書かない

affiliate_placements:
- カタログの id を記事テーマに合わせて最大2件（不要なら []）
- A8は id（a8_programs.yaml から自動付与）と anchor（リンク文言）を記事内容に合わせて生成
- amazon_search は query も必須

記事の主軸:
- **特定のサービス・技術・制度・規制** にフォーカス（全体論・入門総論は避ける）
- 最新ニュース・制度改正・規制動向を中心に、**将来の応用・個人的所感** を厚く書く
- 手順・やり方・設定方法のステップ解説は最小限
- 個人（YouTuber等）の評判・批判記事にしない

JSON文字列内の改行は必ず \\n でエスケープ（生改行禁止）。有効なJSONのみ。
"""

    max_attempts = 3
    last_error = ""
    data: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        repair_hint = ""
        if attempt > 1:
            repair_hint = (
                f"前回の応答は無効なJSONでした（{last_error}）。"
                "markdown_body 内の改行は \\n、ダブルクォートは \\\" に修正し、"
                "JSONオブジェクトのみを再出力してください。"
            )
            print(f"  JSON retry {attempt}/{max_attempts}...")
        try:
            raw = complete_json(_system_prompt(), user_prompt, repair_hint=repair_hint)
            data = parse_llm_json(raw)
            break
        except ValueError as exc:
            last_error = str(exc)
            if attempt == max_attempts:
                raise RuntimeError(f"記事JSONの解析に失敗しました: {last_error}") from exc

    assert data is not None

    data["title"] = validate_title(apply_legal_filter(data.get("title", keyword)))
    data["meta_description"] = validate_meta(apply_legal_filter(data.get("meta_description", "")))
    body = apply_legal_filter(data.get("markdown_body", ""))
    body = body.replace("\\n", "\n")

    if fact_h not in body:
        body += f"\n\n## {fact_h}\n\n【事実】（トレンド情報を反映した事実整理）\n"
    if opinion_h not in body:
        body += f"\n\n## {opinion_h}\n\n【考察】（上記事実を踏まえた筆者の見解。不確実性を明記）\n"

    source_h = editorial.get("source_section_heading", "参考・関連情報")
    if source_h not in body:
        body += f"\n\n## {source_h}\n\n- （参考情報源を3件以上列挙）\n"

    if not body.strip().startswith(">"):
        body = _disclaimer_block(keyword, data.get("category", ""), data.get("title", "")) + "\n\n" + body

    data["markdown_body"] = body
    data["slug"] = re.sub(r"[^a-z0-9-]", "", data.get("slug", "").lower())[:80]
    if not data["slug"]:
        data["slug"] = re.sub(r"[^a-z0-9]+", "-", keyword.lower())[:60].strip("-")

    data["affiliate_placements"] = _sanitize_affiliate_placements(
        data.get("affiliate_placements"),
        keyword,
    )
    ensure_featured_alt_in_prompts(data, keyword)

    return data


def markdown_to_html(md: str) -> str:
    import markdown as md_lib
    return md_lib.markdown(md, extensions=["extra", "nl2br", "sane_lists"])


def build_faq_jsonld(faq: list[dict], page_url: str) -> str:
    entities = []
    for item in faq[:5]:
        entities.append({
            "@type": "Question",
            "name": item.get("question", ""),
            "acceptedAnswer": {"@type": "Answer", "text": item.get("answer", "")},
        })
    payload = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    return f'<script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>'
