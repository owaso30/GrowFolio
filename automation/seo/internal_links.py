"""内部リンク挿入。"""
from __future__ import annotations

from rapidfuzz import fuzz

from config_loader import load_yaml


def build_link_map(published_posts: list[dict]) -> dict[str, str]:
    return {p["slug"]: p["url"] for p in published_posts if p.get("slug") and p.get("url")}


def pick_internal_links(
    keyword: str,
    link_map: dict[str, str],
    titles: dict[str, str],
    limit: int = 4,
) -> list[tuple[str, str]]:
    cfg = load_yaml("internal_links.yaml")
    slugs: list[str] = list(cfg.get("default_links", []))

    scored: list[tuple[int, str]] = []
    for slug in link_map:
        title = titles.get(slug, slug.replace("-", " "))
        score = fuzz.partial_ratio(keyword, title)
        scored.append((score, slug))
    scored.sort(reverse=True)

    for _, slug in scored:
        if slug not in slugs:
            slugs.append(slug)

    links: list[tuple[str, str]] = []
    for slug in slugs:
        url = link_map.get(slug)
        if url:
            links.append((slug, url))
        if len(links) >= limit:
            break
    return links


def render_related_section(links: list[tuple[str, str]], titles: dict[str, str]) -> str:
    if not links:
        return ""
    items = []
    for slug, url in links:
        label = titles.get(slug, slug.replace("-", " "))
        items.append(f'<li><a href="{url}">{label}</a></li>')
    return (
        "<h2>あわせて読みたい</h2>"
        "<ul>" + "".join(items) + "</ul>"
    )
