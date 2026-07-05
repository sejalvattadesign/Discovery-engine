"""Stage 1 / Phase 1 — Play Store scraper (backbone source).

Pulls Spotify reviews for `com.spotify.music` from the Google Play Store across the
IN and US storefronts, newest first, and caches the combined result to
`data/raw/play_store.json`.

Design rules (per CLAUDE.md):
- Cache-first: if the cache file exists we DO NOT re-hit the API unless --refresh.
- Throttled: small sleep between pagination batches.
- Idempotent & independently runnable: `python scrape/play_store.py`.

Each cached item keeps the fields we need downstream:
    reviewId, content, score, at (ISO), thumbsUpCount, country
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from google_play_scraper import Sort, reviews

APP_ID = "com.spotify.music"
COUNTRIES = ["in", "us"]
LANG = "en"

# ~2,500 per country -> ~5,000 total, comfortably above the 2,000 floor.
TARGET_PER_COUNTRY = 2500
BATCH = 200          # max page size the API reliably returns
SLEEP_SECONDS = 1.0  # throttle between batches

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "play_store.json"


def _serialize(entry: dict, country: str) -> dict:
    """Trim a raw review to the fields we cache; make `at` JSON-safe (ISO string)."""
    at = entry.get("at")
    if isinstance(at, datetime):
        at = at.isoformat()
    return {
        "reviewId": entry.get("reviewId"),
        "content": entry.get("content"),
        "score": entry.get("score"),
        "at": at,
        "thumbsUpCount": entry.get("thumbsUpCount"),
        "country": country,
    }


def fetch_country(country: str, target: int = TARGET_PER_COUNTRY) -> list[dict]:
    """Paginate newest-first reviews for one storefront up to `target` items."""
    collected: list[dict] = []
    token = None
    print(f"[{country}] fetching up to {target} reviews ...")
    while len(collected) < target:
        count = min(BATCH, target - len(collected))
        result, token = reviews(
            APP_ID,
            lang=LANG,
            country=country,
            sort=Sort.NEWEST,
            count=count,
            continuation_token=token,
        )
        if not result:
            print(f"[{country}] no more reviews; stopping at {len(collected)}")
            break
        collected.extend(_serialize(r, country) for r in result)
        print(f"[{country}] collected {len(collected)}")
        if token is None:
            print(f"[{country}] reached end of pagination at {len(collected)}")
            break
        time.sleep(SLEEP_SECONDS)
    return collected


def scrape(refresh: bool = False) -> list[dict]:
    """Return all reviews, using the on-disk cache unless refresh=True."""
    if RAW_PATH.exists() and not refresh:
        print(f"Cache hit: {RAW_PATH} (use --refresh to re-scrape)")
        return json.loads(RAW_PATH.read_text())

    all_reviews: list[dict] = []
    for country in COUNTRIES:
        all_reviews.extend(fetch_country(country))

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(all_reviews, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_reviews)} reviews -> {RAW_PATH}")
    return all_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Spotify Play Store reviews.")
    parser.add_argument(
        "--refresh", action="store_true", help="ignore cache and re-scrape"
    )
    args = parser.parse_args()

    data = scrape(refresh=args.refresh)

    # ---- verification output (per CLAUDE.md: print counts + samples) ----
    print("\n=== Play Store scrape summary ===")
    print(f"Total rows: {len(data)}")
    by_country: dict[str, int] = {}
    for r in data:
        by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    for c, n in by_country.items():
        print(f"  {c}: {n}")

    print("\n3 sample rows:")
    for r in data[:3]:
        text = (r.get("content") or "").replace("\n", " ")
        print(
            f"- [{r['country']}] score={r['score']} at={r['at']} "
            f"thumbs={r['thumbsUpCount']}\n    {text[:160]}"
        )


if __name__ == "__main__":
    main()
