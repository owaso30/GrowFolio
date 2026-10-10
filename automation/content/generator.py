"""LLMによる記事生成（トレンド反映・事実/考察分離）。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from config_loader import AUTOMATION_ROOT, load_yaml
from content.json_parse import parse_llm_json
from content.llm_client import complete_json
from content.affiliate_renderer import normalize_affiliate_placements
from images.brand_image import normalize_image_prompts
from seo.content_policy import get_auto_policy
from seo.validator import apply_legal_filter, validate_meta, validate_title
from seo.ssp_meta import ensure_featured_alt_in_prompts

PROMPT_PATH = AUTOMATION_ROOT / "config" / "prompts" / "article_system.txt"
RULES_PATH = AUTOMATION_ROOT.parent / "投稿ルール.md"


def _system_prompt() -> str:
    parts: list[str] = []
    if RULES_PATH.exists():
        parts.append(RULES_PATH.read_text(encoding="utf-8"))
    if PROMPT_PATH.exists():
        parts.append(PROMPT_PATH.read_text(encoding="utf-8"))
    if parts:
        return "\n\n".join(parts)
    site = load_yaml("site.yaml")
    return f"あなたは「{site['site']['name']}」の編集者。{site['site']['concept']}"


def _missing_place_or_time(body: str) -> bool:
    has_place = "千葉" in body
    has_time = re.search(r"\d{1,2}時|朝マズメ|夕マズメ|早朝|夕方|夜", body) is not None
    return not (has_place and has_time)


def ensure_catch_placeholder(md: str, placeholder: str = "[IMAGE:1]") -> str:
    """釣果の段落の直後に、釣れた魚の写真位置を置く。"""
    if placeholder in md:
        return md
    blocks = md.split("\n\n")
    for index, block in enumerate(blocks):
        if any(key in block for key in ("釣果", "釣れ", "揚が")):
            blocks.insert(index + 1, placeholder)
            return "\n\n".join(blocks)
    for index, block in enumerate(blocks):
        if "[[SHOP|" in block:
            blocks.insert(index, placeholder)
            return "\n\n".join(blocks)
    blocks.append(placeholder)
    return "\n\n".join(blocks)


def _disclaimer_block(keyword: str, category: str, title: str = "") -> str:
    del keyword, category, title
    site = load_yaml("site.yaml")
    note = site.get("disclaimer", {}).get("affiliate", "本記事はアフィリエイト広告を含みます。")
    return (
        f'<p style="margin:0 0 1.6em;font-size:0.75em;line-height:1.5;color:#8a8175;text-align:right;">{note}</p>'
    )


def tag_catalog() -> list[dict[str, Any]]:
    """設定済みタグ。group は species（釣種）か gear（道具）。"""
    groups = load_yaml("site.yaml").get("tags") or {}
    catalog: list[dict[str, Any]] = []
    for group, items in groups.items():
        for item in items or []:
            catalog.append({
                "name": item["name"],
                "slug": item.get("slug", ""),
                "group": group,
                "match": list(item.get("match") or [item["name"]]),
            })
    return catalog


def _tag_hit(text: str, hint: str) -> bool:
    if hint == "ライン":
        return re.search(r"(?<!オン)ライン", text) is not None
    return hint.lower() in text.lower()


def select_tags(keyword: str, title: str, body: str, requested: Any) -> list[str]:
    """釣種は最大1つ、道具は記事の対象だけ。一覧外のタグは捨てる。"""
    catalog = tag_catalog()
    by_name = {item["name"]: item for item in catalog}
    requested_names: list[str] = []
    if isinstance(requested, list):
        for name in requested:
            if isinstance(name, str) and name in by_name and name not in requested_names:
                requested_names.append(name)

    focus = f"{keyword} {title}"
    full = f"{focus} {body}"

    def matched(item: dict[str, Any], text: str) -> bool:
        return any(_tag_hit(text, hint) for hint in item["match"])

    species = next((name for name in requested_names if by_name[name]["group"] == "species"), "")
    if not species:
        for item in catalog:
            if item["group"] == "species" and matched(item, full):
                species = item["name"]
                break

    gear = [name for name in requested_names if by_name[name]["group"] == "gear"]
    if not gear:
        gear = [
            item["name"]
            for item in catalog
            if item["group"] == "gear" and matched(item, focus)
        ]

    chosen: list[str] = []
    if species:
        chosen.append(species)
    for name in gear:
        if name not in chosen:
            chosen.append(name)
    return chosen


def format_past_articles(posts: list[dict[str, Any]]) -> str:
    """公開済み記事を、続きを書くための短いメモにする。"""
    if not posts:
        return "（過去記事なし。旬の魚で最初の体験談にする。）"
    lines: list[str] = []
    for post in posts[-8:]:
        tags = " / ".join(str(name) for name in (post.get("tags") or []) if name)
        recap = str(post.get("recap") or post.get("title") or "").strip()
        title = str(post.get("title") or "").strip()
        url = str(post.get("url") or "").strip()
        head = f"- {title}"
        if tags:
            head += f"（{tags}）"
        if url:
            head += f" {url}"
        lines.append(head)
        if recap and recap != title:
            lines.append(f"  前回の内容: {recap}")
    return "\n".join(lines)


def generate_article(
    keyword_item: dict[str, Any],
    internal_links: list[tuple[str, str]],
    trend_context: str = "",
    past_articles: str = "",
) -> dict[str, Any]:
    keyword = keyword_item["keyword"]
    allowed_cats = get_auto_policy().get("allowed_categories", [])
    body_images = int(load_yaml("site.yaml").get("content", {}).get("body_images", 0))

    today = datetime.now()
    link_hints = "\n".join(f"- {slug}: {url}" for slug, url in internal_links)

    forced_category = keyword_item.get("category", "").strip()
    if forced_category and forced_category in allowed_cats:
        category_instruction = f"指定カテゴリ（必ずこのカテゴリ名を category に使用）: {forced_category}"
    elif len(allowed_cats) == 1:
        category_instruction = f"category は必ず「{allowed_cats[0]}」にする"
    else:
        category_instruction = f"category は {'/'.join(allowed_cats)} のいずれかから記事内容に最も合うものを選ぶ"

    user_prompt = f"""対策キーワード（トレンド起点）: {keyword}
