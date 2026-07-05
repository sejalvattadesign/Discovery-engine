"""Stage 4 / Phase 4 — theme coding (LLM classification).

Sends each discovery-relevant review (relevant=1) to the LLM in batches and stores a
structured code per review in `coded_reviews`:

    id, themes (JSON array of strings), sentiment, segment, evidence, model

Taxonomy is OPEN (CLAUDE.md §7): the model MAY introduce a new theme when none fit —
that's how the data surprises us. Resumable: only reviews not already in coded_reviews
are sent, so an interrupted/rate-limited run resumes without re-spending tokens.

Default model: openai/gpt-oss-120b on Groq (strong at nuanced coding; its own daily
token bucket, run at reasoning_effort=low to economize). Override with --model.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from llm import active_provider, complete

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reviews.db"

DEFAULT_MODEL = "openai/gpt-oss-120b"
BATCH_SIZE = 15
TEXT_CHARS = 600
SLEEP_SECONDS = 0.3

THEMES = [
    "discovery_friction",        # hard to find/surface new music
    "sameness_fatigue",          # same songs/artists on repeat, stale rotation
    "algorithm_distrust",        # don't trust / dislike what the algorithm picks
    "profile_pollution_fear",    # afraid one play will wreck recommendations
    "intent_expression_gap",     # can't tell Spotify what they actually want
    "context_mood_mismatch",     # recs ignore mood/activity/context
    "passive_discovery_failure", # Discover Weekly/Release Radar/radio underdeliver
    "over_personalization",      # too narrow, trapped in a bubble
]
SEGMENTS = [
    "power_user", "casual_listener", "new_user", "playlist_curator",
    "genre_enthusiast", "passive_listener", "unknown",
]

PROMPT = """You are coding Spotify user reviews about music discovery & recommendations.

For EACH item, return one JSON object with:
- "id": the item's id (copy exactly)
- "themes": array of 1-3 theme labels from this taxonomy (you MAY add ONE new \
snake_case theme if none truly fit):
{themes}
- "sentiment": "positive" | "neutral" | "negative"
- "segment": the user type, inferred from the text, one of:
{segments}
- "evidence": a short verbatim quote (<=120 chars) from the item supporting the themes

Return ONLY a JSON array of these objects, same order as the items. No prose, no fences.

Items:
{items}"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coded_reviews (
            id        TEXT PRIMARY KEY,
            themes    TEXT,
            sentiment TEXT,
            segment   TEXT,
            evidence  TEXT,
            model     TEXT,
            FOREIGN KEY (id) REFERENCES reviews(id)
        )
        """
    )
    conn.commit()


def _parse_json_array(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:120]}")
    return json.loads(raw[start : end + 1])


def classify(model: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    pending = conn.execute(
        """
        SELECT r.id, r.text FROM reviews r
        LEFT JOIN coded_reviews c ON c.id = r.id
        WHERE r.relevant = 1 AND c.id IS NULL
        """
    ).fetchall()
    total = len(pending)
    print(f"[classify] provider={active_provider()} model={model}")
    print(f"[classify] {total} relevant reviews to code, batches of {BATCH_SIZE}")

    themes_block = "\n".join(f"  - {t}" for t in THEMES)
    segments_block = ", ".join(SEGMENTS)
    done = 0

    for i in range(0, total, BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        items = "\n".join(
            f'- id={rid}: "{(text or "")[:TEXT_CHARS].replace(chr(10), " ")}"'
            for rid, text in batch
        )
        prompt = PROMPT.format(
            themes=themes_block, segments=segments_block, items=items
        )
        try:
            resp = complete(
                prompt, max_tokens=4096, model=model, reasoning_effort="low"
            )
            coded = _parse_json_array(resp)
            by_id = {str(c.get("id")): c for c in coded}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "rate_limit" in msg or "429" in msg:
                print(
                    f"  batch {i // BATCH_SIZE}: rate limit — stopping. "
                    f"{total - done} left to code on re-run.\n  {msg[:160]}"
                )
                break
            print(f"  batch {i // BATCH_SIZE}: error {msg[:120]}; skipping batch")
            continue

        for rid, _ in batch:
            c = by_id.get(str(rid))
            if not c:
                continue
            themes = c.get("themes") or []
            if isinstance(themes, str):
                themes = [themes]
            conn.execute(
                """
                INSERT OR REPLACE INTO coded_reviews
                    (id, themes, sentiment, segment, evidence, model)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    json.dumps(themes),
                    (c.get("sentiment") or "").lower() or None,
                    c.get("segment"),
                    (c.get("evidence") or "")[:200],
                    model,
                ),
            )
        conn.commit()
        done += len(batch)
        print(f"  {done}/{total} coded")
        time.sleep(SLEEP_SECONDS)

    summary(conn)
    conn.close()


def summary(conn: sqlite3.Connection) -> None:
    print("\n=== coding summary ===")
    coded = conn.execute("SELECT COUNT(*) FROM coded_reviews").fetchone()[0]
    relevant = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE relevant=1"
    ).fetchone()[0]
    print(f"Coded {coded} / {relevant} relevant")

    print("\nSentiment:")
    for s, n in conn.execute(
        "SELECT sentiment, COUNT(*) FROM coded_reviews GROUP BY sentiment "
        "ORDER BY COUNT(*) DESC"
    ):
        print(f"  {s}: {n}")

    print("\nTop themes:")
    counts: dict[str, int] = {}
    for (themes_json,) in conn.execute("SELECT themes FROM coded_reviews"):
        for t in json.loads(themes_json or "[]"):
            counts[t] = counts.get(t, 0) + 1
    for t, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {n}")

    print("\nSegments:")
    for seg, n in conn.execute(
        "SELECT segment, COUNT(*) FROM coded_reviews GROUP BY segment "
        "ORDER BY COUNT(*) DESC"
    ):
        print(f"  {seg}: {n}")

    print("\n3 sample coded rows:")
    for row in conn.execute(
        "SELECT id, themes, sentiment, segment, evidence FROM coded_reviews "
        "ORDER BY RANDOM() LIMIT 3"
    ):
        rid, themes, sentiment, segment, evidence = row
        print(f"- {sentiment}/{segment} {themes}\n    evidence: {evidence}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Theme-code relevant reviews.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM model id")
    args = parser.parse_args()
    classify(args.model)


if __name__ == "__main__":
    main()
