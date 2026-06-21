"""
Publica posts no WordPress via REST API com Application Password.
"""
import os
import base64
import requests

WP_URL          = os.environ.get("WP_URL",  "https://voruto.com.br")
WP_USER         = os.environ.get("WP_USER", "voruto-blog-bot")
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]

_AUTH = "Basic " + base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
_UA   = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_HEADERS_JSON = {
    "Authorization": _AUTH,
    "Content-Type":  "application/json",
    "User-Agent":    _UA,
    "Accept":        "application/json",
}
_HEADERS_GET = {
    "Authorization": _AUTH,
    "User-Agent":    _UA,
    "Accept":        "application/json",
}


def _get_or_create_term(endpoint: str, name: str) -> int:
    """Retorna ID de uma categoria ou tag, criando se não existir."""
    resp = requests.get(
        f"{WP_URL}/wp-json/wp/v2/{endpoint}",
        headers=_HEADERS_GET,
        params={"search": name, "per_page": 5},
        timeout=10,
    )
    if not resp.text.strip():
        raise RuntimeError(
            f"[WordPress] GET /{endpoint} retornou resposta vazia "
            f"(HTTP {resp.status_code}). "
            f"Verifique se a REST API está habilitada e se WP_APP_PASSWORD está correto. "
            f"URL testada: {WP_URL}/wp-json/wp/v2/{endpoint}"
        )
    if not resp.ok:
        raise RuntimeError(
            f"[WordPress] GET /{endpoint} HTTP {resp.status_code}: {resp.text[:300]}"
        )
    items = resp.json()
    if isinstance(items, list) and items:
        # Busca correspondência exata por nome
        for item in items:
            if item.get("name", "").lower() == name.lower():
                return item["id"]
        return items[0]["id"]

    # Cria o termo
    slug = name.lower().replace(" ", "-").replace("&", "e").replace("ã", "a").replace("ç", "c")
    create = requests.post(
        f"{WP_URL}/wp-json/wp/v2/{endpoint}",
        headers=_HEADERS_JSON,
        json={"name": name, "slug": slug},
        timeout=10,
    )
    create.raise_for_status()
    return create.json()["id"]


def publish(topic: dict, article: dict, slug: str) -> dict:
    """
    Cria um post publicado no WordPress.
    Retorna {"id": int, "url": str}.
    """
    cat_id  = _get_or_create_term("categories", topic["wp_category"])
    tag_ids = [_get_or_create_term("tags", tag) for tag in article.get("tags", [])]

    resp = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts",
        headers=_HEADERS_JSON,
        json={
            "title":      article["title"],
            "content":    article["content_html"],
            "excerpt":    article["excerpt"],
            "status":     "publish",
            "slug":       slug,
            "categories": [cat_id],
            "tags":       tag_ids,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    url  = data.get("link", "")
    print(f"[WordPress] Post {data['id']} publicado: {url}")
    return {"id": data["id"], "url": url}
