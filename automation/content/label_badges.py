"""【事実】【考察】ラベルをバッジHTMLに変換。"""
from __future__ import annotations

import re

from seo.content_policy import get_editorial_policy

_BADGE_RE = re.compile(
    r'<span class="growfolio-label growfolio-label--(fact|opinion)" style="[^"]*">'
    r'(?:<span style="[^"]*">(事実|考察)</span>|(事実|考察))'
    r"</span>"
)


def _badge_kind_from_match(m: re.Match[str]) -> str:
    return m.group(1)


def _badge_text_from_match(m: re.Match[str]) -> str:
    return m.group(2) or m.group(3) or ""


def _badge_html(text: str, *, kind: str) -> str:
    styles = {
        "fact": {
            "color": "#1e40af",
            "bg": "#dbeafe",
            "border": "#93c5fd",
        },
        "opinion": {
            "color": "#9a3412",
            "bg": "#ffedd5",
            "border": "#fdba74",
        },
    }
    style = styles.get(kind, styles["fact"])
    # inline-flex + min-height だと行ボックスが膨らみ baseline から大きく下にずれるため inline-block で行高に合わせる
    return (
        f'<span class="growfolio-label growfolio-label--{kind}" '
        f'style="display:inline-block;box-sizing:border-box;'
        f"padding:.1em .6em;margin-right:.45em;"
        f"font-size:.75em;font-weight:700;letter-spacing:.04em;line-height:1.2;"
        f"vertical-align:middle;transform:translateY(-.06em);"
        f"color:{style['color']};background:{style['bg']};"
        f"border:1px solid {style['border']};border-radius:999px;"
        f'">{text}</span>'
    )


def apply_label_badges(html: str, editorial: dict | None = None) -> str:
    """Markdown→HTML 後の本文で 【事実】【考察】 をバッジに置換。"""
    if not html:
        return html

    cfg = editorial or get_editorial_policy()
    fact_marker = cfg.get("fact_label", "【事実】")
    opinion_marker = cfg.get("opinion_label", "【考察】")
    fact_text = cfg.get("fact_badge_text", "事実")
    opinion_text = cfg.get("opinion_badge_text", "考察")

    html = html.replace(fact_marker, _badge_html(fact_text, kind="fact"))
    html = html.replace(opinion_marker, _badge_html(opinion_text, kind="opinion"))
    return html


def refresh_label_badge_styles(html: str) -> str:
    """既存HTML内の growfolio-label バッジを最新スタイルへ差し替え。"""
    if not html or "growfolio-label--" not in html:
        return html
    return _BADGE_RE.sub(
        lambda m: _badge_html(_badge_text_from_match(m), kind=_badge_kind_from_match(m)),
        html,
    )


def needs_label_badge_refresh(html: str) -> bool:
    if not html or "growfolio-label--" not in html:
        return False
    return (
        "translateY(-.06em)" not in html
        or "min-height:2em" in html
        or "inline-flex" in html
    )


def needs_label_badges(html: str, editorial: dict | None = None) -> bool:
    """【事実】/【考察】 が残っているか（未バッジ化）。"""
    if not html:
        return False
    cfg = editorial or get_editorial_policy()
    fact_marker = cfg.get("fact_label", "【事実】")
    opinion_marker = cfg.get("opinion_label", "【考察】")
    return fact_marker in html or opinion_marker in html


_OPINION_BADGE_IN_H3 = re.compile(
    r'(<h3>)<span class="growfolio-label growfolio-label--opinion" style="[^"]*">考察</span>'
    r"(.*?)</h3>(\s*<p>)",
    re.DOTALL,
)


def move_opinion_badges_from_headings(html: str) -> str:
    """H3 見出し内の考察バッジを直後の段落先頭へ移動。"""
    if not html or "growfolio-label--opinion" not in html:
        return html
    badge = _badge_html("考察", kind="opinion")

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{m.group(2)}</h3>{m.group(3)}{badge}"

    return _OPINION_BADGE_IN_H3.sub(repl, html)
