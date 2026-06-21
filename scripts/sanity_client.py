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
SANITY_TOKEN      = os.environ["SANITY_API_TOKEN"]

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
            "Authorization": f"Bearer {SANITY_TOKEN}",
            "Content-Type":  "application/json",
        },
        json={"mutations": [{"createOrReplace": doc}]},
        timeout=15,
    )
    resp.raise_for_status()
    print(f"[Sanity] Publicado: {doc_id}  (slug: {slug})")
    return slug