意図カテゴリ: {keyword_item.get('intent', 'C')}
{category_instruction}

=== 直近の動向（記事の判断に使う。本文をニュースまとめにしない） ===
{trend_context or '（取得なし。現場で再現できる手順と、確認できない数字は書かない）'}

=== 内部リンク候補（本文の疑問に答えるものだけ。2本前後） ===
{link_hints or '（なし）'}
リンク文言は「こちら」にせず、リンク先で何が分かるかを書く。

=== 今日と、これまでの記事 ===
今日は{today.year}年{today.month}月。基本は、この時期に千葉の海で旬の魚を狙う。サーフ（ヒラメ、マゴチ、シロギスなど）は外さない。
海では、サーフに限らず外道としてフグ、ゴンズイ、アカエイ、サメがよく釣れる。珍しい出来事として書かない。フグは食べない。エイやサメには不用意に触らない。
{past_articles or '（過去記事なし。旬の魚で最初の体験談にする。）'}
同じ魚なら、前回の釣り具・場所・時間・釣果のどれかを変えた続きにする。前回の文は写さない。
別の魚なら、冒頭で過去の釣行に触れてから今回の魚へ移る。

=== 書き方 ===
投稿ルール.mdに従う。体験談。ですます調。物語にしない。
時間帯と、千葉県でその魚の釣果実績がある場所を入れる。タイトルには場所、時間帯、狙った魚を入れる。
良かった点は公開情報の感触を調べ、言い回しは自分の言葉にする。原文は写さない。
釣果を盛らない。少数回で一番釣れるとは書かない。文字数は水増ししない。

JSONのみ返してください:
{{
  "title": "役割が分かるタイトル。釣り種と道具か悩みを入れる",
  "slug": "english-slug-kebab-case",
  "meta_description": "120字以内。結論と、誰の何が分かるか",
  "category": "カテゴリ名（{'/'.join(allowed_cats)} のいずれか）",
  "tags": ["根魚", "ルアー"],
  "role": "problem",
  "markdown_body": "短い免責のあと、その日のメモ。見出しは少なく。釣果の段落の直後に [IMAGE:1]。購入位置に [[SHOP|検索語|補足]]。==品名== と ++感触一箇所++。",
  "recap": "場所、時間、魚、使ったもの、釣果を1文。次回が続きを書くためのメモ",
  "faq": [{{"question": "...", "answer": "..."}}],
  "affiliate_placements": [],
  "image_prompts": [
    {{"source": "flux", "scene_prompt": "the specific tackle from the article resting on a wet rock, lower-left, harbor blurred behind", "alt": "写っている道具と場所を日本語で"}}
  ]
}}

