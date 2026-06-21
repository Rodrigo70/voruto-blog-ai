#!/usr/bin/env python3
"""
Voruto Blog AI — Gerador automático de posts.
Executa 2x/semana via GitHub Actions (segunda e quinta, 9h BRT).
"""
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Garante que scripts/ está no path (para importar os outros módulos)
sys.path.insert(0, str(Path(__file__).parent))

import gather_data
import sanity_client
import wordpress_client


# ── ROTAÇÃO DE TEMAS ──────────────────────────────────────────────────────────

_ROOT   = Path(__file__).parent.parent
_TOPICS = json.loads((_ROOT / "topics" / "rotation.json").read_text())["categories"]


def pick_topic() -> dict:
    """
    Seleciona o tema do post por rotação semanal (2 publicações/semana).
    TOPIC_OVERRIDE aceita o slug exato de uma categoria para forçar o tema.
    """
    override = os.environ.get("TOPIC_OVERRIDE", "").strip()
    if override:
        for t in _TOPICS:
            if t["slug"] == override:
                return t
        print(f"[warn] TOPIC_OVERRIDE '{override}' não encontrado, usando rotação automática.")

    now      = datetime.utcnow()
    week     = now.isocalendar()[1]
    pub_slot = 0 if now.weekday() < 3 else 1   # Seg-Qua = slot 0, Qui-Dom = slot 1
    idx      = (week * 2 + pub_slot) % len(_TOPICS)
    return _TOPICS[idx]


# ── GERAÇÃO COM CLAUDE ────────────────────────────────────────────────────────

SYSTEM_PROMPT = (_ROOT / "prompts" / "system_prompt.txt").read_text(encoding="utf-8")


def _build_context(data: dict) -> str:
    parts = []

    if data["rss_articles"]:
        lines = [
            f"- [{a['source']}] {a['title']} — {a['summary'][:220]}"
            for a in data["rss_articles"][:8]
        ]
        parts.append("### Notícias recentes (RSS):\n" + "\n".join(lines))

    if data.get("ebay_sold"):
        lines = [
            f"- {l['title']}: vendido por US$ {l['sold_usd']:,.0f} ({l['condition']}) em {l['end_date'][:10]}"
            for l in data["ebay_sold"][:6]
        ]
        parts.append("### Vendas recentes no eBay (leilões concluídos):\n" + "\n".join(lines))

    if data.get("heritage_results"):
        lines = [
            f"- {h['title']} — {h['summary'][:250]}"
            for h in data["heritage_results"][:4]
        ]
        parts.append("### Resultados Heritage Auctions:\n" + "\n".join(lines))

    if data.get("recent_sets"):
        lines = [
            f"- {s['name']} ({s['series']}) — {s['total']} cartas — lançado em {s['releaseDate']}"
            for s in data["recent_sets"]
        ]
        parts.append("### Sets Pokémon TCG recentes (PokémonTCG.io):\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "Dados externos indisponíveis. Use conhecimento de mercado consolidado."


def generate_article(topic: dict, data: dict) -> dict:
    print("[Claude] Gerando artigo...")
    context = _build_context(data)

    user_msg = f"""Escreva um artigo completo para o blog da Voruto sobre o tema: **{topic['name']}**

Descrição do tema: {topic['description']}

Dados coletados para embasar o artigo:
{context}

Requisitos do artigo:
1. **Título** criativo e otimizado para SEO (texto simples, sem markdown no título)
2. **Resumo** de 1-2 frases para o excerpt
3. **Corpo** em HTML limpo (use apenas <p>, <h2>, <h3>, <ul>, <li>, <strong>, <em>):
   - Introdução envolvente (1-2 parágrafos)
   - 3 a 4 seções com subtítulos <h2>
   - Dados reais dos feeds quando disponíveis
   - Perspectiva de investimento e colecionismo
   - Conclusão com CTA natural para voruto.com.br/marketplace ou /vorfamily
   - Entre 900 e 1.200 palavras no total
4. **Meta description** SEO: máximo 155 caracteres
5. **Tags**: 5 a 7 palavras-chave em formato array

Responda SOMENTE com JSON válido, sem markdown ao redor:
{{
  "title": "...",
  "excerpt": "...",
  "content_html": "...",
  "meta_description": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""

    client  = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()

    # Extrai JSON mesmo que venha envolto em ```json ... ```
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Claude não retornou JSON válido:\n{raw[:600]}")

    return json.loads(match.group())


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'=' * 55}")
    print(f"  VORUTO BLOG AI — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"{'=' * 55}\n")

    topic   = pick_topic()
    print(f"Tema: {topic['name']}\n")

    data    = gather_data.gather_all(topic)
    article = generate_article(topic, data)
    slug    = sanity_client.publish(topic, article)
    result  = wordpress_client.publish(topic, article, slug)

    print(f"\n{'=' * 55}")
    print(f"  PUBLICADO")
    print(f"  Título:       {article['title']}")
    print(f"  WordPress ID: {result['id']}")
    print(f"  URL:          {result['url']}")
    print(f"  Sanity slug:  {slug}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
