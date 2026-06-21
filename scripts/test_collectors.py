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


def test_wordpress() -> None:
    section("WordPress REST API — Autenticação e categorias")
    import os, base64, requests
    wp_url  = os.environ.get("WP_URL",  "https://voruto.com.br")
    wp_user = os.environ.get("WP_USER", "voruto-blog-bot")
    wp_pass = os.environ.get("WP_APP_PASSWORD", "")

    if not wp_pass:
        print("  FALHOU  WP_APP_PASSWORD não definido no .env")
        return

    auth = "Basic " + base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    ua   = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    headers_get  = {"Authorization": auth, "User-Agent": ua, "Accept": "application/json"}
    headers_post = {**headers_get, "Content-Type": "application/json"}

    # Teste 1: GET sem auth mas com UA de browser
    r1 = requests.get(f"{wp_url}/wp-json/wp/v2/categories",
                      headers={"User-Agent": ua, "Accept": "application/json"}, timeout=10)
    print(f"  GET sem auth  : HTTP {r1.status_code} — {len(r1.text)} bytes")

    # Teste 2: GET com auth + UA
    r2 = requests.get(f"{wp_url}/wp-json/wp/v2/categories",
                      headers=headers_get,
                      params={"search": "Leilões", "per_page": 5}, timeout=10)
    print(f"  GET com auth  : HTTP {r2.status_code} — {len(r2.text)} bytes")
    if r2.text.strip():
        print(f"  Resposta      : {r2.text[:200]}")
    else:
        print("  Resposta      : VAZIA")

    # Teste 3: /users/me com auth + UA
    r3 = requests.get(f"{wp_url}/wp-json/wp/v2/users/me",
                      headers=headers_get, timeout=10)
    print(f"  /users/me     : HTTP {r3.status_code} — {r3.text[:200]}")


if __name__ == "__main__":
    print("\nVORUTO BLOG AI — Teste de Collectors")
    test_rss()
    test_pokemon_tcg()
    test_ebay()
    test_auction_news()
    test_wordpress()
    print(f"\n{'=' * 55}")
    print("  Teste concluído.")
    print(f"{'=' * 55}\n")
