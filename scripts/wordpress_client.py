"""
Publica posts no WordPress via REST API com Application Password.
O bypass do Cloudflare é feito via /etc/hosts no workflow (IP direto + domínio real).
"""
import os
import base64
import requests

WP_URL  = os.environ.get("WP_URL",  "https://voruto.com.br")
WP_USER = os.environ.get("WP_USER", "voruto-blog-bot")

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _auth_headers(content_type: bool = False) -> dict:
    password = os.environ.get("WP_APP_PASSWORD", "")
    if not password:
        raise RuntimeError(
            "[WordPress] WP_APP_PASSWORD não configurado. "
            "Configure em WP Admin → Usuários → voruto-blog-bot → Senhas de aplicativo."
        )
    auth = "Basic " + base64.b64encode(f"{WP_USER}:{password}".encode()).decode()
    headers = {"Authorization": auth, "User-Agent": _UA, "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _get_or_create_term(endpoint: str, name: str) -> int:
    """Retorna ID de uma categoria ou tag, criando se não existir."""
    resp = requests.get(
        f"{WP_URL}/wp-json/wp/v2/{endpoint}",
        headers=_auth_headers(),
        params={"search": name, "per_page": 5},
        timeout=10,
    )
    if not resp.text.strip():
        raise RuntimeError(
            f"[WordPress] GET /{endpoint} retornou resposta vazia "
            f"(HTTP {resp.status_code}). "
            f"Verifique se a REST API está habilitada e se WP_APP_PASSWORD está correto."
        )
    if not resp.ok:
        raise RuntimeError(
            f"[WordPress] GET /{endpoint} HTTP {resp.status_code}: {resp.text[:300]}"
        )
    items = resp.json()
    if isinstance(items, list) and items:
        for item in items:
            if item.get("name", "").lower() == name.lower():
                return item["id"]
        return items[0]["id"]

    slug   = name.lower().replace(" ", "-").replace("&", "e").replace("ã", "a").replace("ç", "c")
    create = requests.post(
        f"{WP_URL}/wp-json/wp/v2/{endpoint}",
        headers=_auth_headers(content_type=True),
        json={"name": name, "slug": slug},
        timeout=10,
    )
    if create.status_code == 400:
        body = create.json()
        if body.get("code") == "term_exists":
            term_id = body.get("data", {}).get("term_id")
            if term_id:
                print(f"[WordPress] Termo '{name}' já existe (ID {term_id}), reutilizando.")
                return int(term_id)
    if not create.ok:
        raise RuntimeError(
            f"[WordPress] POST /{endpoint} HTTP {create.status_code}: {create.text[:300]}"
        )
    return create.json()["id"]


def upload_featured_image(image: dict, title: str) -> int | None:
    """
    Baixa imagem do Pexels e faz upload para a biblioteca de mídia do WordPress.
    Retorna o media ID ou None se falhar.
    """
    try:
        img_resp = requests.get(image["url"], timeout=30)
        img_resp.raise_for_status()

        safe_title = "".join(c if c.isalnum() or c == "-" else "-" for c in title.lower()[:40])
        filename   = f"voruto-{safe_title}.jpg"

        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            headers={
                **_auth_headers(),
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type":        "image/jpeg",
            },
            data=img_resp.content,
            timeout=30,
        )
        if not resp.ok:
            print(f"[WordPress] Upload de imagem falhou: {resp.status_code} {resp.text[:200]}")
            return None
        media_id = resp.json()["id"]

        # Adiciona crédito ao fotógrafo nos metadados da imagem
        requests.post(
            f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
            headers=_auth_headers(content_type=True),
            json={"caption": f'Foto: <a href="{image["pexels_url"]}" target="_blank">'
                             f'{image["photographer"]}</a> via Pexels'},
            timeout=10,
        )
        print(f"[WordPress] Imagem enviada: ID {media_id} ({image['photographer']} / Pexels)")
        return media_id
    except Exception as e:
        print(f"[WordPress] Erro no upload de imagem: {e}")
        return None


def publish(topic: dict, article: dict, slug: str, featured_image: dict | None = None) -> dict:
    """
    Cria um post publicado no WordPress.
    Retorna {"id": int, "url": str}.
    """
    import json as _json
    cat_id   = _get_or_create_term("categories", topic["wp_category"])
    tag_ids  = [_get_or_create_term("tags", tag) for tag in article.get("tags", [])]
    media_id = upload_featured_image(featured_image, article["title"]) if featured_image else None

    word_count   = len(article.get("content_html", "").split())
    reading_time = max(1, round(word_count / 200))
    sources_used = article.get("_sources_used", [])

    payload = {
        "title":      article["title"],
        "content":    article["content_html"],
        "excerpt":    article["excerpt"],
        "status":     "publish",
        "slug":       slug,
        "categories": [cat_id],
        "tags":       tag_ids,
        "meta": {
            "_voruto_reading_time": str(reading_time),
            "_voruto_sources":      _json.dumps(sources_used, ensure_ascii=False),
        },
    }
    if media_id:
        payload["featured_media"] = media_id

    resp = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts",
        headers=_auth_headers(content_type=True),
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"[WordPress] POST /posts HTTP {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    url  = data.get("link", "")
    print(f"[WordPress] Post {data['id']} publicado: {url}")
    print(f"[WordPress] Tempo de leitura: {reading_time} min | Fontes: {sources_used}")
    return {"id": data["id"], "url": url}
