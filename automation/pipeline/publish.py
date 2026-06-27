"""記事生成〜WordPress公開。"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import requests

from config_loader import get_wp_credentials, load_json, load_yaml, save_json
from content.affiliate_renderer import render_affiliate_blocks
from content.generator import build_faq_jsonld, generate_article
from content.trends import fetch_trend_context
from images.generator import process_images
from seo.content_policy import filter_auto_keywords, get_editorial_policy, is_allowed_for_auto
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


def publish_next(count: int = 1, dry_run: bool = False) -> list[dict]:
    queue = load_json("keyword_queue.json")
    published = load_json("published.json")
    site = load_yaml("site.yaml")
    site_url = site["site"]["url"]
    editorial = get_editorial_policy()

    pending = [
        k for k in queue.get("keywords", [])
        if k.get("status") == "pending" and is_allowed_for_auto(k.get("keyword", ""))
    ]
    pending.sort(key=lambda x: x.get("score", 0), reverse=True)

    if not pending:
        raise RuntimeError(
            "自動投稿対象の pending キーワードがありません。"
            "research を実行するか keyword_queue.json を確認してください。"
        )

    link_map = build_link_map(published.get("posts", []))
    titles = {p["slug"]: p["title"] for p in published.get("posts", [])}
    results: list[dict] = []
    client = WordPressClient()
    allowed_cats = load_yaml("content_policy.yaml")["auto_publish"]["allowed_categories"]

    for item in pending[:count]:
        keyword = item["keyword"]
        print(f"Generating (auto): {keyword}")

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
            results.append({"keyword": keyword, "dry_run": True, "title": article["title"]})
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
        affiliate = render_affiliate_blocks(
            article.get("affiliate_placements"),
            site_url=site_url,
            keyword=keyword,
        )
        full_html = html + affiliate + related + faq_ld

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
        published.setdefault("posts", []).append({
            "id": post["id"],
            "slug": article["slug"],
            "title": article["title"],
            "url": post_url,
            "categories": [cat_name],
            "keywords": [keyword],
            "source": "auto",
        })
        link_map[article["slug"]] = post_url
        titles[article["slug"]] = article["title"]

        item["status"] = "done"
        item["published_at"] = datetime.now(timezone.utc).isoformat()
        item["post_url"] = post_url
        results.append({"keyword": keyword, "url": post_url, "id": post["id"]})
        print(f"Published: {post_url}")

    queue["keywords"] = filter_auto_keywords(queue.get("keywords", []))
    save_json("published.json", published)
    save_json("keyword_queue.json", queue)
    return results
