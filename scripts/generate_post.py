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


def _normalize_slug(text: str) -> str:
    for chars, replacement in [("áàãâä","a"),("éèêë","e"),("íìîï","i"),("óòõôö","o"),("úùûü","u"),("ç","c")]:
        for ch in chars:
            text = text.replace(ch, replacement)
    return text.lower().strip()


def pick_topic() -> dict:
    """
    Seleciona o tema do post por rotação semanal (2 publicações/semana).
    TOPIC_OVERRIDE aceita o slug com ou sem acentos (ex: leiloes-mercado ou leilões-mercado).
    """
    override = _normalize_slug(os.environ.get("TOPIC_OVERRIDE", ""))
    if override:
        for t in _TOPICS:
            if _normalize_slug(t["slug"]) == override:
                return t
        print(f"[warn] TOPIC_OVERRIDE '{override}' não encontrado, usando rotação automática.")

    now      = datetime.utcnow()
    week     = now.isocalendar()[1]
    pub_slot = 0 if now.weekday() < 3 else 1   # Seg-Qua = slot 0, Qui-Dom = slot 1
    idx      = (week * 2 + pub_slot) % len(_TOPICS)
    return _TOPICS[idx]


# ── GERAÇÃO COM CLAUDE ────────────────────────────────────────────────────────

SYSTEM_PROMPT = (_ROOT / "prompts" / "system_prompt.txt").read_text(encoding="utf-8")


def _build_context(data: dict) -> tuple[str, list[str]]:
    """Returns (context_text, sources_used_list)."""
    parts = []
    sources_used: list[str] = []

    if data["rss_articles"]:
        rss_sources = list({a["source"] for a in data["rss_articles"][:8]})
        sources_used.extend(rss_sources)
        lines = [
            f"- [{a['source']}] {a['title']} — {a['summary'][:280]}"
            for a in data["rss_articles"][:8]
        ]
        parts.append("### Notícias recentes (RSS — PokeBeach, Hypebeast, TCGPlayer, etc.):\n" + "\n".join(lines))

    if data.get("ebay_listings"):
        sources_used.append("eBay Browse API")
        lines = [
            f"- {l['title']}: US$ {l['price_usd']:,.0f} ({l['condition']}) — {l['buying']}"
            for l in data["ebay_listings"][:8]
        ]
        parts.append(
            "### Mercado ativo eBay — cards de alto valor em circulação (dados em tempo real):\n"
            + "\n".join(lines)
            + "\n(Use esses preços para contextualizar o mercado. Cite como 'dados do eBay'.)"
        )

    if data.get("auction_news"):
        sources_used.append("Google News")
        lines = [
            f"- [{n['source']}] {n['title']} ({n['date'][:16]}) — {n['summary'][:200]}"
            for n in data["auction_news"][:6]
        ]
        parts.append("### Notícias de leilões e vendas recentes (Google News — Heritage, PWCC, eBay):\n" + "\n".join(lines))

    if data.get("recent_sets"):
        sources_used.append("PokémonTCG.io")
        lines = [
            f"- {s['name']} ({s['series']}) — {s['total']} cartas — lançado em {s['releaseDate']}"
            for s in data["recent_sets"]
        ]
        parts.append("### Sets Pokémon TCG mais recentes (PokémonTCG.io):\n" + "\n".join(lines))

    text = "\n\n".join(parts) if parts else "Dados externos indisponíveis. Use conhecimento de mercado consolidado e histórico."
    return text, list(dict.fromkeys(sources_used))  # deduplica preservando ordem


def generate_article(topic: dict, data: dict) -> dict:
    print("[Claude] Gerando artigo...")
    context, sources_used = _build_context(data)

    user_msg = f"""Escreva um artigo completo para o blog da VORUTO sobre o tema: **{topic['name']}**

Descrição do tema: {topic['description']}

Dados coletados de múltiplas fontes para embasar o artigo:
{context}

INSTRUÇÕES IMPORTANTES:
- Cruze as informações entre as fontes. Um preço do eBay + uma notícia de leilão + um lançamento de set contam uma história mais rica do que qualquer fonte isolada.
- Cite as fontes brevemente no texto (ex: "segundo dados do eBay", "conforme noticiado pela Heritage Auctions", "de acordo com o PokémonTCG.io").
- Use dados concretos: preços reais, nomes de cards, datas, volumes de mercado quando disponíveis.
- Contextualize para o colecionador brasileiro: câmbio BRL/USD, barreiras de importação, mercado local.

Estrutura obrigatória do corpo HTML:
1. Introdução (1-2 parágrafos) — por que este tema é relevante agora
2. Panorama do mercado — análise dos dados coletados, cruzando fontes
3. Análise aprofundada — 2-3 sub-seções com <h3> sobre aspectos técnicos, históricos ou tendências
4. <h2>Perspectiva de Investimento</h2> — risco/retorno, liquidez, comparação com outros ativos alternativos, impacto do câmbio para o colecionador BR
5. <h2>Reflexão do Colecionador</h2> — o lado humano, cultural e emocional. Voz mais pessoal e conectada à missão da VORUTO
6. Conclusão com CTA natural (1 parágrafo) — link para voruto.com.br/marketplace ou /vorfamily

Requisitos finais:
- HTML limpo: apenas <p>, <h2>, <h3>, <ul>, <li>, <strong>, <em>, <blockquote>
- Entre 1.200 e 1.500 palavras no corpo total
- Título criativo e otimizado para SEO (texto simples, sem markdown)
- Excerpt de 1-2 frases impactantes
- Meta description SEO: máximo 155 caracteres
- Tags: 6 a 8 palavras-chave

Responda SOMENTE com JSON válido, sem markdown ao redor:
{{
  "title": "...",
  "excerpt": "...",
  "content_html": "...",
  "meta_description": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"]
}}"""

    client  = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Claude não retornou JSON válido:\n{raw[:600]}")

    article = json.loads(match.group())
    article["_sources_used"] = sources_used
    return article


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
