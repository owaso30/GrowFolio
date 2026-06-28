"""記事本文の重要箇所を SWELL 互換の装飾ブロック・マーカーに変換。"""
from __future__ import annotations

import re

_CAP_COLSET = {
    "要点": "col1",
    "ポイント": "col1",
    "結論": "col1",
    "注意": "col2",
    "リスク": "col3",
    "重要": "col1",
}

_CAP_NAMED = re.compile(
    r"\[\[(要点|ポイント|結論|注意|リスク|重要)\|([^\]]+)\]\]",
    re.DOTALL,
)
_MARK_YELLOW = re.compile(r"==([^=\n]+?)==")
_MARK_BLUE = re.compile(r"\+\+([^+\n]+?)\+\+")


def needs_emphasis(text: str) -> bool:
    """未変換の強調ショートコード（[[...|...]] / == / ++）が残っているか。"""
    if not text:
        return False
    return bool(_CAP_NAMED.search(text) or _MARK_YELLOW.search(text) or _MARK_BLUE.search(text))


def _cap_box(title: str, body: str, colset: str) -> str:
    text = body.strip()
    if not text.startswith("<"):
        text = f"<p>{text}</p>"
    return (
        f'<div class="cap_box" data-colset="{colset}">'
        f'<div class="cap_box_ttl">{title}</div>'
        f'<div class="cap_box_content">{text}</div>'
        f"</div>"
    )


def apply_emphasis_markdown(md: str) -> str:
    """Markdown 段階でショートコード → HTML（SWELL 装飾）。"""

    def cap_repl(match: re.Match[str]) -> str:
        title = match.group(1)
        body = match.group(2).strip()
        colset = _CAP_COLSET.get(title, "col1")
        return _cap_box(title, body, colset)

    text = _CAP_NAMED.sub(cap_repl, md)
    text = _MARK_BLUE.sub(r'<span class="mark_blue">\1</span>', text)
    text = _MARK_YELLOW.sub(r'<span class="mark_yellow">\1</span>', text)
    return text


def apply_emphasis_html(html: str) -> str:
    """HTML 内のショートコード残骸を変換（念のため）。"""
    if not html:
        return html

    def cap_repl(match: re.Match[str]) -> str:
        title = match.group(1)
        body = match.group(2).strip()
        colset = _CAP_COLSET.get(title, "col1")
        return _cap_box(title, body, colset)

    text = _CAP_NAMED.sub(cap_repl, html)
    text = _MARK_BLUE.sub(r'<span class="mark_blue">\1</span>', text)
    text = _MARK_YELLOW.sub(r'<span class="mark_yellow">\1</span>', text)
    return text
