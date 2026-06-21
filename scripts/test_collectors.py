#!/usr/bin/env python3
"""
Testa os collectors individualmente sem gerar artigo nem publicar nada.
Uso: python3 scripts/test_collectors.py
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

import gather_data

TOPIC_LEILOES = {
    "slug": "leiloes-mercado",
    "name": "Leilões & Mercado",
    "keywords": ["pokemon card auction", "PSA 10 charizard", "PWCC", "graded card sale"],
    "ebay_query": "pokemon card PSA 10 graded charizard rare vintage",
}


def section(title: str) -> None:
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")


def test_rss() -> None:
    section("RSS Feeds")
    results = gather_data.gather_rss_news(TOPIC_LEILOES, max_items=3)
    if results:
        for r in results:
            print(f"  OK  [{r['source']}] {r['title'][:70]}")
    else:
        print("  FALHOU  Nenhum artigo encontrado")


def test_pokemon_tcg() -> None:
    section("PokémonTCG.io — Sets recentes")
    results = gather_data.gather_pokemon_sets()
    if results:
        for r in results:
            print(f"  OK  {r['name']} ({r['series']}) — {r['releaseDate']}")
    else:
        print("  FALHOU  Nenhum set encontrado")


def test_ebay() -> None:
    section("eBay Browse API — Listagens de alto valor")
    results = gather_data.gather_ebay_listings(TOPIC_LEILOES, max_items=5)
    if results:
        for r in results:
            print(f"  OK  {r['title'][:65]}")
            print(f"       US$ {r['price_usd']:,.0f} | {r['condition']}")
    else:
        print("  FALHOU  Verifique EBAY_APP_ID e EBAY_CERT_ID no .env")


def test_auction_news() -> None:
    section("Google News — Notícias de leilões TCG")
    results = gather_data.gather_auction_news(max_items=5)
    if results:
        for r in results:
            print(f"  OK  [{r['source']}] {r['title'][:65]}")
            print(f"       {r['date'][:16]}")
    else:
        print("  FALHOU  Verifique conexão com Google News")


if __name__ == "__main__":
    print("\nVORUTO BLOG AI — Teste de Collectors")
    test_rss()
    test_pokemon_tcg()
    test_ebay()
    test_auction_news()
    print(f"\n{'=' * 55}")
    print("  Teste concluído.")
    print(f"{'=' * 55}\n")
