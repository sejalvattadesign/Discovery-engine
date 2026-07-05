"""Stage 1 / Phase 1 — Reddit scraper (PullPush archive, NO credentials).

Reddit blocked its no-auth `.json` endpoints (403) and PRAW needs a registered app.
To avoid the credential dependency entirely, this uses **PullPush** (https://pullpush.io),
the free community successor to Pushshift — a Reddit archive with an open REST API that
needs no login, no app, no keys.

We pull BOTH submissions and comments matching discovery queries in r/spotify and
r/truespotify, normalize to the shared row shape, dedupe, and cache. The rest of the
pipeline (load → filter → classify → JTBD) is unchanged.

    python scrape/reddit.py --refresh

Row shape (one row per submission AND per comment):
    id, kind (submission|comment), subreddit, title, text, score, created_utc (ISO),
    permalink, query
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "reddit.json"

SUBREDDITS = ["spotify", "truespotify"]
QUERIES = [
    "discover weekly",
    "algorithm",
    "recommendations",
    "same songs",
    "repetitive",
    "filter bubble",
    "discover",
    "release radar",
]
SIZE = 100                 # max rows per query per endpoint
SLEEP_SECONDS = 1.5        # be polite to the free archive
UA = "spotify-discovery-research/0.1 (review analysis)"
BASE = "https://api.pullpush.io/reddit/search"


def _iso(created_utc) -> str | None:
    if created_utc is None:
        return None
    try:
        return datetime.fromtimestamp(int(created_utc), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _get(kind: str, subreddit: str, query: str) -> list[dict]:
    """kind = 'submission' | 'comment'."""
    url = f"{BASE}/{kind}/"
    params = {"q": query, "subreddit": subreddit, "size": SIZE}
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 429:
                print("  rate-limited (429); backing off 20s")
                time.sleep(20)
                continue
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as exc:  # noqa: BLE001 — keep the crawl going
            print(f"  {kind} request failed (try {attempt + 1}): {exc}")
            time.sleep(5)
    return []


def scrape(refresh: bool = False) -> list[dict]:
    if RAW_PATH.exists() and RAW_PATH.stat().st_size > 2 and not refresh:
        print(f"Cache hit: {RAW_PATH} (use --refresh to re-scrape)")
        return json.loads(RAW_PATH.read_text())

    rows: list[dict] = []
    seen: set[str] = set()

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            # submissions
            subs = _get("submission", subreddit, query)
            print(f"[r/{subreddit}] {query!r}: {len(subs)} submissions")
            for d in subs:
                sid = d.get("id")
                if not sid or f"s_{sid}" in seen:
                    continue
                seen.add(f"s_{sid}")
                text = (d.get("selftext") or "").strip()
                if text in ("[deleted]", "[removed]"):
                    text = ""
                rows.append({
                    "id": sid, "kind": "submission", "subreddit": subreddit,
                    "title": d.get("title"), "text": text,
                    "score": d.get("score"),
                    "created_utc": _iso(d.get("created_utc")),
                    "permalink": d.get("permalink"), "query": query,
                })
            time.sleep(SLEEP_SECONDS)

            # comments (rich opinion text — great for discovery feedback)
            comments = _get("comment", subreddit, query)
            print(f"[r/{subreddit}] {query!r}: {len(comments)} comments")
            for d in comments:
                cid = d.get("id")
                body = (d.get("body") or "").strip()
                if not cid or f"c_{cid}" in seen or body in ("", "[deleted]", "[removed]"):
                    continue
                seen.add(f"c_{cid}")
                rows.append({
                    "id": cid, "kind": "comment", "subreddit": subreddit,
                    "title": None, "text": body,
                    "score": d.get("score"),
                    "created_utc": _iso(d.get("created_utc")),
                    "permalink": d.get("permalink"), "query": query,
                })
            time.sleep(SLEEP_SECONDS)

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"Wrote {len(rows)} rows -> {RAW_PATH}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Spotify Reddit posts (PullPush, no auth).")
    parser.add_argument("--refresh", action="store_true", help="ignore cache")
    data = scrape(refresh=parser.parse_args().refresh)

    print("\n=== Reddit scrape summary ===")
    print(f"Total rows: {len(data)}")
    by_kind: dict[str, int] = {}
    by_sub: dict[str, int] = {}
    for r in data:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        by_sub[r["subreddit"]] = by_sub.get(r["subreddit"], 0) + 1
    print(f"  by kind: {by_kind}")
    print(f"  by subreddit: {by_sub}")

    print("\n3 sample rows:")
    for r in data[:3]:
        text = (r.get("text") or r.get("title") or "").replace("\n", " ")
        print(f"- [{r['kind']} r/{r['subreddit']}] score={r['score']} at={r['created_utc']}\n    {text[:160]}")


if __name__ == "__main__":
    main()
