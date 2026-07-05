"""Job-to-be-done (JTBD) coding pass.

Segments reviews by the GOAL the user was pursuing — not by who they are. Goals appear
in review text far more often than identity, so coverage is much higher than the
evidence-gated persona pass (~70-80% vs 30%). This gives a defensible "segments by need"
view for the dashboard + deck.

Writes a `jtbd` and `jtbd_why` column on coded_reviews. Evidence-gated: if the text
doesn't reveal a goal, returns "unclear". Resumable via jtbd_method marker.

    python pipeline/classify_jtbd.py --model openai/gpt-oss-120b
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
JTBD_MARKER = "v1"

# Jobs-to-be-done for music discovery — the goal behind the listening session.
JOBS = """\
- find_new_music: actively trying to discover new artists/songs/genres they don't know yet.
- build_playlist: creating, organizing, sorting, or maintaining their own playlists.
- background_listening: lean-back — wants something good playing without choosing; radio/autoplay.
- mood_or_activity: music for a specific context — workout, study, sleep, commute, party, focus.
- replay_favorites: wants to hear music they already know and love, on demand.
- steer_algorithm: trying to fix/control/tune what the algorithm recommends to them.
- unclear: the text does not reveal what the user was trying to do.
"""

PROMPT = """You are coding Spotify reviews by the JOB-TO-BE-DONE — the goal the user was \
pursuing when the experience frustrated (or pleased) them. Infer the goal from what the \
text describes the user DOING or WANTING, not from who they are. Be evidence-based: if the \
text does not reveal a goal, return "unclear". Do not guess.

Jobs (pick the single best fit):
{jobs}

For EACH item return one JSON object:
- "id": copy the id exactly
- "jtbd": one label from the list above
- "why": <=100 chars — the exact phrase/signal in the text. If "unclear", write "no goal signal".

Return ONLY a JSON array, same order as items. No prose, no code fences.

Items:
{items}"""


def _parse_json_array(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    s, e = raw.find("["), raw.rfind("]")
    if s == -1 or e == -1:
        raise ValueError(f"no JSON array: {raw[:120]}")
    return json.loads(raw[s : e + 1])


def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(coded_reviews)")}
    if "jtbd" not in cols:
        conn.execute("ALTER TABLE coded_reviews ADD COLUMN jtbd TEXT")
    if "jtbd_why" not in cols:
        conn.execute("ALTER TABLE coded_reviews ADD COLUMN jtbd_why TEXT")
    if "jtbd_method" not in cols:
        conn.execute("ALTER TABLE coded_reviews ADD COLUMN jtbd_method TEXT")
    conn.commit()


def run(model: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)
    pending = conn.execute(
        "SELECT c.id, r.text FROM coded_reviews c JOIN reviews r ON c.id=r.id "
        "WHERE c.jtbd_method IS NULL OR c.jtbd_method != ?",
        (JTBD_MARKER,),
    ).fetchall()
    total = len(pending)
    print(f"[jtbd] provider={active_provider()} model={model}")
    print(f"[jtbd] {total} reviews to code, batches of {BATCH_SIZE}")
    done = 0

    for i in range(0, total, BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        items = "\n".join(
            f'- id={rid}: "{(text or "")[:TEXT_CHARS].replace(chr(10), " ")}"'
            for rid, text in batch
        )
        prompt = PROMPT.format(jobs=JOBS, items=items)
        try:
            resp = complete(prompt, max_tokens=2200, model=model, reasoning_effort="low")
            by_id = {str(c.get("id")): c for c in _parse_json_array(resp)}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "rate_limit" in msg or "429" in msg:
                print(f"  batch {i // BATCH_SIZE}: rate limit — stopping. "
                      f"{total - done} left on re-run.\n  {msg[:140]}")
                break
            print(f"  batch {i // BATCH_SIZE}: error {msg[:110]}; skipping")
            continue

        for rid, _ in batch:
            c = by_id.get(str(rid))
            if not c:
                continue
            conn.execute(
                "UPDATE coded_reviews SET jtbd=?, jtbd_why=?, jtbd_method=? WHERE id=?",
                ((c.get("jtbd") or "unclear").strip().lower(),
                 (c.get("why") or "")[:120], JTBD_MARKER, rid),
            )
        conn.commit()
        done += len(batch)
        print(f"  {done}/{total} coded")
        time.sleep(SLEEP_SECONDS)

    print("\n=== JTBD distribution ===")
    rows = conn.execute(
        "SELECT jtbd, COUNT(*) FROM coded_reviews GROUP BY jtbd ORDER BY COUNT(*) DESC"
    ).fetchall()
    tot = sum(n for _, n in rows)
    for j, n in rows:
        print(f"  {j or '(none)':20} {n:3} ({round(n / tot * 100)}%)")
    conn.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL)
    run(p.parse_args().model)


if __name__ == "__main__":
    main()
