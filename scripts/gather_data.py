"""
Coleta dados externos para embasar os artigos do blog Voruto.
Fontes: RSS feeds, eBay Finding API (sold listings), Heritage Auctions RSS, PokémonTCG.io
"""
import os
import re
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

# URL do feed RSS de resultados realizados da Heritage Auctions.
# Categoria 2601 = Trading Cards. Ajuste o ID se necessário.
# Referência: https://www.ha.com/rss/auctions.zx
HERITAGE_RSS_URL = os.environ.get(
    "HERITAGE_RSS_URL",
    "https://www.ha.com/rss/auctions.zx?category=2601&type=realized",
)


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


def gather_ebay_sold(topic: dict, max_items: int = 8) -> list[dict]:
    """
    Busca leilões CONCLUÍDOS (vendidos) no eBay via Finding API — findCompletedItems.
    Retorna apenas itens que efetivamente foram vendidos (EndedWithSales).
    """
    app_id = os.environ.get("EBAY_APP_ID", "")
    if not app_id:
        print("[eBay] EBAY_APP_ID não configurado, pulando.")
        return []

    try:
        resp = requests.get(
            "https://svcs.ebay.com/services/search/FindingService/v1",
            params={
                "OPERATION-NAME":                    "findCompletedItems",
                "SERVICE-VERSION":                   "1.0.0",
                "SECURITY-APPNAME":                  app_id,
                "RESPONSE-DATA-FORMAT":              "JSON",
                "keywords":                          topic.get("ebay_query", "pokemon card PSA 10 rare"),
                "categoryId":                        "183050",
                "itemFilter(0).name":                "SoldItemsOnly",
                "itemFilter(0).value":               "true",
                "sortOrder":                         "PricePlusShippingHighest",
                "paginationInput.entriesPerPage":    str(max_items),
            },
            timeout=12,
        )
        resp.raise_for_status()
        items = (
            resp.json()
            .get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
        )
        results = []
        for item in items:
            selling_state = (
                item.get("sellingStatus", [{}])[0]
                    .get("sellingState", [""])[0]
            )
            if selling_state != "EndedWithSales":
                continue
            sold_price = float(
                item.get("sellingStatus", [{}])[0]
                    .get("currentPrice", [{}])[0]
                    .get("__value__", "0")
            )
            results.append({
                "title":       item.get("title", [""])[0],
                "sold_usd":    sold_price,
                "url":         item.get("viewItemURL", [""])[0],
                "condition":   (
                    item.get("condition", [{}])[0]
                        .get("conditionDisplayName", [""])[0]
                ),
                "end_date":    (
                    item.get("listingInfo", [{}])[0]
                        .get("endTime", [""])[0]
                ),
            })
        return results
    except Exception as e:
        print(f"[eBay] Erro: {e}")
        return []


def gather_heritage_results(max_items: int = 6) -> list[dict]:
    """
    Coleta resultados realizados de leilões da Heritage Auctions via RSS.
    Categoria 2601 = Trading Cards (Pokémon, MTG, etc.).
    """
    try:
        feed = feedparser.parse(HERITAGE_RSS_URL)
        if not feed.entries:
            print(f"[Heritage] Feed sem entradas: {HERITAGE_RSS_URL}")
            return []

        results = []
        for entry in feed.entries[:max_items]:
            clean_summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:500]
            results.append({
                "title":   entry.get("title", ""),
                "summary": clean_summary,
                "url":     entry.get("link", ""),
                "date":    entry.get("published", ""),
            })
        return results
    except Exception as e:
        print(f"[Heritage] Erro: {e}")
        return []


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
            timeout=10,
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


def gather_all(topic: dict) -> dict:
    print(f"[gather] Coletando dados para: {topic['name']}")

    sets = []
    if topic["slug"] in ("lancamentos-tcg", "mercado-global", "curiosidades-raridades"):
        sets = gather_pokemon_sets()

    heritage = []
    if topic["slug"] in ("leiloes-mercado", "curiosidades-raridades", "mercado-global"):
        heritage = gather_heritage_results()

    return {
        "rss_articles":       gather_rss_news(topic),
        "ebay_sold":          gather_ebay_sold(topic),
        "heritage_results":   heritage,
        "recent_sets":        sets,
    }
