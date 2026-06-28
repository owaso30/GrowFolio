"""参考・関連情報セクションのリンク整形（URL非表示・文字リンク化）。"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from seo.content_policy import get_editorial_policy

_URL_RE = re.compile(r"https?://[^\s<\"（]+")
_PAREN_COLON_RE = re.compile(r"（([^）]*?):([^）]*?)）")

# 参考行に URL が無い場合の既知ソース（部分一致 → 公式URL）
SOURCE_URL_HINTS: list[tuple[str, str]] = [
    (
        "gihyo.jp「github.comでCopilot",
        "https://gihyo.jp/article/2026/06/mastering-copilot-on-github",
    ),
    (
        "AIsmiley「GitHub Copilotとは",
        "https://aismiley.co.jp/ai_news/github-copilot-ai-tool/",
    ),
    (
        "エクサウィザーズ「Claude Codeとは",
        "https://exawizards.com/column/article/ai/claude-code/",
    ),
    (
        "NTTドコモビジネス「【2026年最新版】Microsoft 365 Copilot",
        "https://www.ntt.com/bizon/copilot.html",
    ),
]


def _clean_paren_colons(text: str) -> str:
    while True:
        new = _PAREN_COLON_RE.sub(lambda m: f"（{m.group(1).strip()} {m.group(2).strip()}）", text)
        if new == text:
            return text
        text = new


def _strip_trailing_colon(text: str) -> str:
    return re.sub(r":\s*$", "", text.strip())


def _has_bare_url(text: str) -> bool:
    """href 属性以外に裸URLが残っているか。"""
    without_href = re.sub(r'href="[^"]*"', "", text)
    return bool(_URL_RE.search(without_href))


def _linkify_plain_text(text: str) -> str:
    """裸URLを直前テキストの文字リンクへ。コロン区切りを除去。"""
    text = text.strip()
    if not text:
        return text

    if "<a " in text and not _has_bare_url(text):
        text = re.sub(r":\s*(?=<a\s)", " ", text)
        text = re.sub(r"^([^<:]+):\s*", r"\1 ", text)
        return _clean_paren_colons(text)

    match = _URL_RE.search(text)
    if not match:
        return _clean_paren_colons(re.sub(r":\s+", " ", text, count=1))

    url = match.group(0).rstrip(".,)")
    before = _strip_trailing_colon(text[: match.start()])
    after = _clean_paren_colons(text[match.end() :].strip())

    if not before:
        before = url

    link = (
        f'<a href="{url}" rel="noopener noreferrer" target="_blank">{before}</a>'
    )
    return f"{link}{after}"


def _linkify_text_only_source(text: str) -> str:
    """URL なし参考行を既知ソース URL で文字リンク化。"""
    text = text.strip()
    if not text or "<a " in text or _has_bare_url(text):
        return text
    for hint, url in SOURCE_URL_HINTS:
        if hint in text:
            return (
                f'<a href="{url}" rel="noopener noreferrer" target="_blank">{text}</a>'
            )
    return _clean_paren_colons(text)


def _linkify_list_item(li: Tag) -> None:
    inner = li.decode_contents().strip()

    if _has_bare_url(inner):
        merged = _linkify_plain_text(li.get_text())
    elif "<a " in inner:
        merged = _linkify_plain_text(inner)
    else:
        merged = _linkify_text_only_source(inner)

    li.clear()
    li.append(BeautifulSoup(merged, "html.parser"))


def format_source_section_html(html: str, heading: str | None = None) -> str:
    """「参考・関連情報」の ul 内を文字リンク化し、裸URLと「:」区切りを除去。"""
    if not html:
        return html

    cfg = get_editorial_policy()
    source_h = heading or cfg.get("source_section_heading", "参考・関連情報")
    if source_h not in html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    target_h2 = None
    for h2 in soup.find_all("h2"):
        if source_h in h2.get_text(strip=True):
            target_h2 = h2
            break
    if not target_h2:
        return html

    ul = target_h2.find_next_sibling("ul")
    if not ul:
        return html

    for li in ul.find_all("li", recursive=False):
        _linkify_list_item(li)

    return str(soup)


def needs_source_link_format(html: str, heading: str | None = None) -> bool:
    if not html:
        return False
    cfg = get_editorial_policy()
    source_h = heading or cfg.get("source_section_heading", "参考・関連情報")
    if source_h not in html:
        return False
    idx = html.find(source_h)
    section = html[idx : idx + 4000]
    if "href=\"&lt;/a&gt;\"" in section or "関連記事:" in section:
        return True
    without_href = re.sub(r'href="[^"]*"', "", section)
    if _URL_RE.search(without_href):
        return True
    for hint, url in SOURCE_URL_HINTS:
        if hint in section and url not in section:
            return True
    return ": <a " in section or re.search(r"[^/]: https?://", section) is not None
