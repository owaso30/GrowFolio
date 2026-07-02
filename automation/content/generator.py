"""LLMによる記事生成（トレンド反映・事実/考察分離）。"""
from __future__ import annotations

import json
import re
from typing import Any

from config_loader import AUTOMATION_ROOT, load_yaml
from content.json_parse import parse_llm_json
from content.llm_client import complete_json
from content.affiliate_catalog import format_catalog_for_prompt
from content.affiliate_renderer import normalize_affiliate_placements
from images.brand_image import normalize_image_prompts
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

    forced_category = keyword_item.get("category", "").strip()
    category_instruction = (
        f"指定カテゴリ（必ずこのカテゴリ名を category に使用）: {forced_category}"
        if forced_category
        else f"category は {'/'.join(allowed_cats)} のいずれかから記事内容に最も合うものを選ぶ"
    )

    user_prompt = f"""対策キーワード（トレンド起点）: {keyword}
意図カテゴリ: {keyword_item.get('intent', 'C')}
{category_instruction}

=== 直近ニュース・トレンド（記事に反映すること） ===
{trend_context or '（取得なし。業界の一般的動向を事実と考察に分けて記述）'}

=== 内部リンク候補（2〜3本自然に挿入） ===
{link_hints or '（なし）'}

=== アフィリエイト案件カタログ（記事に合う id を3〜4件、スロット別に選ぶ） ===
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
  "title": "SEOタイトル（全角50〜60字目安。長くても省略せず全文。**特定サービス・制度・ニュース**を明示）",
  "slug": "english-slug-kebab-case",
  "meta_description": "120字前後のメタ（特定トピック＋読者メリット）",
  "category": "カテゴリ名（{'/'.join(allowed_cats)} のいずれか。記事内容に最も合うものを選ぶ）",
  "markdown_body": "記事本文（Markdown）。冒頭免責→[[結論|...]]→必須2セクション→FAQ/補足→{source_h}。事実は【事実】、考察は【考察】。重要箇所は [[要点|...]] [[注意|...]]、==マーカー==、++最重要フレーズ++。",
  "faq": [{{"question": "...", "answer": "..."}}],
  "affiliate_placements": [
    {{
      "program": "a8_nisa",
      "slot": "intro",
      "heading": "NISA口座を開設するなら今がチャンス",
      "teaser": "制度改正を踏まえ、口座開設からつみたてまで一気通貫で始められます。",
      "anchor": "SBI証券でNISA口座を開設する"
    }},
    {{
      "program": "amazon_search",
      "slot": "mid",
      "heading": "関連書籍で基礎を固める",
      "teaser": "記事のテーマに合う入門書をAmazonでまとめて探せます。",
      "query": "NISA 初心者 本",
      "anchor": "NISA入門書をAmazonで探す"
    }},
    {{
      "program": "bitradex",
      "slot": "end",
      "heading": "次のステップ：AI運用を試すなら",
      "teaser": "仮想通貨AI運用の公式情報もあわせて確認できます。",
      "anchor": "BitradeXの公式サイトで詳細を見る"
    }}
  ],
  "image_prompts": [
    {{"source": "brand", "brand_key": "vscode", "scene_prompt": "英語で記事の具体内容を描く近未来イラスト（UIやワークフローが分かるもの・読める文字なし）", "alt": "日本語alt（主題サービス名＋記事テーマ）"}},
    {{"source": "brand", "brand_key": "vscode", "placeholder": "[IMAGE:main]", "alt": "日本語alt"}}
  ]
}}

image_prompts:
- 1件目は必須（アイキャッチ）。2件目以降は最大{body_images}件まで（不要なら1件のみ）
- **アイキャッチはハイブリッド**: 記事の主題サービスがある場合は `"source": "brand"` + `brand_key`（左に公式ロゴ、右に記事テーマの近未来イラストを自動合成）
- **brand_key は記事の主題に合わせる**（例: VS Codeアップデート記事→vscode、Copilot料金比較→github_copilot、Cursor比較→cursor、BitradeX→bitradex）。空欄でも可（自動判定）
- より具体的な背景にしたい場合は `scene_prompt`（英語・記事内容を具体的に・読める文字や公式ロゴなし）を任意で指定
- 背景は **記事テーマが一目で分かる近未来イラスト**（UI・ワークフロー・比較図など）。写真風よりクリーンなベクター寄りイラスト
- 本文画像は brand（ロゴのみ）または控えめな Flux
- brand_key 例: bitradex / github_copilot / cursor / vscode / claude / microsoft_365
- Flux のみの場合も prompt / scene_prompt は記事テーマ直結の近未来イラスト。読める文字・公式ロゴ・実画面スクショの伪造は禁止
- 実残高スクショ風・管理画面の伪造は禁止

affiliate_placements:
- **最大3件**を slot 別に指定（intro 1件 / mid 1件 / end 1件）。記事末に並ぶのは end のみ
- 各件に program, slot, heading（20〜35字の魅力的な見出し）, teaser（1〜2行の訴求文）, anchor を必須
- A8は id（a8_programs.yaml）と anchor を記事内容に合わせて生成
- amazon_search は query も必須
- 記事テーマに合わない案件は選ばない（空配列 [] も可）

重要箇所の強調（必須）:
- 結論先出し: [[結論|2〜4文]]
- 記事中盤: [[要点|...]] / [[注意|...]] / [[リスク|...]] を合計2〜4ブロック
- インライン: ==キーワード==（黄）、++最重要1フレーズ++（青）を各セクションに適宜
- **太字** も使うが1段落の装飾は2種類まで

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

    data["affiliate_placements"] = normalize_affiliate_placements(
        data.get("affiliate_placements"),
        keyword,
    )
    data["image_prompts"] = normalize_image_prompts(
        data.get("image_prompts"),
        keyword=keyword,
        title=data.get("title", ""),
        category=data.get("category", ""),
        slug=data.get("slug", ""),
        max_body=max(0, min(body_images, 1)),
    )
    ensure_featured_alt_in_prompts(data, keyword)

    return data


def markdown_to_html(md: str) -> str:
    import markdown as md_lib

    from content.emphasis import apply_emphasis_html, apply_emphasis_markdown
    from content.label_badges import apply_label_badges
    from content.source_links import format_source_section_html

    md = apply_emphasis_markdown(md)
    html = md_lib.markdown(md, extensions=["extra", "nl2br", "sane_lists"])
    html = apply_emphasis_html(html)
    html = apply_label_badges(html)
    return format_source_section_html(html)


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
