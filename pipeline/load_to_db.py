"""Stage 2 / Phase 2 — normalize every raw source into one SQLite `reviews` table.

Source-agnostic: it loads whatever files exist in data/raw/ and silently skips the
ones not collected yet (e.g. reddit.json / bluesky.json before credentials are set up).
Re-running after new sources land folds them in — dedupe on `id` makes it idempotent.

Unified schema (CLAUDE.md §5), plus `country` which we keep for later segment analysis:
    id, source, platform, date, rating, text, url, country

`id` = stable sha1(source | original_id) so re-loads never create duplicates.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "reviews.db"

PLATFORM = {
    "play_store": "android",
    "app_store": "ios",
    "reddit": "web",
    "forum": "web",
    "bluesky": "web",
}


def _row_id(source: str, original_id: str) -> str:
    return hashlib.sha1(f"{source}|{original_id}".encode()).hexdigest()[:16]


def _to_date(raw) -> str | None:
    """Normalize various timestamp formats to an ISO date (YYYY-MM-DD)."""
    if not raw:
        return None
    s = str(raw).strip().replace("Z", "")
    # try full ISO first, then date-only
    for parser in (
        lambda x: datetime.fromisoformat(x),
        lambda x: datetime.strptime(x[:10], "%Y-%m-%d"),
    ):
        try:
            return parser(s).date().isoformat()
        except (ValueError, TypeError):
            continue
    return None


def _make(source, original_id, date, rating, text, url, country):
    text = (text or "").strip()
    if not text:
        return None
    return {
        "id": _row_id(source, str(original_id)),
        "source": source,
        "platform": PLATFORM.get(source, "web"),
        "date": _to_date(date),
        "rating": rating,
        "text": text,
        "url": url,
        "country": country,
    }


# ---- per-source normalizers (each yields unified rows) ----

def normalize_play_store(raw: list[dict]):
    app_url = "https://play.google.com/store/apps/details?id=com.spotify.music"
    for r in raw:
        yield _make(
            "play_store", r.get("reviewId"), r.get("at"), r.get("score"),
            r.get("content"), app_url, r.get("country"),
        )


def normalize_app_store(raw: list[dict]):
    for r in raw:
        title = (r.get("title") or "").strip()
        body = (r.get("content") or "").strip()
        text = f"{title}. {body}" if title else body
        yield _make(
            "app_store", r.get("reviewId"), r.get("at"), r.get("score"),
            text, None, r.get("country"),
        )


def normalize_forum(raw: list[dict]):
    for r in raw:
        # for the opening post, prepend the thread title for context
        text = r.get("text") or ""
        if r.get("kind") == "thread" and r.get("title"):
            text = f"{r['title']}. {text}"
        yield _make(
            "forum", r.get("id"), r.get("date"), None, text, r.get("url"), None,
        )


def normalize_reddit(raw: list[dict]):
    for r in raw:
        text = r.get("text") or ""
        if r.get("kind") == "submission" and r.get("title"):
            text = f"{r['title']}. {text}"
        url = r.get("permalink")
        if url and url.startswith("/"):
            url = "https://www.reddit.com" + url
        yield _make(
            "reddit", r.get("id"), r.get("created_utc"), None, text, url, None,
        )


def normalize_bluesky(raw: list[dict]):
    for r in raw:
        yield _make(
            "bluesky", r.get("uri"), r.get("created_at"), None,
            r.get("text"), r.get("url"), None,
        )


NORMALIZERS = {
    "play_store": normalize_play_store,
    "app_store": normalize_app_store,
    "forum": normalize_forum,
    "reddit": normalize_reddit,
    "bluesky": normalize_bluesky,
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id       TEXT PRIMARY KEY,
            source   TEXT NOT NULL,
            platform TEXT,
            date     TEXT,
            rating   INTEGER,
            text     TEXT NOT NULL,
            url      TEXT,
            country  TEXT
        )
        """
    )
    conn.commit()


def load() -> None:
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    per_source: dict[str, dict] = {}
    for source, normalizer in NORMALIZERS.items():
        path = RAW_DIR / f"{source}.json"
        if not path.exists():
            print(f"[{source}] no raw file (skipped)")
            continue
        raw = json.loads(path.read_text())
        if not raw:
            print(f"[{source}] raw file empty (skipped)")
            continue

        rows = [r for r in normalizer(raw) if r]
        before = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        conn.executemany(
            """
            INSERT OR IGNORE INTO reviews
                (id, source, platform, date, rating, text, url, country)
            VALUES (:id, :source, :platform, :date, :rating, :text, :url, :country)
            """,
            rows,
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        per_source[source] = {
            "normalized": len(rows),
            "inserted": after - before,
            "dupes_skipped": len(rows) - (after - before),
        }
        print(
            f"[{source}] normalized={len(rows)} inserted={after - before} "
            f"dupes_skipped={len(rows) - (after - before)}"
        )

    # ---- verification output ----
    print("\n=== reviews table summary ===")
    total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    print(f"Total rows: {total}")
    for source, n in conn.execute(
        "SELECT source, COUNT(*) FROM reviews GROUP BY source ORDER BY COUNT(*) DESC"
    ):
        print(f"  {source}: {n}")

    print("\n3 sample rows:")
    for row in conn.execute(
        "SELECT source, platform, date, rating, country, substr(text,1,140) "
        "FROM reviews ORDER BY RANDOM() LIMIT 3"
    ):
        src, plat, date, rating, country, text = row
        print(
            f"- [{src}/{plat}] date={date} rating={rating} country={country}\n"
            f"    {text}"
        )

    conn.close()


if __name__ == "__main__":
    load()
