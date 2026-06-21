"""
Coleta dados externos para embasar os artigos do blog Voruto.
Fontes: RSS feeds, eBay Browse API (OAuth), PWCC Marketplace, PokémonTCG.io
"""
import os
import re
import time
import base64
import requests
import feedparser

RSS_FEEDS = [
    {"url": "https://www.pokebeach.com/feed",                       "name": "PokeBeach"},
    {"url": "https://hypebeast.com/feed",                           "name": "Hypebeast"},
    {"url": "https://bleedingcool.com/category/collectibles/feed/", "name": "Bleeding Cool"},
    {"url": "https://www.tcgplayer.com/rss/blog",                   "name": "TCGPlayer Blog"},
    {"url": "https://complex.com/rss",                              "name": "Complex"},
    {"url": "https://highsnobiety.com/rss",                         "name": "Highsnobiety"},
]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Cache do token eBay OAuth (válido por 2h)
_ebay_token_cache: dict = {"token": None, "expires_at": 0.0}


# ── eBay Browse API (OAuth) ───────────────────────────────────────────────────

def _get_ebay_oauth_token() -> str:
    if _ebay_token_cache["token"] and time.time() < _ebay_token_cache["expires_at"]:
        return _ebay_token_cache["token"]

    app_id  = os.environ["EBAY_APP_ID"]
    cert_id = os.environ["EBAY_CERT_ID"]
    credentials = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()

    resp = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization":  f"Basic {credentials}",
            "Content-Type":   "application/x-www-form-urlencoded",
        },
        data="grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _ebay_token_cache["token"]      = data["access_token"]
    _ebay_token_cache["expires_at"] = time.time() + data.get("expires_in", 7200) - 60
    return _ebay_token_cache["token"]


def gather_ebay_listings(topic: dict, max_items: int = 8) -> list[dict]:
    """
    Busca listagens de alto valor no eBay via Browse API (OAuth).
    Mostra o mercado ativo de cards raros — preços reais em circulação.
    """
    if not os.environ.get("EBAY_APP_ID") or not os.environ.get("EBAY_CERT_ID"):
        print("[eBay] EBAY_APP_ID ou EBAY_CERT_ID não configurado, pulando.")
        return []

    try:
        token = _get_ebay_oauth_token()
        resp  = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={
                "Authorization":           f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "Content-Type":            "application/json",
            },
            params={
                "q":     topic.get("ebay_query", "pokemon card PSA 10 rare"),
                "sort":  "-price",
                "limit": str(max_items),
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("itemSummaries", [])

        results = []
        for item in items:
            price = item.get("price", {})
            results.append({
                "title":     item.get("title", ""),
                "price_usd": float(price.get("value", 0)),
                "condition": item.get("condition", ""),
                "url":       item.get("itemWebUrl", ""),
                "buying":    ", ".join(item.get("buyingOptions", [])),
            })

        print(f"[eBay] {len(results)} listagens encontradas.")
        return results

    except Exception as e:
        print(f"[eBay] Erro: {e}")
        return []


# ── Google News RSS ───────────────────────────────────────────────────────────

def gather_auction_news(query: str = "pokemon card sold auction PSA graded", max_items: int = 6) -> list[dict]:
    """
    Busca notícias de leilões e vendas de cards via Google News RSS.
    Sem autenticação, sempre atualizado, cobre Heritage, PWCC, eBay e outros.
    """
    import urllib.parse
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:max_items]:
            clean = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:400]
            results.append({
                "title":   entry.get("title", ""),
                "summary": clean,
                "url":     entry.get("link", ""),
                "date":    entry.get("published", ""),
                "source":  entry.get("source", {}).get("title", "Google News"),
            })
        print(f"[Google News] {len(results)} notícias para '{query}'")
        return results
    except Exception as e:
        print(f"[Google News] Erro: {e}")
        return []


# ── PokémonTCG.io ─────────────────────────────────────────────────────────────

def gather_pokemon_sets() -> list[dict]:
    """Busca os sets mais recentes via PokémonTCG.io (API key opcional)."""
    headers = {}
    api_key = os.environ.get("POKEMON_TCG_API_KEY", "")
    if api_key:
        headers["X-Api-Key"] = api_key

    try:
        resp = requests.get(
            "https://api.pokemontcg.io/v2/sets",
            headers=headers,
            params={"orderBy": "-releaseDate", "pageSize": "6"},
            timeout=30,
        )
        resp.raise_for_status()
        return [
            {
                "name":        s.get("name"),
                "series":      s.get("series"),
                "total":       s.get("total"),
                "releaseDate": s.get("releaseDate"),
            }
            for s in resp.json().get("data", [])
        ]
    except Exception as e:
        print(f"[PokémonTCG.io] Erro: {e}")
        return []


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

def gather_rss_news(topic: dict, max_items: int = 10) -> list[dict]:
    """Filtra artigos relevantes dos RSS feeds com base nas keywords do tema."""
    keywords = [k.lower() for k in topic.get("keywords", [])] + [
        "pokemon", "tcg", "card", "collectible", "geek", "anime"
    ]
    articles: list[dict] = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in (feed.entries or [])[:15]:
                title   = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                if any(kw in title + " " + summary for kw in keywords):
                    clean = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:400]
                    articles.append({
                        "source":  feed_info["name"],
                        "title":   entry.get("title", ""),
                        "summary": clean,
                        "url":     entry.get("link", ""),
                        "date":    entry.get("published", ""),
                    })
        except Exception as e:
            print(f"[RSS] Erro em {feed_info['name']}: {e}")

    seen: set[str] = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:max_items]


# ── Orquestrador ──────────────────────────────────────────────────────────────

def gather_all(topic: dict) -> dict:
    print(f"[gather] Coletando dados para: {topic['name']}")

    sets = []
    if topic["slug"] in ("lancamentos-tcg", "mercado-global", "curiosidades-raridades"):
        sets = gather_pokemon_sets()

    auction_news = []
    if topic["slug"] in ("leiloes-mercado", "curiosidades-raridades", "mercado-global"):
        auction_news = gather_auction_news(
            query=f"pokemon card sold auction PSA {topic.get('slug', '')}"
        )

    return {
        "rss_articles":  gather_rss_news(topic),
        "ebay_listings": gather_ebay_listings(topic),
        "auction_news":  auction_news,
        "recent_sets":   sets,
    }
