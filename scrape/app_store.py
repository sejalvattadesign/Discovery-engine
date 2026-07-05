"""Stage 1 / Phase 1 — App Store scraper.

Pulls Spotify reviews (app id 324684580) from the Apple App Store for the IN and US
storefronts and caches the combined result to `data/raw/app_store.json`.

Background: the documented approaches in CLAUDE.md no longer work as written —
  * `app-store-scraper` is dead: it scrapes a bearer token from a page meta tag Apple
    removed, so it returns 0 reviews.
  * Apple's legacy iTunes customer-reviews RSS feed is deprecated globally (HTTP 200 but
    zero entries for every app).

Working approach used here — Apple's modern storefront API (`amp-api-edge`):
  1. Load the public App Store web page for the app.
  2. Extract the ES256 media JWT embedded in the page's main JS bundle.
  3. Page through `amp-api-edge.apps.apple.com/.../reviews` with that bearer token.
     (Note: the `amp-api-edge` host works; the plain `amp-api` host returns 401.)

Cache-first: existing cache is reused unless --refresh.

Cached item shape:
    reviewId, title, content, score, at (ISO), country
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

APP_ID = "324684580"
COUNTRIES = ["in", "us"]
TARGET_PER_COUNTRY = 500
PAGE_LIMIT = 20            # max the reviews endpoint returns per call
SLEEP_SECONDS = 0.7
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
)
API_HOST = "https://amp-api-edge.apps.apple.com"

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "app_store.json"


def get_token(country: str) -> str:
    """Scrape the Apple media JWT bearer token from the app page's JS bundle."""
    page_url = f"https://apps.apple.com/{country}/app/id{APP_ID}"
    page = requests.get(page_url, headers={"User-Agent": UA}, timeout=20).text
    js_match = re.search(r'src="(/assets/index~[^"]+\.js)"', page)
    if not js_match:
        raise RuntimeError("could not locate JS bundle on App Store page")
    js = requests.get(
        "https://apps.apple.com" + js_match.group(1),
        headers={"User-Agent": UA},
        timeout=20,
    ).text
    token_match = re.search(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", js)
    if not token_match:
        raise RuntimeError("could not locate bearer token in JS bundle")
    return token_match.group(0)


def fetch_country(country: str, token: str, target: int = TARGET_PER_COUNTRY) -> list[dict]:
    """Page through the reviews endpoint for one storefront up to `target` items."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://apps.apple.com",
        "User-Agent": UA,
        "Accept": "application/json",
    }
    out: list[dict] = []
    offset = 0
    print(f"[{country}] amp-api-edge reviews ...")
    while len(out) < target:
        url = f"{API_HOST}/v1/catalog/{country}/apps/{APP_ID}/reviews"
        params = {
            "l": "en-US",
            "offset": offset,
            "limit": PAGE_LIMIT,
            "platform": "web",
            "additionalPlatforms": "appletv,ipad,iphone,mac",
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - flaky network/host, stop this country
            print(f"[{country}] request failed at offset {offset}: {exc}")
            break

        data = payload.get("data", [])
        if not data:
            print(f"[{country}] no more reviews at offset {offset}")
            break

        for item in data:
            attr = item.get("attributes", {})
            out.append(
                {
                    "reviewId": item.get("id"),
                    "title": attr.get("title"),
                    "content": attr.get("review"),
                    "score": attr.get("rating"),
                    "at": attr.get("date"),
                    "country": country,
                }
            )
        print(f"[{country}] collected {len(out)}")

        # Apple paginates via a `next` link; stop when it disappears.
        if not payload.get("next"):
            print(f"[{country}] reached end of pagination at {len(out)}")
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_SECONDS)
    return out


def scrape(refresh: bool = False) -> list[dict]:
    if RAW_PATH.exists() and not refresh:
        print(f"Cache hit: {RAW_PATH} (use --refresh to re-scrape)")
        return json.loads(RAW_PATH.read_text())

    all_reviews: list[dict] = []
    for country in COUNTRIES:
        try:
            token = get_token(country)
        except Exception as exc:  # noqa: BLE001
            print(f"[{country}] token fetch failed: {exc}; skipping")
            continue
        all_reviews.extend(fetch_country(country, token))

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(all_reviews, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_reviews)} reviews -> {RAW_PATH}")
    return all_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Spotify App Store reviews.")
    parser.add_argument("--refresh", action="store_true", help="ignore cache")
    args = parser.parse_args()

    data = scrape(refresh=args.refresh)

    print("\n=== App Store scrape summary ===")
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
            f"title={r.get('title')!r}\n    {text[:160]}"
        )


if __name__ == "__main__":
    main()
