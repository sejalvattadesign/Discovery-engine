"""Stage 3 / Phase 3 — filter the corpus down to discovery-relevant reviews.

Two passes (CLAUDE.md §6) so real themes aren't drowned in "app keeps crashing" noise:

  Pass 1 — keyword prefilter (free): rows that mention no discovery-related keyword are
           dropped immediately (relevant=0). The rest become "candidates".
  Pass 2 — LLM relevance (Claude Haiku): each candidate gets a yes/no on whether it's
           actually about discovering new music / the recommendation experience.

Results are written back to the `reviews` table:
    relevant       INTEGER  (1 = keep, 0 = drop)
    relevance_pass TEXT     (keyword_drop | llm_yes | llm_no | llm_error)

Resumable & idempotent: only rows with relevant IS NULL are processed, so an interrupted
run never re-spends tokens. Run again to continue where it left off.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path

from llm import active_provider, complete, model_name

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reviews.db"

BATCH_SIZE = 40
TEXT_CHARS = 250
SLEEP_SECONDS = 0.3

# Pass 1 keyword set (CLAUDE.md §6, lightly expanded).
KEYWORDS = [
    "discover", "discovery", "discover weekly", "recommend", "recommendation",
    "suggest", "suggestion", "algorithm", "playlist", "repetitive", "repeat",
    "same song", "same music", "same artist", "new music", "new artist", "radio",
    "release radar", "daylist", "autoplay", "shuffle", "for you", "made for you",
    "taste", "variety", "fresh", "explore",
]
_KEYWORD_RE = re.compile("|".join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)

PROMPT = """You are screening user reviews/comments about the Spotify app.

For EACH item below, decide if it is about DISCOVERING NEW MUSIC or the RECOMMENDATION \
EXPERIENCE. That includes: Discover Weekly / Release Radar / radio / autoplay quality, \
the recommendation algorithm, repetitive listening or hearing the same songs/artists, \
trouble finding new music, music variety/taste, personalization, playlist suggestions.

It does NOT include unrelated complaints: billing/price, ads, crashes/bugs, login, \
audio quality/bitrate, podcasts, account issues, UI gripes with no discovery angle.

Return ONLY a JSON array, one object per item, in the same order:
[{{"id": "<id>", "relevant": true|false}}]
No prose, no markdown fences.

Items:
{items}"""


def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(reviews)")}
    if "relevant" not in cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN relevant INTEGER")
    if "relevance_pass" not in cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN relevance_pass TEXT")
    conn.commit()


def keyword_pass(conn: sqlite3.Connection) -> int:
    """Drop rows with no keyword hit. Returns number of candidates remaining."""
    rows = conn.execute(
        "SELECT id, text FROM reviews WHERE relevant IS NULL"
    ).fetchall()
    dropped = 0
    for rid, text in rows:
        if not _KEYWORD_RE.search(text or ""):
            conn.execute(
                "UPDATE reviews SET relevant=0, relevance_pass='keyword_drop' "
                "WHERE id=?",
                (rid,),
            )
            dropped += 1
    conn.commit()
    candidates = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE relevant IS NULL"
    ).fetchone()[0]
    print(f"[pass 1] keyword: dropped {dropped}, {candidates} candidates remain")
    return candidates


def _parse_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:120]}")
    return json.loads(raw[start : end + 1])


def llm_pass(conn: sqlite3.Connection) -> None:
    """Classify keyword-surviving candidates via the LLM wrapper, in batches."""
    print(f"[pass 2] provider={active_provider()} model={model_name()}")

    candidates = conn.execute(
        "SELECT id, text FROM reviews WHERE relevant IS NULL"
    ).fetchall()
    total = len(candidates)
    print(f"[pass 2] LLM: classifying {total} candidates in batches of {BATCH_SIZE}")

    done = 0
    for i in range(0, total, BATCH_SIZE):
        batch = candidates[i : i + BATCH_SIZE]
        items = "\n".join(
            f'- id={rid}: "{(text or "")[:TEXT_CHARS].replace(chr(10), " ")}"'
            for rid, text in batch
        )
        try:
            text_resp = complete(PROMPT.format(items=items), max_tokens=2048)
            verdicts = _parse_json_array(text_resp)
            by_id = {str(v.get("id")): bool(v.get("relevant")) for v in verdicts}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            # On a rate-limit/quota error, STOP cleanly and leave rows undecided
            # (relevant stays NULL) so a later re-run retries them — never drop them.
            if "rate_limit" in msg or "429" in msg:
                print(
                    f"  batch {i // BATCH_SIZE}: rate limit hit — stopping. "
                    f"{total - done} candidates left undecided for re-run.\n  {msg[:160]}"
                )
                return
            print(f"  batch {i // BATCH_SIZE}: error {msg[:120]}; leaving undecided")
            continue

        for rid, _ in batch:
            keep = by_id.get(str(rid))
            if keep is None:
                conn.execute(
                    "UPDATE reviews SET relevant=0, relevance_pass='llm_error' "
                    "WHERE id=?",
                    (rid,),
                )
            else:
                conn.execute(
                    "UPDATE reviews SET relevant=?, relevance_pass=? WHERE id=?",
                    (1 if keep else 0, "llm_yes" if keep else "llm_no", rid),
                )
        conn.commit()
        done += len(batch)
        print(f"  {done}/{total} classified")
        time.sleep(SLEEP_SECONDS)


def summary(conn: sqlite3.Connection) -> None:
    print("\n=== relevance summary ===")
    total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    kept = conn.execute("SELECT COUNT(*) FROM reviews WHERE relevant=1").fetchone()[0]
    dropped = conn.execute("SELECT COUNT(*) FROM reviews WHERE relevant=0").fetchone()[0]
    undecided = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE relevant IS NULL"
    ).fetchone()[0]
    print(f"Total {total} | kept {kept} | dropped {dropped} | undecided {undecided}")

    print("\nBy pass:")
    for pass_name, n in conn.execute(
        "SELECT relevance_pass, COUNT(*) FROM reviews GROUP BY relevance_pass"
    ):
        print(f"  {pass_name}: {n}")

    print("\nKept by source:")
    for source, n in conn.execute(
        "SELECT source, COUNT(*) FROM reviews WHERE relevant=1 "
        "GROUP BY source ORDER BY COUNT(*) DESC"
    ):
        print(f"  {source}: {n}")

    print("\n3 sample KEPT rows:")
    for source, text in conn.execute(
        "SELECT source, substr(text,1,150) FROM reviews WHERE relevant=1 "
        "ORDER BY RANDOM() LIMIT 3"
    ):
        print(f"- [{source}] {text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter discovery-relevant reviews.")
    parser.add_argument(
        "--keyword-only", action="store_true",
        help="run only the free keyword pass (skip the LLM pass)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)
    keyword_pass(conn)
    if not args.keyword_only:
        llm_pass(conn)
    summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
