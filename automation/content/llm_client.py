"""記事生成用 LLM クライアント（Anthropic Claude）。"""
from __future__ import annotations

import os

from anthropic import Anthropic

from config_loader import get_anthropic_api_key, load_yaml


def _llm_config() -> dict:
    return load_yaml("models.yaml").get("llm", {})


_JSON_RULES = (
    "【JSON出力ルール】"
    "応答は有効なJSONオブジェクト1つのみ。最初の文字は { で始める。"
    "文字列内の改行は \\n、ダブルクォートは \\\" でエスケープ。"
    "markdown_body も1行のJSON文字列として出力（生の改行を入れない）。"
    "説明文・コードフェンスは付けない。"
)


def complete_json(system: str, user: str, *, repair_hint: str = "") -> str:
    cfg = _llm_config()
    model = os.environ.get("CLAUDE_MODEL", cfg.get("model", "claude-sonnet-4-6"))
    max_tokens = int(os.environ.get("CLAUDE_MAX_TOKENS", cfg.get("max_tokens", 8192)))
    temperature = float(os.environ.get("CLAUDE_TEMPERATURE", cfg.get("temperature", 0.65)))

    prompt = user if not repair_hint else f"{user}\n\n{repair_hint}"
    system_full = f"{system.rstrip()}\n\n{_JSON_RULES}"

    client = Anthropic(api_key=get_anthropic_api_key())
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_full,
        messages=[{"role": "user", "content": prompt}],
    )

    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)
