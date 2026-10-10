"""Flux 画像生成（fal.ai）。"""
from __future__ import annotations

import os

import requests

from config_loader import get_fal_api_key, load_yaml

FAL_RUN_URL = "https://fal.run/{model_id}"


def _image_config() -> dict:
    return load_yaml("models.yaml").get("images", {})


def _parse_size(size: str) -> dict[str, int]:
    if "x" in size.lower():
        w, h = size.lower().split("x", 1)
        return {"width": int(w), "height": int(h)}
    return {"width": 1024, "height": 1024}


def _enhance_prompt(prompt: str, role: str = "featured") -> str:
    cfg = _image_config()
    if role == "catch":
        suffix = cfg.get(
            "catch_prompt_suffix",
            ". Documentary horizontal photo. The fish is the subject, sharp, in the lower-left, "
            "just landed on wet tetrapod at a Japanese harbor in the evening. "
            "No people, no hands, no text, no logos, no packaging, no lure.",
        )
    elif role == "shop":
        suffix = cfg.get(
            "shop_prompt_suffix",
            ". Clean product photograph on a plain light gray background. One fishing product only, "
            "centered and sharp. No harbor, no fish, no people, no text, no watermark.",
        )
    else:
        suffix = cfg.get(
            "prompt_suffix",
            ". Minimal editorial photography or clean flat design. Soft natural lighting, neutral background. "
            "No text, no numbers, no UI screenshots, no fake logos, no 3D render, no neon glow, no glossy AI art.",
        )
    return prompt.rstrip(".") + suffix


def generate_image_bytes(prompt: str, size: str = "1792x1024", *, role: str = "featured") -> bytes:
    cfg = _image_config()
    if role == "body":
        model = os.environ.get("FLUX_BODY_MODEL", cfg.get("body_model", "fal-ai/flux/dev"))
    else:
        model = os.environ.get("FLUX_FEATURED_MODEL", cfg.get("featured_model", "fal-ai/flux/dev"))

    url = FAL_RUN_URL.format(model_id=model)
    payload = {
        "prompt": _enhance_prompt(prompt, role),
        "image_size": _parse_size(size),
        "num_images": 1,
        "enable_safety_checker": True,
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Key {get_fal_api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    images = data.get("images") or []
    if not images or not images[0].get("url"):
        raise RuntimeError(f"Flux 画像URLが取得できませんでした: {data}")

    img_response = requests.get(images[0]["url"], timeout=120)
    img_response.raise_for_status()
    return img_response.content
