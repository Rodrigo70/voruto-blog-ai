"""
Imagens dos posts do Insights (30/10/2026):
  • cartas citadas no artigo → busca no catálogo do VORUTO (imagem + link da página da carta)
  • figuras dentro do texto no lugar dos marcadores [[CARD:n]]
  • capa da marca (cover_image.make_cover) com as cartas encontradas
"""
from __future__ import annotations

import html
import os
import re

import requests

from cover_image import make_cover

WP_URL = os.environ.get("WP_URL", "https://voruto.com.br")
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 VORUTO-Insights"
_MARKER = re.compile(r"\[\[CARD:(\d+)\]\]")


def lookup_card(card: dict) -> dict | None:
    name = (card.get("name") or "").strip()
    if len(name) < 2:
        return None
    try:
        r = requests.get(
            f"{WP_URL}/wp-json/voruto/v1/blog-cards",
            params={"name": name, "set": card.get("set") or "", "number": str(card.get("number") or "")},
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[Cartas] Falha ao buscar '{name}': {e}")
        return None
    if not data.get("found"):
        print(f"[Cartas] '{name}' ({card.get('set') or '-'} {card.get('number') or ''}) não está no catálogo.")
        return None
    print(f"[Cartas] {data['name']} · {data['set']} · {data['number']} → {data['url']}")
    return data


def _brl(v: float) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def figure_html(c: dict, rate: dict | None) -> str:
    name, set_, num = html.escape(c["name"]), html.escape(c.get("set") or ""), html.escape(c.get("number") or "")
    url, img = html.escape(c["url"]), html.escape(c["image"])
    meta = " · ".join(x for x in (set_, num) if x)
    price = ""
    if c.get("price_usd"):
        usd = float(c["price_usd"])
        brl = f" (≈ R$ {_brl(usd * rate['bid']).split(',')[0]})" if rate and rate.get("bid") else ""
        price = f'<span class="vb-tcg-price">Referência TCGplayer, sem gradação: US$ {_brl(usd)}{brl}</span>'
    return (
        f'<figure class="vb-tcg-card"><a href="{url}">'
        f'<img src="{img}" alt="{name} — {meta}" loading="lazy" width="250" height="349"></a>'
        f"<figcaption><strong>{name}</strong>{meta}{price}"
        f'<a href="{url}">Ver carta e preços no VORUTO →</a></figcaption></figure>'
    )


def resolve_cards(article: dict, rate: dict | None) -> list[dict]:
    """Troca [[CARD:n]] pelas figuras das cartas encontradas (ou remove) e devolve as encontradas."""
    wanted = article.get("cards") or []
    found: dict[int, dict] = {}
    seen_ids: set[str] = set()
    for i, card in enumerate(wanted[:4], start=1):
        c = lookup_card(card if isinstance(card, dict) else {"name": str(card)})
        if c and c["card_id"] not in seen_ids:
            found[i] = c
            seen_ids.add(c["card_id"])

    used: set[int] = set()

    def _sub(m: re.Match) -> str:
        n = int(m.group(1))
        if n in found and n not in used:
            used.add(n)
            return figure_html(found[n], rate)
        return ""

    content = article.get("content_html", "")
    content = re.sub(r"<p>\s*(\[\[CARD:\d+\]\])\s*</p>", r"\1", content)  # marcador sozinho num <p>
    article["content_html"] = _MARKER.sub(_sub, content)
    return [found[i] for i in sorted(found)]


def build_cover(title: str, category: str, category_slug: str, cards: list[dict]) -> bytes:
    return make_cover(title, category, category_slug, [c["image"] for c in cards[:3]])
