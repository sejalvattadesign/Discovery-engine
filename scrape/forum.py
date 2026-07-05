"""Stage 1 / Phase 1 — Spotify Community forum scraper.

community.spotify.com runs on Khoros/Lithium. We:
  1. Hit the public search page for each discovery-related query.
  2. Collect unique thread permalinks (`/m-p/<id>`) from the results.
  3. Fetch each thread and extract every message body + its posted date.

This is the no-credentials 3rd source (the brief marks the forum optional/fragile, so
we degrade gracefully and never block on it). Per the ethics note in CLAUDE.md §10 we
do NOT store usernames — only the discussion text, date, board, and URL.

Cache-first: existing cache is reused unless --refresh.

Cached item shape (one row per message within a matched thread):
    id, kind (thread|reply), board, title, text, date (ISO-ish), url, query
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://community.spotify.com"
QUERIES = [
    "discover weekly",
    "recommendations",
    "algorithm",
    "same songs repetitive",
    "release radar",
    "discover new music",
    "filter bubble",
]
SEARCH_PAGES = 2          # result pages per query
THREADS_PER_QUERY = 12    # cap threads fetched per query
SLEEP_SECONDS = 1.5
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
)

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "forum.json"

_ID_RE = re.compile(r"/m-p/(\d+)")
_BOARD_RE = re.compile(r"/t5/([^/]+)/")


def _get(url: str, params: dict | None = None) -> str | None:
    try:
        resp = requests.get(
            url, params=params, headers={"User-Agent": UA}, timeout=25
        )
        resp.raise_for_status()
        return resp.text
    except Exception as exc:  # noqa: BLE001 - fragile HTML/site, keep going
        print(f"  request failed: {exc}")
        return None


def _parse_date(raw: str) -> str:
    """Normalize Khoros '2024-11-18 06:07 AM' -> ISO date; fall back to raw."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %I:%M %p", "%m-%d-%Y %I:%M %p", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return raw


def search_threads(query: str) -> list[str]:
    """Return unique thread URLs for a query across SEARCH_PAGES.

    Each reply in a thread has its own `/m-p/<id>` permalink, but they all render the
    same thread page. So we dedupe on the thread SLUG (the path before `/m-p/`), not on
    the message id — otherwise we'd fetch (and duplicate) the same thread many times.
    """
    found: dict[str, str] = {}  # thread slug -> clean url
    for page in range(1, SEARCH_PAGES + 1):
        url = f"{BASE}/t5/forums/searchpage/tab/message"
        html = _get(url, {"q": query, "page": page, "collapse_discussion": "true"})
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/m-p/" not in href:
                continue
            # strip fragment / query / highlight suffix to a clean permalink
            clean = href.split("?")[0].split("#")[0].replace("/highlight/true", "")
            slug = clean.split("/m-p/")[0]  # /t5/Board/Title-slug -> thread identity
            if slug in found:
                continue
            if clean.startswith("/"):
                clean = BASE + clean
            found[slug] = clean
            if len(found) >= THREADS_PER_QUERY:
                return list(found.values())
        time.sleep(SLEEP_SECONDS)
    return list(found.values())


def fetch_thread(url: str, query: str) -> list[dict]:
    """Extract every message (op + replies) from a thread page."""
    html = _get(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = (title_tag.text if title_tag else "").replace(
        " - The Spotify Community", ""
    ).replace("Solved: ", "").strip()

    board_m = _BOARD_RE.search(url)
    board = board_m.group(1) if board_m else None
    # stable thread key = the title-slug segment (last path part before /m-p/)
    thread_id = url.split("/m-p/")[0].rstrip("/").split("/")[-1] or url

    rows: list[dict] = []
    bodies = soup.select(".lia-message-body-content")
    for idx, body in enumerate(bodies):
        text = body.get_text(" ", strip=True)
        if not text:
            continue
        # find the posted date within this message's container
        container = body.find_parent(
            class_=re.compile(r"lia-message-view|MessageView")
        )
        date_raw = None
        if container:
            date_node = container.select_one(".local-date, .DateTime, .lia-message-posted-on")
            if date_node:
                date_raw = date_node.get_text(" ", strip=True)
        rows.append(
            {
                "id": f"{thread_id}-{idx}",
                "kind": "thread" if idx == 0 else "reply",
                "board": board,
                "title": title,
                "text": text,
                "date": _parse_date(date_raw) if date_raw else None,
                "url": url,
                "query": query,
            }
        )
    return rows


def scrape(refresh: bool = False) -> list[dict]:
    if RAW_PATH.exists() and not refresh:
        print(f"Cache hit: {RAW_PATH} (use --refresh to re-scrape)")
        return json.loads(RAW_PATH.read_text())

    rows: list[dict] = []
    seen_threads: set[str] = set()
    for query in QUERIES:
        print(f"[forum] search: {query!r}")
        threads = search_threads(query)
        print(f"  {len(threads)} threads")
        for turl in threads:
            slug = turl.split("/m-p/")[0]  # thread identity, stable across queries
            if slug in seen_threads:
                continue
            seen_threads.add(slug)
            thread_rows = fetch_thread(turl, query)
            rows.extend(thread_rows)
            print(f"    {turl.split('/m-p/')[0].split('/')[-1][:40]}: {len(thread_rows)} msgs")
            time.sleep(SLEEP_SECONDS)

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"Wrote {len(rows)} rows -> {RAW_PATH}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Spotify Community forum.")
    parser.add_argument("--refresh", action="store_true", help="ignore cache")
    args = parser.parse_args()

    data = scrape(refresh=args.refresh)

    print("\n=== Forum scrape summary ===")
    print(f"Total rows: {len(data)}")
    by_kind: dict[str, int] = {}
    threads = set()
    for r in data:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        threads.add(r["id"].rsplit("-", 1)[0])  # strip trailing -<idx>
    print(f"  by kind: {by_kind}")
    print(f"  unique threads: {len(threads)}")

    print("\n3 sample rows:")
    for r in data[:3]:
        text = (r.get("text") or "").replace("\n", " ")
        print(
            f"- [{r['kind']} {r['board']}] date={r['date']}\n"
            f"    title={r['title'][:70]!r}\n    {text[:160]}"
        )


if __name__ == "__main__":
    main()