購入リンク:
- affiliate_placements は空配列
- 本文の、その品の話が一段落したところに [[SHOP|検索語|補足]] を1〜2箇所。画像URLは空でよい。パイプラインが同じ商品の別写真を付ける
- 検索語は記事に出た道具そのもの。別の商品名にしない
image_prompts:
- 1件目だけ。アイキャッチの中身になる写真。枠も文字も入れない
- scene_prompt は、その記事の道具が、書いた場所の岩やテトラの上にある光景。左下に主役、背景はぼかす
- 釣れた魚の写真は書かない。[IMAGE:1] の位置にパイプラインが入れる
- alt は写っている道具と場所を日本語で

tags:
- 釣種は 根魚 / サーフ / シーバス / チニング / アジング / ブラックバス / トラウト から最大1つ。シーバスはブラックバスにしない
- 道具は ロッド / リール / ルアー / ライン / バッグ から、記事の主役だけ

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

    if _missing_place_or_time(apply_legal_filter(str(data.get("markdown_body", "")))):
        print("  place/time retry...")
        try:
            raw = complete_json(
                _system_prompt(),
                user_prompt,
                repair_hint=(
                    "本文に、千葉県でその魚の釣果実績がある場所と、その日の時間帯がありません。"
                    "場所と時刻を入れて、投稿ルールどおりのJSONを出し直してください。"
                    "物語にしない。ですます調。文字数は水増ししない。"
                ),
            )
            data = parse_llm_json(raw)
        except ValueError as exc:
            print(f"  place/time retry skipped: {exc}")

    data["title"] = validate_title(apply_legal_filter(data.get("title", keyword)))
    data["meta_description"] = validate_meta(apply_legal_filter(data.get("meta_description", "")))
    body = apply_legal_filter(data.get("markdown_body", ""))
    body = body.replace("\\n", "\n")

    if "アフィリエイト広告を含みます" not in body[:500]:
        body = _disclaimer_block(keyword, data.get("category", ""), data.get("title", "")) + "\n\n" + body
    body = re.sub(r"^.*アフィリエイトプログラムに参加しています.*\n?", "", body, flags=re.M)
    if "[[SHOP|" not in body:
        body += f"\n\n[[SHOP|{keyword}|この記事で使ったものです。長さや番手を確認してください。]]\n"
    body = ensure_catch_placeholder(body)

    allowed = get_auto_policy().get("allowed_categories") or []
    if allowed and data.get("category") not in allowed:
        data["category"] = allowed[0]

    data["markdown_body"] = body
    data["recap"] = apply_legal_filter(str(data.get("recap") or "")).strip()[:200]
    if not data["recap"]:
        data["recap"] = data["meta_description"][:200]
    data["tags"] = select_tags(keyword, data.get("title", ""), body, data.get("tags"))
    data["slug"] = re.sub(r"[^a-z0-9-]", "", data.get("slug", "").lower())[:80]
    if not data["slug"]:
        data["slug"] = re.sub(r"[^a-z0-9]+", "-", keyword.lower())[:60].strip("-")

    if "[[SHOP|" in body:
        data["affiliate_placements"] = []
    else:
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
        species=next((name for name in data["tags"] if name in {
            item["name"] for item in tag_catalog() if item["group"] == "species"
        }), ""),
        max_body=max(body_images, 1),
    )
    ensure_featured_alt_in_prompts(data, keyword)

    return data


def markdown_to_html(md: str) -> str:
    import markdown as md_lib

    from content.emphasis import apply_emphasis_html, apply_emphasis_markdown
    from content.label_badges import apply_label_badges
    from content.source_links import format_source_section_html

    from content.affiliate_renderer import expand_shop_tokens

    md = expand_shop_tokens(md)
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
