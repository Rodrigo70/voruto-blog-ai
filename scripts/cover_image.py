"""
Capa da marca VORUTO para os posts do Insights (30/10/2026).

1200×630 (padrão de compartilhamento): fundo escuro do blog, grade roxa sutil, brilhos,
logo, selo da categoria, título e até 3 cartas reais citadas no artigo (em leque).
Sem cartas → mascote VORUTO no lugar.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
INK = (15, 23, 42)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
GRAD = [(124, 58, 237), (236, 72, 153), (59, 130, 246)]
CAT_COLORS = {
    "lancamentos-tcg": (124, 58, 237), "leiloes-mercado": (236, 72, 153), "collabs-cultura": (59, 130, 246),
    "guia-colecionador": (16, 185, 129), "curiosidades-raridades": (245, 158, 11), "mercado-global": (6, 182, 212),
}

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT = ASSETS / "PlusJakartaSans.ttf"


def _font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def _glow(img: Image.Image, center, radius: int, color, alpha: int) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    img.alpha_composite(layer)


def _gradient_bar(w: int, h: int) -> Image.Image:
    bar = Image.new("RGBA", (w, h))
    px = bar.load()
    for x in range(w):
        t = x / max(1, w - 1) * (len(GRAD) - 1)
        i = min(int(t), len(GRAD) - 2)
        f = t - i
        c = tuple(int(GRAD[i][k] + (GRAD[i + 1][k] - GRAD[i][k]) * f) for k in range(3))
        for y in range(h):
            px[x, y] = c + (255,)
    return bar


def _wrap(text: str, font, max_w: int, draw) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_title(title: str, draw, max_w: int, max_h: int):
    for size in range(60, 33, -2):
        f = _font(size, 800)
        lines = _wrap(title, f, max_w, draw)
        lh = int(size * 1.14)
        if len(lines) * lh <= max_h:
            return f, lines, lh
    f = _font(34, 800)
    lines = _wrap(title, f, max_w, draw)
    lh = int(34 * 1.14)
    keep = max_h // lh
    if len(lines) > keep:
        lines = lines[:keep]
        lines[-1] = lines[-1].rstrip(" ,.:;") + "…"
    return f, lines, lh


def _rounded(im: Image.Image, r: int) -> Image.Image:
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], r, fill=255)
    im.putalpha(mask)
    return im


def _download(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 VORUTO-Insights"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        print(f"[Capa] imagem indisponível ({url[:60]}…): {e}")
        return None


def _place_card(canvas: Image.Image, card: Image.Image, cx: int, cy: int, h: int, angle: float) -> None:
    w = int(card.size[0] * h / card.size[1])
    c = _rounded(card.resize((w, h), Image.LANCZOS), max(8, h // 28))
    rot = c.rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.getchannel("A").point(lambda a: int(a * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    x, y = cx - rot.size[0] // 2, cy - rot.size[1] // 2
    canvas.alpha_composite(shadow, (x + 10, y + 22))
    canvas.alpha_composite(rot, (x, y))


def make_cover(title: str, category: str, category_slug: str, card_image_urls: list[str]) -> bytes:
    img = Image.new("RGBA", (W, H), INK + (255,))
    d = ImageDraw.Draw(img)

    # grade sutil + brilhos (mesma linguagem do hero do blog)
    for x in range(0, W, 48):
        d.line([(x, 0), (x, H)], fill=(124, 58, 237, 22))
    for y in range(0, H, 48):
        d.line([(0, y), (W, y)], fill=(124, 58, 237, 22))
    _glow(img, (980, 120), 360, (124, 58, 237), 90)
    _glow(img, (120, 640), 300, (236, 72, 153), 55)
    _glow(img, (1150, 600), 260, (59, 130, 246), 60)

    # cartas (direita)
    cards = [c for c in (_download(u) for u in card_image_urls[:3]) if c is not None]
    right_cx, right_cy = 912, 330
    if len(cards) >= 3:
        _place_card(img, cards[1], right_cx - 118, right_cy + 18, 380, 10)
        _place_card(img, cards[2], right_cx + 118, right_cy + 18, 380, -10)
        _place_card(img, cards[0], right_cx, right_cy, 440, 0)
    elif len(cards) == 2:
        _place_card(img, cards[1], right_cx + 85, right_cy + 12, 410, -8)
        _place_card(img, cards[0], right_cx - 75, right_cy, 440, 6)
    elif len(cards) == 1:
        _place_card(img, cards[0], right_cx, right_cy, 470, -5)
    else:
        mascot = Image.open(ASSETS / "voruto_standing_vortex.png").convert("RGBA").resize((480, 480), Image.LANCZOS)
        img.alpha_composite(mascot, (right_cx - 240, right_cy - 230))

    # véu à esquerda para o texto respirar sobre cartas largas
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vp = veil.load()
    for x in range(0, 760):
        a = 235 if x < 640 else int(235 * (760 - x) / 120)
        for y in range(H):
            vp[x, y] = INK + (a,)
    img.alpha_composite(veil.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img)

    # logo
    logo = Image.open(ASSETS / "voruto_logo_white.png").convert("RGBA")
    logo = logo.crop(logo.getbbox())
    lh = 62
    logo = logo.resize((int(logo.size[0] * lh / logo.size[1]), lh), Image.LANCZOS)
    img.alpha_composite(logo, (64, 52))

    # selo da categoria
    cat_rgb = CAT_COLORS.get(category_slug, GRAD[0])
    pill_font = _font(17, 700)
    label = f"INSIGHTS · {category.upper()}" if category else "INSIGHTS VORUTO"
    tw = int(d.textlength(label, font=pill_font))
    px, py = 64, 150
    d.rounded_rectangle([px, py, px + tw + 32, py + 36], 18, fill=cat_rgb + (46,), outline=cat_rgb + (150,), width=2)
    d.text((px + 16, py + 7), label, font=pill_font, fill=tuple(min(255, c + 110) for c in cat_rgb))

    # título
    tf, lines, lhgt = _fit_title(title, d, 600, 300)
    ty = 210
    for ln in lines:
        d.text((64, ty), ln, font=tf, fill=WHITE)
        ty += lhgt

    # barra degradê + rodapé
    img.alpha_composite(_gradient_bar(140, 6), (64, min(ty + 18, 540)))
    d.text((64, 568), "voruto.com.br", font=_font(20, 600), fill=MUTED)

    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue()


