"""
Publica posts no Sanity via HTTP Mutations API.
Não requer SDK — apenas requests.
"""
import os
import re
from datetime import datetime, timezone

import requests

SANITY_PROJECT_ID = os.environ.get("SANITY_PROJECT_ID", "cuj6jfyx")
SANITY_DATASET    = os.environ.get("SANITY_DATASET",    "production")

_API_URL = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/data/mutate/{SANITY_DATASET}"


def _slugify(text: str) -> str:
    for src, tgt in [
        ("áàãâä", "a"), ("éèêë", "e"), ("íìîï", "i"),
        ("óòõôö", "o"), ("úùûü", "u"), ("ç", "c"),
    ]:
        for ch in src:
            text = text.replace(ch, tgt)
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")[:80]


def publish(topic: dict, article: dict) -> str:
    """
    Cria ou substitui um documento blogPost no Sanity.
    Retorna o slug gerado.
    """
    token = os.environ.get("SANITY_API_TOKEN", "")
    if not token:
        raise RuntimeError("[Sanity] SANITY_API_TOKEN não configurado.")

    slug   = _slugify(article["title"])
    doc_id = f"blogPost-{datetime.now().strftime('%Y%m%d%H%M')}"
    now    = datetime.now(timezone.utc).isoformat()

    doc = {
        "_id":             doc_id,
        "_type":           "blogPost",
        "title":           article["title"],
        "slug":            {"_type": "slug", "current": slug},
        "excerpt":         article["excerpt"],
        "contentHtml":     article["content_html"],
        "metaDescription": article.get("meta_description", ""),
        "tags":            article.get("tags", []),
        "category":        topic["wp_category"],
        "publishedAt":     now,
        "aiGenerated":     True,
    }

    resp = requests.post(
        _API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={"mutations": [{"createOrReplace": doc}]},
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"[Sanity] HTTP {resp.status_code}: {resp.text[:400]}")
    print(f"[Sanity] Publicado: {doc_id}  (slug: {slug})")
    return slug


def delete(slug: str) -> None:
    """Remove documento do Sanity pelo slug (rollback em caso de falha no WordPress)."""
    token = os.environ.get("SANITY_API_TOKEN", "")
    if not token:
        print("[Sanity] SANITY_API_TOKEN ausente — não foi possível fazer rollback.")
        return

    query = f'*[_type == "blogPost" && slug.current == "{slug}"][0]._id'
    resp  = requests.get(
        f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/data/query/{SANITY_DATASET}",
        headers={"Authorization": f"Bearer {token}"},
        params={"query": query},
        timeout=10,
    )
    doc_id = resp.json().get("result") if resp.ok else None
    if not doc_id:
        print(f"[Sanity] Rollback: documento com slug '{slug}' não encontrado.")
        return

    del_resp = requests.post(
        _API_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"mutations": [{"delete": {"id": doc_id}}]},
        timeout=10,
    )
    if del_resp.ok:
        print(f"[Sanity] Rollback: documento {doc_id} removido.")
    else:
        print(f"[Sanity] Rollback falhou: {del_resp.status_code} {del_resp.text[:200]}")
