"""記事生成〜WordPress公開（クォータ＋重複ガード付き）。"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import requests

from config_loader import get_wp_credentials, load_json, load_yaml, save_json
from content.affiliate_renderer import inject_affiliates_into_html
from content.generator import build_faq_jsonld, generate_article
from content.trends import fetch_trend_context
from images.generator import process_images
from seo.content_policy import filter_auto_keywords, get_editorial_policy, is_allowed_for_auto
from seo.fingerprint import classify_cluster, find_cannibal_match, intent_fingerprint, quota_allows
from seo.internal_links import build_link_map, pick_internal_links, render_related_section
from seo.ssp_meta import (
    SSP_META_DESCRIPTION,
    SSP_META_TITLE,
    build_ssp_meta,
    ensure_featured_alt_in_prompts,
)
from wordpress.client import WordPressClient


def _media_source_url(client: WordPressClient, media_id: int) -> str:
    base, user, pw = get_wp_credentials()
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    r = requests.get(
        f"{base}/wp-json/wp/v2/media/{media_id}",
        headers={"Authorization": f"Basic {token}"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("source_url", "")


def _select_publishable(
    pending: list[dict],
    published: list[dict],
    queue_items: list[dict],
    count: int,
) -> list[dict]:
    """重複・クォータを満たす pending を最大 count 件選ぶ。"""
    selected: list[dict] = []
    # 選択中の仮カウント用にコピー
    simulated = list(queue_items)

    # 公開選定では done / rewrite_candidate のみ照合（他 pending 同士の誤衝突を避ける）。
    # 同一実行で選んだ分は simulated に done として足すので二重選定も防ぐ。
    queue_for_cannibal = ("done", "rewrite_candidate")

    for item in pending:
        keyword = item.get("keyword", "")
        if not is_allowed_for_auto(keyword):
            continue

        match = find_cannibal_match(
            keyword,
            published,
            queue_items=simulated,
            queue_statuses=queue_for_cannibal,
        )
        if match:
            item["status"] = "rewrite_candidate"
            item["existing_slug"] = match.get("slug") or ""
            item["existing_title"] = match.get("title") or ""
            item["reason"] = match.get("reason") or "cannibal"
            item["noted_at"] = datetime.now(timezone.utc).isoformat()
            print(f"  skip cannibal: {keyword[:50]} -> {item['existing_slug'] or item['existing_title'][:40]}")
            continue

        cluster = item.get("cluster") or classify_cluster(keyword)
        item["cluster"] = cluster
        item.setdefault("fingerprint", sorted(intent_fingerprint(keyword)))

        ok, reason = quota_allows(cluster, simulated, published)
        if not ok:
            print(f"  skip quota ({cluster}): {keyword[:50]} ({reason})")
            continue

        selected.append(item)
        # 仮に done 扱いにして同一実行内の二重枠消費を防ぐ
        simulated.append({
            **item,
            "status": "done",
            "published_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(selected) >= count:
            break

    return selected


def publish_next(count: int = 1, dry_run: bool = False) -> list[dict]:
    queue = load_json("keyword_queue.json")
    published = load_json("published.json")
    site = load_yaml("site.yaml")
    site_url = site["site"]["url"]
    editorial = get_editorial_policy()
    queue_items = list(queue.get("keywords", []))

    pending = [
        k for k in queue_items
        if k.get("status") == "pending" and is_allowed_for_auto(k.get("keyword", ""))
    ]
    pending.sort(key=lambda x: x.get("score", 0), reverse=True)

    selected = _select_publishable(pending, published.get("posts", []), queue_items, count)

    if not selected:
        # cannibal で rewrite_candidate 化した分を保存。
        # 定期実行で「枠なし／穴なし」は正常系なので例外にせず空結果を返す
        # （exit 1 だとキュー更新の auto-commit もスキップされる）。
        queue["keywords"] = filter_auto_keywords(queue_items)
        save_json("keyword_queue.json", queue)
        print(
            "WARN: 公開可能な pending がありません（重複ガードまたは週次クォータ）。"
            "research / seed-from-analytics を実行するか、rewrite_candidate を確認してください。"
        )
        return []

    link_map = build_link_map(published.get("posts", []))
    titles = {p["slug"]: p["title"] for p in published.get("posts", [])}
    results: list[dict] = []
    client = WordPressClient()
    allowed_cats = load_yaml("content_policy.yaml")["auto_publish"]["allowed_categories"]

    for item in selected:
        keyword = item["keyword"]
        print(f"generating (auto): {keyword} [cluster={item.get('cluster')}]")

        # 公開直前の最終ガード（pending 同士は除外・自己照合なし）
        match = find_cannibal_match(
            keyword,
            published.get("posts", []),
            queue_items=queue_items,
            queue_statuses=("done", "rewrite_candidate"),
        )
        if match:
            item["status"] = "rewrite_candidate"
            item["existing_slug"] = match.get("slug") or ""
            item["reason"] = match.get("reason") or "cannibal"
            print(f"  abort cannibal at publish: {keyword}")
            continue

        trend_text = ""
        if editorial.get("trend_research", True):
            try:
                trend = fetch_trend_context(
                    keyword,
                    max_items=editorial.get("max_trend_headlines", 8),
                )
                trend_text = trend["context_text"]
                item["trend_fetched_at"] = trend.get("fetched_at")
                print(f"  Trends: {len(trend.get('headlines', []))} headlines")
            except Exception as e:
                print(f"  Trend fetch warning: {e}")

        internal = pick_internal_links(keyword, link_map, titles)
        article = generate_article(item, internal, trend_context=trend_text)
        ensure_featured_alt_in_prompts(article, keyword)

        if dry_run:
            print("DRY RUN - title:", article["title"])
            results.append({
                "keyword": keyword,
                "dry_run": True,
                "title": article["title"],
                "cluster": item.get("cluster"),
            })
            continue

        images, html = process_images(article, keyword)
        featured_id = None
        body_counter = 0

        for img in images:
            media_id = client.upload_media(img["bytes"], img["filename"], img["alt"])
            if img["role"] == "featured":
                featured_id = media_id
            else:
                body_counter += 1
                src = _media_source_url(client, media_id)
                html = html.replace(f"BODY_IMAGE_{body_counter}", src)

        related = render_related_section(internal, titles)
        faq_ld = build_faq_jsonld(article.get("faq", []), "")
        html = inject_affiliates_into_html(
            html,
            article.get("affiliate_placements"),
            site_url=site_url,
            keyword=keyword,
            fact_heading=editorial.get("fact_section_heading", "いま起きていること（事実）"),
            opinion_heading=editorial.get("opinion_section_heading", "筆者の考察・見解"),
            source_heading=editorial.get("source_section_heading", "参考・関連情報"),
        )
        full_html = html + related + faq_ld

        cat_name = article.get("category") or allowed_cats[0]
        if cat_name not in allowed_cats:
            cat_name = allowed_cats[0]

        cat_id = client.ensure_category(cat_name)
        status = site.get("publish", {}).get("default_status", "publish")
        ssp = build_ssp_meta(article)

        post = client.create_post(
            title=article["title"],
            content=full_html,
            slug=article["slug"],
            category_id=cat_id,
            status=status,
            featured_media=featured_id,
            meta_title=ssp[SSP_META_TITLE],
            meta_description=ssp[SSP_META_DESCRIPTION],
        )

        post_url = post.get("link", "")
        published_at = datetime.now(timezone.utc).isoformat()
        published.setdefault("posts", []).append({
            "id": post["id"],
            "slug": article["slug"],
            "title": article["title"],
            "url": post_url,
            "categories": [cat_name],
            "keywords": [keyword],
            "source": "auto",
            "cluster": item.get("cluster"),
            "published_at": published_at,
        })
        link_map[article["slug"]] = post_url
        titles[article["slug"]] = article["title"]

        item["status"] = "done"
        item["published_at"] = published_at
        item["post_url"] = post_url
        item["cluster"] = item.get("cluster") or classify_cluster(keyword)
        results.append({
            "keyword": keyword,
            "url": post_url,
            "id": post["id"],
            "cluster": item["cluster"],
        })
        print(f"Published: {post_url}")

    queue["keywords"] = filter_auto_keywords(queue_items)
    save_json("published.json", published)
    save_json("keyword_queue.json", queue)
    return results
