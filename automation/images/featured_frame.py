"""アイキャッチの固定フレーム。外枠は共通で、中央の図だけ記事ごとに変える。"""
from __future__ import annotations

import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

W, H = 1792, 1024
RAIL = 18
BG = (16, 22, 32)
RAIL_COLOR = (198, 163, 106)
CREAM = (247, 241, 230)
INK = (20, 28, 40)

def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\YuGothB.ttc" if bold else r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\meiryob.ttc" if bold else r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _gradient(image: Image.Image, box: tuple[int, int, int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(image)
    height = max(1, y1 - y0)
    for i in range(height):
        t = i / height
        color = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=color)


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _draw_scene(canvas: Image.Image, box: tuple[int, int, int, int], scene: str) -> None:
    palettes = {
        "kit": ((28, 48, 72), (18, 32, 48)),
        "trouble": ((72, 48, 36), (36, 28, 28)),
        "buy": ((42, 58, 46), (24, 36, 32)),
        "snag": ((16, 48, 58), (10, 28, 40)),
        "bag": ((64, 52, 38), (36, 32, 28)),
        "worm": ((20, 46, 40), (12, 28, 32)),
        "wash": ((48, 62, 72), (28, 40, 52)),
        "review": ((32, 42, 58), (20, 28, 40)),
    }
    top, bottom = palettes.get(scene, ((28, 42, 58), (16, 24, 36)))
    _gradient(canvas, box, top, bottom)
    draw = ImageDraw.Draw(canvas)
    painters = {
        "kit": _scene_kit,
        "trouble": _scene_trouble,
        "buy": _scene_buy,
        "snag": _scene_snag,
        "bag": _scene_bag,
        "worm": _scene_worm,
        "wash": _scene_wash,
        "review": _scene_review,
    }
    painters.get(scene, _scene_kit)(draw, box)


def _scene_kit(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    for i, color in enumerate(((40, 52, 64), (32, 44, 56), (24, 36, 48))):
        draw.ellipse((x0 + 80 + i * 220, y1 - 220, x0 + 420 + i * 220, y1 - 40), fill=color)
    draw.line((x0 + 180, y1 - 160, x1 - 220, y0 + 80), fill=(232, 224, 208), width=8)
    draw.ellipse((x0 + 150, y1 - 190, x0 + 230, y1 - 110), fill=(198, 163, 106), outline=(247, 241, 230), width=4)
    draw.rounded_rectangle((x0 + 260, y1 - 250, x0 + 430, y1 - 170), radius=10, fill=(232, 220, 196))
    draw.rounded_rectangle((x0 + 460, y1 - 230, x0 + 600, y1 - 160), radius=10, fill=(90, 122, 110))


def _scene_trouble(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = x0 + 520, (y0 + y1) // 2 - 10
    draw.ellipse((cx - 120, cy - 120, cx + 120, cy + 120), outline=(232, 224, 208), width=10)
    draw.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), fill=(198, 163, 106))
    draw.arc((cx + 150, cy - 80, cx + 430, cy + 160), 200, 40, fill=(232, 196, 150), width=8)
    draw.arc((cx + 180, cy - 20, cx + 400, cy + 180), 210, 20, fill=(232, 196, 150), width=8)
    draw.rounded_rectangle((x1 - 420, y0 + 80, x1 - 180, y0 + 210), radius=16, outline=(214, 122, 74), width=6)


def _scene_buy(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    mid_y = y0 + 250
    draw.rounded_rectangle((x0 + 140, mid_y, x0 + 390, mid_y + 180), radius=18, fill=(232, 224, 208))
    draw.ellipse((x0 + 210, mid_y + 30, x0 + 320, mid_y + 140), outline=(90, 110, 96), width=8)
    draw.line((x0 + 560, mid_y + 20, x0 + 700, mid_y + 170), fill=(232, 224, 208), width=6)
    draw.polygon([(x0 + 690, mid_y + 150), (x0 + 760, mid_y + 190), (x0 + 670, mid_y + 200)], fill=(198, 163, 106))
    draw.ellipse((x0 + 980, mid_y + 40, x0 + 1120, mid_y + 180), fill=(198, 163, 106))
    draw.ellipse((x0 + 1030, mid_y + 90, x0 + 1070, mid_y + 130), fill=(20, 28, 40))
    draw.line((x0 + 200, y0 + 120, x1 - 240, y0 + 70), fill=(70, 86, 74), width=10)


def _scene_snag(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.ellipse((x0 + 80, y1 - 280, x0 + 520, y1 - 40), fill=(28, 52, 58))
    draw.ellipse((x0 + 360, y1 - 240, x0 + 860, y1 - 20), fill=(18, 40, 48))
    draw.ellipse((x0 + 700, y1 - 300, x0 + 1280, y1 - 60), fill=(24, 48, 56))
    hx, hy = x0 + 620, y1 - 250
    draw.line((hx, hy - 80, hx, hy + 30), fill=(232, 224, 208), width=4)
    draw.ellipse((hx - 16, hy + 20, hx + 16, hy + 52), fill=(198, 163, 106))
    draw.arc((hx - 28, hy + 36, hx + 36, hy + 96), 20, 220, fill=(232, 224, 208), width=4)
    draw.ellipse((x0 + 1040, y0 + 120, x0 + 1090, y0 + 170), fill=(198, 163, 106))
    draw.line((x0 + 1065, y0 + 80, x0 + 1065, y0 + 130), fill=(232, 224, 208), width=3)


def _scene_bag(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 180, y0 + 150, x0 + 980, y1 - 120), radius=28, fill=(92, 74, 52), outline=(232, 220, 196), width=6)
    draw.arc((x0 + 360, y0 + 70, x0 + 800, y0 + 230), 200, 340, fill=(232, 220, 196), width=8)
    draw.rounded_rectangle((x0 + 280, y0 + 240, x0 + 460, y0 + 340), radius=10, fill=(232, 224, 208))
    draw.ellipse((x0 + 520, y0 + 250, x0 + 640, y0 + 370), fill=(198, 163, 106))
    draw.line((x0 + 1120, y0 + 180, x0 + 1360, y0 + 420), fill=(214, 122, 74), width=8)
    draw.line((x0 + 1360, y0 + 180, x0 + 1120, y0 + 420), fill=(214, 122, 74), width=8)


def _scene_worm(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cy = y0 + 280
    draw.rounded_rectangle((x0 + 140, cy, x0 + 460, cy + 36), radius=18, fill=(232, 196, 186))
    draw.arc((x0 + 620, cy - 40, x0 + 860, cy + 80), 0, 180, fill=(196, 214, 120), width=16)
    draw.line((x0 + 640, cy + 20, x0 + 820, cy + 20), fill=(196, 214, 120), width=16)
    draw.ellipse((x0 + 1080, cy - 20, x0 + 1280, cy + 70), fill=(120, 168, 140))
    draw.ellipse((x0 + 1240, cy + 10, x0 + 1380, cy + 90), fill=(90, 140, 120))


def _scene_wash(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.ellipse((x0 + 160, y0 + 180, x0 + 760, y1 - 140), outline=(232, 236, 240), width=8)
    draw.ellipse((x0 + 860, y0 + 220, x0 + 1040, y0 + 400), outline=(232, 224, 208), width=10)
    draw.ellipse((x0 + 910, y0 + 270, x0 + 990, y0 + 350), fill=(198, 163, 106))
    draw.rounded_rectangle((x0 + 1080, y1 - 280, x0 + 1520, y1 - 150), radius=12, fill=(226, 220, 206))
    for i in range(4):
        draw.ellipse((x0 + 300 + i * 40, y0 + 120, x0 + 318 + i * 40, y0 + 150), fill=(200, 220, 230))


def _scene_review(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    labels = ("使いやすさ", "準備時間", "耐久性", "収納性")
    gap = 24
    width = (x1 - x0 - gap * 5) // 4
    top = y0 + 150
    bottom = y1 - 120
    font = _font(36, bold=True)
    for i, label in enumerate(labels):
        left = x0 + gap + i * (width + gap)
        draw.rounded_rectangle((left, top, left + width, bottom), radius=18, fill=(24, 36, 52), outline=RAIL_COLOR, width=3)
        tw = font.getlength(label)
        draw.text((left + (width - tw) / 2, (top + bottom) / 2 - 20), label, font=font, fill=CREAM)


def _paste_round(base: Image.Image, panel: Image.Image, box: tuple[int, int, int, int], radius: int) -> None:
    x0, y0, x1, y1 = box
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), radius=radius, fill=255)
    base.paste(panel, (x0, y0), mask)


def compose_featured(
    *,
    title: str,
    category: str,
    tags: list[str] | None = None,
    scene: str = "kit",
    inner: Image.Image | None = None,
    caption: str = "",
) -> bytes:
    """共通レイアウト。色と枠だけを残し、文字は載せない。中央は渡した写真。"""
    del title, category, tags, caption
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, RAIL, H), fill=RAIL_COLOR)

    ix0, iy0, ix1, iy1 = 48, 36, 1756, 988
    panel = Image.new("RGB", (ix1 - ix0, iy1 - iy0), BG)
    if inner is not None:
        panel = _cover(inner, ix1 - ix0, iy1 - iy0)
    else:
        _draw_scene(panel, (0, 0, panel.width, panel.height), scene)
    _paste_round(canvas, panel, (ix0, iy0, ix1, iy1), 28)
    draw.rounded_rectangle((ix0, iy0, ix1, iy1), radius=28, outline=RAIL_COLOR, width=3)

    buf = BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def compose_featured_bytes(
    *,
    title: str,
    category: str,
    tags: list[str] | None = None,
    scene: str = "",
    caption: str = "",
    inner_bytes: bytes | None = None,
) -> bytes:
    inner = None
    if inner_bytes:
        inner = Image.open(BytesIO(inner_bytes))
    return compose_featured(
        title=title,
        category=category,
        tags=tags,
        scene=scene or "kit",
        inner=inner,
        caption=caption,
    )
