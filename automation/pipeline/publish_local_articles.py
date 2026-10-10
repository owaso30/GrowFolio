"""articles/ 以下の Markdown を、固定フレームの画像と購入リンク付きで公開する。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from config_loader import AUTOMATION_ROOT, load_json, save_json
from content.generator import markdown_to_html, tag_catalog
from content.generator import build_faq_jsonld
from images.flux_client import generate_image_bytes
from seo.ssp_meta import SSP_META_DESCRIPTION, SSP_META_TITLE
from wordpress.client import WordPressClient

ARTICLES_DIR = AUTOMATION_ROOT.parent / "articles"
SITE = "https://growfolio-note.com"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("frontmatter がありません")
    end = text.find("\n---", 3)
    if end < 0:
        raise ValueError("frontmatter の終わりがありません")
    meta = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4 :].lstrip("\n")
    return meta, body


def _load_articles() -> list[dict]:
    paths = sorted(ARTICLES_DIR.glob("*/*.md"))
    articles = []
    for path in paths:
        meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        meta["path"] = str(path)
        meta["markdown"] = body
        articles.append(meta)
    return articles


def _validate(articles: list[dict]) -> list[str]:
    errors: list[str] = []
    for art in articles:
        desc = str(art.get("meta_description") or "")
        alt = str(art.get("image_alt") or "")
        if not desc or len(desc) > 120:
            errors.append(f"{art.get('slug')}: meta {len(desc)}字")
        if not alt or len(alt) > 100:
            errors.append(f"{art.get('slug')}: alt {len(alt)}字")
        if "[[SHOP|" not in art["markdown"]:
            errors.append(f"{art.get('slug')}: 購入リンクがありません")
        if not str(art.get("image_prompt") or "").strip():
            errors.append(f"{art.get('slug')}: image_prompt がありません")
    return errors


def _html(art: dict) -> str:
    html = markdown_to_html(art["markdown"])
    faq = []
    for item in art.get("faq") or []:
        faq.append({"question": item.get("q", ""), "answer": item.get("a", "")})
    if faq:
        html += build_faq_jsonld(faq, f"{SITE}/{art['slug']}/")
    return html


def _sync_links(client: WordPressClient, posted: list[dict]) -> None:
    actual = {item["slug"]: item["link"] for item in posted}
    for item in posted:
        content = item["content"]
        updated = content
        for slug, link in actual.items():
            assumed = f"{SITE}/{slug}/"
            if link and link.rstrip("/") != assumed.rstrip("/"):
                updated = updated.replace(assumed, link if link.endswith("/") else link + "/")
        if updated != content:
            client.update_post(item["id"], {"content": updated})
            item["content"] = updated


def publish(dry_run: bool = False) -> list[dict]:
    articles = _load_articles()
    errors = _validate(articles)
    if errors:
        raise SystemExit("\n".join(errors))

    catalog = {item["name"]: item for item in tag_catalog()}
    prepared = []
    for art in articles:
        image_file = str(art.get("image_file") or "").strip()
        if image_file:
            png = Path(image_file).read_bytes()
        else:
            png = generate_image_bytes(
                str(art.get("image_prompt") or art["title"]),
                size="1792x1024",
                role="featured",
            )
        prepared.append({**art, "html": _html(art), "png": png})

    if dry_run:
        preview = AUTOMATION_ROOT / "data" / "preview"
        preview.mkdir(parents=True, exist_ok=True)
        report = []
        for art in prepared:
            (preview / f"{art['slug']}.png").write_bytes(art["png"])
            (preview / f"{art['slug']}.html").write_text(art["html"], encoding="utf-8")
            report.append({
                "slug": art["slug"],
                "meta": len(art["meta_description"]),
                "alt": len(art["image_alt"]),
                "shops": art["html"].count("growfolio-shops"),
                "amazon": art["html"].count("Amazonで価格・在庫を確認"),
                "rakuten": art["html"].count("楽天市場で価格・在庫を確認"),
            })
        (preview / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    client = WordPressClient()
    posted = []
    published = load_json("published.json")
    posts = published.setdefault("posts", [])
    now = datetime.now(timezone.utc).isoformat()

    for art in prepared:
        cat_id = client.ensure_category(art["category"])
        tag_ids = []
        for name in art.get("tags") or []:
            item = catalog.get(name)
            if not item:
                continue
            tag_ids.append(
                client.ensure_tag(
                    item["name"],
                    item.get("slug", ""),
                    "釣種" if item.get("group") == "species" else "道具",
                )
            )
        ext = "jpg" if art["png"][:3] == b"\xff\xd8\xff" else "png"
        media_id = client.upload_media(art["png"], f"{art['slug']}-featured.{ext}", art["image_alt"])
        existing = client.find_post_by_slug(art["slug"])
        fields = {
            "title": art["title"],
            "content": art["html"],
            "slug": art["slug"],
            "status": "publish",
            "categories": [cat_id],
            "tags": tag_ids,
            "featured_media": media_id,
            "excerpt": art["meta_description"],
            "meta": {
                SSP_META_TITLE: art["title"],
                SSP_META_DESCRIPTION: art["meta_description"],
            },
        }
        if existing:
            post = client.update_post(int(existing["id"]), fields)
        else:
            post = client.create_post(
                title=art["title"],
                content=art["html"],
                slug=art["slug"],
                category_id=cat_id,
                tag_ids=tag_ids,
                status="publish",
                featured_media=media_id,
                meta_title=art["title"],
                meta_description=art["meta_description"],
                excerpt=art["meta_description"],
            )
        link = post.get("link") or f"{SITE}/{art['slug']}/"
        posted.append({"id": int(post["id"]), "slug": art["slug"], "link": link, "content": art["html"], "title": art["title"], "tags": art.get("tags") or [], "category": art["category"], "keyword": art.get("keyword", "")})
        print(f"posted {art['slug']} {post.get('id')}")

    _sync_links(client, posted)

    by_slug = {item.get("slug"): item for item in posts}
    for item in posted:
        by_slug[item["slug"]] = {
            "id": item["id"],
            "slug": item["slug"],
            "title": item["title"],
            "url": item["link"],
            "categories": [item["category"]],
            "tags": item["tags"],
            "keywords": [item["keyword"]] if item["keyword"] else [],
            "source": "local",
            "cluster": "rockfish-start",
            "published_at": now,
        }
    published["posts"] = list(by_slug.values())
    published["synced_at"] = now
    save_json("published.json", published)
    result_path = AUTOMATION_ROOT / "data" / "local_publish_result.json"
    result_path.write_text(
        json.dumps([{"slug": p["slug"], "url": p["link"], "id": p["id"]} for p in posted], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return posted


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    publish(dry_run=dry)
