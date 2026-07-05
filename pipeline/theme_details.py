"""Precompute per-theme drill-down details → web/lib/theme_details.ts

For each of the 8 canonical themes: pulls the real reviews tagged with it, computes
deterministic stats (count, % negative, source split), samples representative quotes,
and asks the LLM ONCE for a cited sub-problem synthesis ("what is this theme actually
about?"). Baked into the dashboard so theme drill-downs are instant + verifiable.

    python pipeline/theme_details.py --model openai/gpt-oss-120b
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from llm import complete

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "reviews.db"
OUT = ROOT / "web" / "lib" / "theme_details.ts"

THEME_LABELS = {
    "algorithm_distrust":        "Algorithm distrust",
    "discovery_friction":        "Discovery friction",
    "over_personalization":      "Over-personalization",
    "sameness_fatigue":          "Sameness fatigue",
    "intent_expression_gap":     "Intent expression gap",
    "passive_discovery_failure": "Passive discovery failure",
    "profile_pollution_fear":    "Profile pollution fear",
    "context_mood_mismatch":     "Context / mood mismatch",
}
THEME_DEFINITIONS = {
    "algorithm_distrust":        "Users don't trust what the algorithm serves — suspecting promotion/payola, unlabeled AI, or a black box they can't see into.",
    "discovery_friction":        "It's hard to find or surface genuinely new music; discovery takes effort or doesn't happen at all.",
    "over_personalization":      "Recommendations are too narrow — users feel trapped in a bubble of the already-familiar.",
    "sameness_fatigue":          "The same songs and artists repeat; the rotation feels stale and predictable.",
    "intent_expression_gap":     "Users can't tell Spotify what they actually want right now — no way to express in-the-moment intent.",
    "passive_discovery_failure": "The automated surfaces (Discover Weekly, Release Radar, radio) under-deliver on novelty.",
    "profile_pollution_fear":    "Users fear one play — or even a skip — will wreck their recommendations and long-term taste profile.",
    "context_mood_mismatch":     "Recommendations ignore the user's mood, activity, or listening context.",
}
SOURCE_LABELS = {"play_store": "Play Store", "app_store": "App Store",
                 "forum": "Community Forum", "reddit": "Reddit"}

SUMMARY_PROMPT = """You are analyzing Spotify reviews all tagged with the theme \
"{label}" ({definition}). From the numbered reviews below, identify the 3-5 DISTINCT \
sub-problems within this theme. For each, give a short name and one sentence, citing the \
reviews with [n]. Be specific to what users actually say. Return concise markdown bullets \
only (no preamble).

REVIEWS:
{context}

Sub-problems (cited):"""


def fetch_theme_rows(conn, key):
    rows = conn.execute(
        "SELECT c.id, c.themes, c.sentiment, r.text, r.source, r.date, r.rating "
        "FROM coded_reviews c JOIN reviews r ON c.id = r.id WHERE r.relevant = 1"
    ).fetchall()
    out = []
    for id_, themes_json, sentiment, text, source, date, rating in rows:
        try:
            themes = json.loads(themes_json or "[]")
        except json.JSONDecodeError:
            themes = []
        if key in themes:
            out.append({"id": id_, "sentiment": sentiment, "text": (text or "").strip(),
                        "source": source, "date": date, "rating": rating})
    return out


def pick_quotes(rows, n=8):
    # concise but substantive, punchy quotes: 40-240 chars, dedup, prefer variety of sources
    cand = [r for r in rows if 40 <= len(r["text"]) <= 240]
    cand.sort(key=lambda r: (r["source"], -(r["rating"] or 0)))
    seen_src, picked = {}, []
    for r in cand:
        if seen_src.get(r["source"], 0) >= 3:
            continue
        seen_src[r["source"]] = seen_src.get(r["source"], 0) + 1
        picked.append(r)
        if len(picked) >= n:
            break
    return picked or cand[:n]


def esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-oss-120b")
    model = ap.parse_args().model

    conn = sqlite3.connect(DB)
    details = {}

    for key, label in THEME_LABELS.items():
        rows = fetch_theme_rows(conn, key)
        if not rows:
            continue
        count = len(rows)
        neg_pct = round(sum(r["sentiment"] == "negative" for r in rows) / count * 100)
        src_counts = {}
        for r in rows:
            src_counts[r["source"]] = src_counts.get(r["source"], 0) + 1
        sources = [{"source": SOURCE_LABELS.get(s, s), "n": n}
                   for s, n in sorted(src_counts.items(), key=lambda x: -x[1])]

        quotes = pick_quotes(rows, 8)
        context = "\n".join(
            f'[{i+1}] ({q["source"]}) "{q["text"][:220]}"' for i, q in enumerate(quotes)
        )
        try:
            summary = complete(
                SUMMARY_PROMPT.format(label=label, definition=THEME_DEFINITIONS[key],
                                      context=context),
                max_tokens=600, model=model, reasoning_effort="low",
            ).strip()
        except Exception as exc:  # noqa: BLE001
            print(f"  {key}: summary failed ({str(exc)[:80]}) — leaving blank")
            summary = ""

        details[label] = {
            "key": key, "label": label, "definition": THEME_DEFINITIONS[key],
            "count": count, "negPct": neg_pct, "sources": sources,
            "summary": summary,
            "quotes": [{
                "n": i + 1, "snippet": q["text"][:240], "source": SOURCE_LABELS.get(q["source"], q["source"]),
                "date": str(q["date"] or ""), "rating": q["rating"], "segment": "",
            } for i, q in enumerate(quotes)],
        }
        print(f"  {key}: {count} reviews, {len(quotes)} quotes, summary {'ok' if summary else 'blank'}")

    conn.close()

    # render TS
    ts = ["// AUTO-GENERATED by pipeline/theme_details.py — per-theme drill-down data.",
          "export interface ThemeQuote { n: number; snippet: string; source: string; date: string; rating: number | null; segment: string; }",
          "export interface ThemeDetail { key: string; label: string; definition: string; count: number; negPct: number; sources: {source:string;n:number}[]; summary: string; quotes: ThemeQuote[]; }",
          "export const THEME_DETAILS: Record<string, ThemeDetail> = " + json.dumps(details, ensure_ascii=False, indent=2) + ";"]
    OUT.write_text("\n\n".join(ts))
    print(f"✓ Wrote {len(details)} theme details → {OUT}")


if __name__ == "__main__":
    main()
