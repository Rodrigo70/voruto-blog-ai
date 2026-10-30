#!/usr/bin/env python3
"""
Capas para os posts antigos do Insights (30/10/2026).

Para cada post publicado sem imagem de capa: o Claude lê o texto e aponta até 3 cartas citadas,
o motor busca as imagens no catálogo do VORUTO, gera a capa da marca e a define no post.
Não altera o texto dos posts. Rodar pelo workflow (modo "capas-antigas").
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import anthropic
import requests

sys.path.insert(0, str(Path(__file__).parent))

import blog_media
import wordpress_client as wp

_ROOT = Path(__file__).parent.parent
_TOPICS = json.loads((_ROOT / "topics" / "rotation.json").read_text())["categories"]
_SLUG_BY_CAT = {t["wp_category"].lower(): t["slug"] for t in _TOPICS}
MODEL = "claude-opus-4-8"


def _posts_without_cover() -> list[dict]:
    out, page = [], 1
    while True:
        r = requests.get(f"{wp.WP_URL}/wp-json/wp/v2/posts", headers=wp._auth_headers(),
                         params={"per_page": 50, "page": page, "status": "publish",
                                 "_fields": "id,title,content,categories,featured_media,slug"}, timeout=30)
        if r.status_code == 400:
            break
        r.raise_for_status()
        items = r.json()
        out.extend(p for p in items if not p.get("featured_media"))
        if len(items) < 50:
            break
        page += 1
    return out


def _category(cat_ids: list[int]) -> tuple[str, str]:
    for cid in cat_ids or []:
        r = requests.get(f"{wp.WP_URL}/wp-json/wp/v2/categories/{cid}", headers=wp._auth_headers(), timeout=15)
        if r.ok:
            name = html.unescape(r.json().get("name", ""))
            if name.lower() != "uncategorized" and name.lower() != "sem categoria":
                return name, _SLUG_BY_CAT.get(name.lower(), "")
    return "", ""


def _cards_from_text(client: anthropic.Anthropic, title: str, text: str) -> list[dict]:
    msg = client.messages.create(
        model=MODEL, max_tokens=500,
        messages=[{"role": "user", "content": (
            "Do artigo abaixo, liste até 3 cartas de TCG reais e específicas que ele discute com destaque, "
            "a principal primeiro. Use o nome oficial em inglês como impresso na carta, a coleção em inglês e o "
            "número se souber. Responda só com JSON: {\"cards\": [{\"name\": \"\", \"set\": \"\", \"number\": \"\"}]} "
            "(lista vazia se não houver carta específica).\n\n"
            f"TÍTULO: {title}\n\nTEXTO:\n{text[:12000]}")}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        return (json.loads(m.group()) if m else {}).get("cards", [])[:3]
    except json.JSONDecodeError:
        return []


def main() -> None:
    client = anthropic.Anthropic()
    posts = _posts_without_cover()
    print(f"[Capas] {len(posts)} post(s) sem capa.")
    done = 0
    for p in posts:
        title = html.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"]))
        text = html.unescape(re.sub(r"<[^>]+>", " ", p["content"]["rendered"]))
        print(f"\n— #{p['id']} {title[:80]}")
        try:
            wanted = _cards_from_text(client, title, text)
            cards = [c for c in (blog_media.lookup_card(w) for w in wanted) if c]
            cat, cat_slug = _category(p.get("categories"))
            cover = blog_media.build_cover(title, cat, cat_slug, cards)
            media_id = wp.upload_cover(cover, p["slug"], title)
            if media_id and wp.set_featured(p["id"], media_id):
                done += 1
                print(f"[Capas] #{p['id']} ok ({len(cards)} carta(s)).")
        except Exception as e:
            print(f"[Capas] #{p['id']} falhou: {e}")
    print(f"\n[Capas] concluído: {done}/{len(posts)} post(s) com capa nova.")


if __name__ == "__main__":
    main()
