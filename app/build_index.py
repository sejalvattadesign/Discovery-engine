"""Phase 6 (build step) — embed coded reviews into a local Chroma vector store.

Reads relevant + coded reviews from SQLite, embeds each with sentence-transformers
(all-MiniLM-L6-v2, local & free), and writes them to a persistent Chroma collection at
data/chroma/. The Streamlit app queries this collection for retrieval-augmented answers.

Run once after classify.py (re-run to rebuild): python app/build_index.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reviews.db"
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = "reviews"
EMBED_MODEL = "all-MiniLM-L6-v2"


def fetch_rows() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT r.id, r.text, r.source, r.date, r.url, r.country, r.rating,
               c.themes, c.sentiment, c.segment, c.evidence
        FROM reviews r
        JOIN coded_reviews c ON c.id = r.id
        WHERE r.relevant = 1
        """
    ).fetchall()
    conn.close()
    cols = [
        "id", "text", "source", "date", "url", "country", "rating",
        "themes", "sentiment", "segment", "evidence",
    ]
    return [dict(zip(cols, row)) for row in rows]


def build() -> None:
    rows = fetch_rows()
    print(f"Embedding {len(rows)} coded reviews with {EMBED_MODEL} ...")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # rebuild from scratch for a clean, reproducible index
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    collection = client.create_collection(COLLECTION, embedding_function=embed_fn)

    ids, docs, metas = [], [], []
    for r in rows:
        themes = ", ".join(json.loads(r["themes"] or "[]"))
        ids.append(r["id"])
        docs.append(r["text"])
        metas.append(
            {
                "source": r["source"] or "",
                "date": r["date"] or "",
                "url": r["url"] or "",
                "country": r["country"] or "",
                "rating": r["rating"] if r["rating"] is not None else -1,
                "themes": themes,
                "sentiment": r["sentiment"] or "",
                "segment": r["segment"] or "",
                "evidence": r["evidence"] or "",
            }
        )

    # add in batches (Chroma embeds on add)
    B = 256
    for i in range(0, len(ids), B):
        collection.add(
            ids=ids[i : i + B],
            documents=docs[i : i + B],
            metadatas=metas[i : i + B],
        )
        print(f"  indexed {min(i + B, len(ids))}/{len(ids)}")

    print(f"Done. Collection '{COLLECTION}' has {collection.count()} docs at {CHROMA_DIR}")


if __name__ == "__main__":
    build()
