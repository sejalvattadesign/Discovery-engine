"""Evidence-gated re-segmentation pass.

Fixes the soft power_user/casual_listener boundary from classify.py. The original
single-pass prompt forced a behavioral segment on every review even when the text
carried no signal, inflating casual_listener into a low-signal default bucket.

This pass re-asks the LLM for the SEGMENT ONLY, under a strict rule: assign a
behavioral segment ONLY when the text contains an explicit signal; otherwise return
"unknown". It updates only the `segment` column in coded_reviews — themes, sentiment,
and evidence are left untouched.

    python pipeline/resegment.py            # re-segment all coded reviews
    python pipeline/resegment.py --model openai/gpt-oss-120b

Resumable via a `seg_method` marker: rows already marked "evidence_gated" are skipped.
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
SEG_MARKER = "evidence_gated"

# Each segment now requires an EXPLICIT textual signal. The model must point to that
# signal in "why"; if it can't, it must return "unknown". This is what stops the model
# from guessing "casual_listener" on a one-line review with no behavioral content.
SEGMENT_RULES = """\
- power_user: explicit heavy/long-term use — names tenure ("since 2014", "for years",
  "a decade"), large library ("3000+ songs", "hundreds of playlists"), deep feature use,
  or self-identifies as a long-time/heavy listener.
- new_user: explicitly new — "just downloaded", "just signed up", "first week",
  "new to Spotify", onboarding/first-impression language.
- playlist_curator: focused on BUILDING/ORGANIZING playlists — sorting, ordering,
  curating, "my playlists", complaints about playlist management tools.
- genre_enthusiast: centered on a specific genre/language/scene — names genres or
  languages ("Kannada songs", "metal", "K-pop"), wants genre/language filtering.
- passive_listener: explicitly lean-back — "just hit play", "let it run", background/
  radio listening, doesn't want to actively choose.
- casual_listener: shows light/occasional engagement signal but none of the above —
  ONLY use when there is a genuine casual-use signal, NOT as a default.
- unknown: USE THIS whenever the text gives no clear behavioral signal about the user.
  A short or generic complaint about the app with no personal usage detail is "unknown".
"""

PROMPT = """You are inferring the USER TYPE behind each Spotify review, for behavioral \
segmentation. This must be EVIDENCE-GATED: assign a behavioral segment ONLY when the \
review text contains an explicit signal for it. If the text gives no clear signal about \
who the user is, you MUST return "unknown". Do not guess. Do not default to \
"casual_listener".

Segment definitions (each needs an explicit textual signal):
{rules}

For EACH item return one JSON object:
- "id": copy the id exactly
- "segment": one label from the list above
- "why": <=100 chars — the EXACT phrase/signal in the text that justifies it. If you
  write "unknown", "why" must be "no behavioral signal".

Return ONLY a JSON array, same order as the items. No prose, no code fences.

Items:
{items}"""


def _parse_json_array(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:120]}")
    return json.loads(raw[start : end + 1])


def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(coded_reviews)")}
    if "seg_method" not in cols:
        conn.execute("ALTER TABLE coded_reviews ADD COLUMN seg_method TEXT")
    if "seg_why" not in cols:
        conn.execute("ALTER TABLE coded_reviews ADD COLUMN seg_why TEXT")
    conn.commit()


def resegment(model: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)

    pending = conn.execute(
        """
        SELECT c.id, r.text
        FROM coded_reviews c JOIN reviews r ON c.id = r.id
        WHERE c.seg_method IS NULL OR c.seg_method != ?
        """,
        (SEG_MARKER,),
    ).fetchall()
    total = len(pending)
    print(f"[resegment] provider={active_provider()} model={model}")
    print(f"[resegment] {total} reviews to re-segment, batches of {BATCH_SIZE}")
    done = 0

    for i in range(0, total, BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        items = "\n".join(
            f'- id={rid}: "{(text or "")[:TEXT_CHARS].replace(chr(10), " ")}"'
            for rid, text in batch
        )
        prompt = PROMPT.format(rules=SEGMENT_RULES, items=items)
        try:
            resp = complete(prompt, max_tokens=2200, model=model, reasoning_effort="low")
            coded = _parse_json_array(resp)
            by_id = {str(c.get("id")): c for c in coded}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "rate_limit" in msg or "429" in msg:
                print(f"  batch {i // BATCH_SIZE}: rate limit — stopping. "
                      f"{total - done} left on re-run.\n  {msg[:160]}")
                break
            print(f"  batch {i // BATCH_SIZE}: error {msg[:120]}; skipping")
            continue

        for rid, _ in batch:
            c = by_id.get(str(rid))
            if not c:
                continue
            conn.execute(
                "UPDATE coded_reviews SET segment=?, seg_why=?, seg_method=? WHERE id=?",
                (
                    (c.get("segment") or "unknown").strip().lower(),
                    (c.get("why") or "")[:120],
                    SEG_MARKER,
                    rid,
                ),
            )
        conn.commit()
        done += len(batch)
        print(f"  {done}/{total} re-segmented")
        time.sleep(SLEEP_SECONDS)

    summary(conn)
    conn.close()


def summary(conn: sqlite3.Connection) -> None:
    print("\n=== re-segmentation summary ===")
    rows = conn.execute(
        "SELECT segment, COUNT(*) FROM coded_reviews GROUP BY segment ORDER BY COUNT(*) DESC"
    ).fetchall()
    total = sum(n for _, n in rows)
    for seg, n in rows:
        print(f"  {seg:18} {n:3}  ({round(n / total * 100)}%)")

    print("\n3 sample evidence-gated rows:")
    for seg, why in conn.execute(
        "SELECT segment, seg_why FROM coded_reviews "
        "WHERE seg_method=? ORDER BY RANDOM() LIMIT 5", (SEG_MARKER,)
    ):
        print(f"  {seg:18} ← {why}")


def main() -> None:
    p = argparse.ArgumentParser(description="Evidence-gated re-segmentation.")
    p.add_argument("--model", default=DEFAULT_MODEL)
    resegment(p.parse_args().model)


if __name__ == "__main__":
    main()
