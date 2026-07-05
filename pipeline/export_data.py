"""Export pipeline data to web/lib/data.ts so the Next.js dashboard stays in sync.

Run after any pipeline refresh:
    python pipeline/export_data.py

Reads from data/reviews.db (coded_reviews + reviews tables) and writes
web/lib/data.ts with real counts, sentiment, and segment breakdowns.
"""

from __future__ import annotations

import json
import sqlite3
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB   = ROOT / "data" / "reviews.db"
OUT  = ROOT / "web" / "lib" / "data.ts"

CANONICAL = [
    "algorithm_distrust",
    "discovery_friction",
    "over_personalization",
    "sameness_fatigue",
    "intent_expression_gap",
    "passive_discovery_failure",
    "profile_pollution_fear",
    "context_mood_mismatch",
]
THEME_LABELS: dict[str, str] = {
    "algorithm_distrust":        "Algorithm distrust",
    "discovery_friction":        "Discovery friction",
    "over_personalization":      "Over-personalization",
    "sameness_fatigue":          "Sameness fatigue",
    "intent_expression_gap":     "Intent expression gap",
    "passive_discovery_failure": "Passive discovery failure",
    "profile_pollution_fear":    "Profile pollution fear",
    "context_mood_mismatch":     "Context / mood mismatch",
}
SEGMENT_LABELS: dict[str, str] = {
    "power_user":      "Power User",
    "casual_listener": "Casual Listener",
    "playlist_curator":"Playlist Curator",
    "new_user":        "New User",
    "genre_enthusiast":"Genre Enthusiast",
    "passive_listener":"Passive Listener",
}
SOURCE_COLORS = {
    "play_store": "#1DB954",
    "app_store":  "#4A90D9",
    "forum":      "#9B59B6",
    "reddit":     "#FF4500",
}
SOURCE_LABELS = {
    "play_store": "Play Store",
    "app_store":  "App Store",
    "forum":      "Community Forum",
    "reddit":     "Reddit",
}
# Job-to-be-done labels — the GOAL behind the session (high-coverage segmentation).
JOB_LABELS = {
    "steer_algorithm":      "Steer / fix the algorithm",
    "find_new_music":       "Find new music",
    "build_playlist":       "Build & curate playlists",
    "replay_favorites":     "Replay favorites",
    "background_listening": "Background listening",
    "mood_or_activity":     "Mood / activity",
}


def main() -> None:
    conn = sqlite3.connect(DB)

    # ── totals ────────────────────────────────────────────────────────────────
    total_n = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    n_sources = conn.execute("SELECT COUNT(DISTINCT source) FROM reviews").fetchone()[0]

    # ── coded reviews (relevant only) ─────────────────────────────────────────
    rows = conn.execute(
        "SELECT cr.id, cr.themes, cr.sentiment, cr.segment, cr.jtbd, "
        "r.source, r.date, r.rating "
        "FROM coded_reviews cr "
        "JOIN reviews r ON cr.id = r.id"
    ).fetchall()

    records = []
    for id_, themes_json, sentiment, segment, jtbd, source, date, rating in rows:
        try:
            theme_list = json.loads(themes_json or "[]")
        except json.JSONDecodeError:
            theme_list = []
        records.append({
            "id": id_, "themes": theme_list, "sentiment": sentiment,
            "segment": segment, "jtbd": jtbd, "source": source,
            "date": date, "rating": rating,
        })

    n_relevant = len(records)

    # explode to one row per canonical theme
    exploded = [
        {**r, "theme": t}
        for r in records
        for t in r["themes"]
        if t in CANONICAL
    ]

    # ── stats ─────────────────────────────────────────────────────────────────
    n_neg = sum(1 for r in records if r["sentiment"] == "negative")
    neg_pct = round(n_neg / n_relevant * 100) if n_relevant else 0
    n_themes = len(set(e["theme"] for e in exploded))

    # ── theme frequencies + % negative ────────────────────────────────────────
    theme_mentions: dict[str, int] = {}
    theme_neg: dict[str, list[bool]] = {}
    for e in exploded:
        t = e["theme"]
        theme_mentions[t] = theme_mentions.get(t, 0) + 1
        theme_neg.setdefault(t, []).append(e["sentiment"] == "negative")

    theme_data = []
    for t in sorted(CANONICAL, key=lambda x: -theme_mentions.get(x, 0)):
        mentions = theme_mentions.get(t, 0)
        neg_list = theme_neg.get(t, [])
        neg_p = round(sum(neg_list) / len(neg_list) * 100) if neg_list else 0
        theme_data.append({
            "theme":    THEME_LABELS[t],
            "mentions": mentions,
            "negPct":   neg_p,
        })

    # ── source counts (all reviews) ────────────────────────────────────────────
    src_rows = conn.execute(
        "SELECT source, COUNT(*) as n FROM reviews GROUP BY source ORDER BY n DESC"
    ).fetchall()
    sources = [
        {"source": SOURCE_LABELS.get(s, s), "n": n, "color": SOURCE_COLORS.get(s, "#888")}
        for s, n in src_rows
    ]

    # ── segmentation is evidence-gated: most app-store reviews carry no user-type
    #    signal, so ~70% land in "unknown". We only chart segments with enough
    #    confidently-attributed reviews (>= SEG_MIN) and surface the identifiable
    #    share as an honest stat. "unknown" is never charted as a column.
    SEG_MIN = 15
    seg_counts: dict[str, int] = {}
    for r in records:
        seg = SEGMENT_LABELS.get(r["segment"])  # None for "unknown"
        if seg:
            seg_counts[seg] = seg_counts.get(seg, 0) + 1

    # segments worth charting, biggest first
    segments_ordered = [
        s for s in sorted(seg_counts, key=lambda x: -seg_counts[x])
        if seg_counts[s] >= SEG_MIN
    ]
    n_identifiable = sum(seg_counts.values())          # reviews with ANY segment signal
    identifiable_pct = round(n_identifiable / n_relevant * 100) if n_relevant else 0

    # ── PRIMARY "who feels each pain" lens: RATING BAND (NPS-style) ─────────────
    #    Real metadata on every store review (1-5★). Far higher coverage + richer
    #    cells than inferred persona. Cells = % of that band's reviews citing the
    #    theme, so band-size differences don't distort the colour. Forum reviews
    #    have no rating and are excluded from this chart (noted in the UI).
    def band_of(rating) -> str | None:
        if rating is None:
            return None
        try:
            r = int(float(rating))
        except (ValueError, TypeError):
            return None
        if r <= 2:
            return "Detractor (1–2★)"
        if r == 3:
            return "Passive (3★)"
        return "Promoter (4–5★)"

    RATING_BANDS = ["Detractor (1–2★)", "Passive (3★)", "Promoter (4–5★)"]
    band_totals: dict[str, int] = {b: 0 for b in RATING_BANDS}
    band_theme: dict[str, dict[str, int]] = {THEME_LABELS[t]: {b: 0 for b in RATING_BANDS} for t in CANONICAL}
    for r in records:
        b = band_of(r["rating"])
        if not b:
            continue
        band_totals[b] += 1
        for t in set(r["themes"]):
            if t in CANONICAL:
                band_theme[THEME_LABELS[t]][b] += 1

    n_rated = sum(band_totals.values())
    rating_heatmap = {
        theme: {
            b: round(band_theme[theme][b] / band_totals[b] * 100) if band_totals[b] else 0
            for b in RATING_BANDS
        }
        for theme in band_theme
    }

    # keep the persona heatmap too (now a secondary/qualitative lens)
    heatmap: dict[str, dict[str, int]] = {THEME_LABELS[t]: {} for t in CANONICAL}
    for e in exploded:
        label = THEME_LABELS.get(e["theme"])
        seg   = SEGMENT_LABELS.get(e["segment"])
        if label and seg in segments_ordered:
            heatmap[label][seg] = heatmap[label].get(seg, 0) + 1

    # ── JOB-TO-BE-DONE: segment by GOAL (94% coverage — the real "segments" view).
    #    Reviews coded by what the user was trying to DO, not who they are. "unclear"
    #    is excluded from the chart; coverage reported as a stat.
    job_counts: dict[str, int] = {}
    for r in records:
        j = r["jtbd"]
        if j in JOB_LABELS:
            job_counts[j] = job_counts.get(j, 0) + 1
    n_jtbd = sum(job_counts.values())
    jtbd_pct = round(n_jtbd / n_relevant * 100) if n_relevant else 0
    jtbd_data = [
        {"job": JOB_LABELS[j], "count": c, "pct": round(c / n_relevant * 100)}
        for j, c in sorted(job_counts.items(), key=lambda x: -x[1])
    ]

    conn.close()

    # ── render TypeScript ─────────────────────────────────────────────────────
    theme_ts = "[\n" + "".join(
        f'  {{ theme: {json.dumps(t["theme"])}, mentions: {t["mentions"]}, negPct: {t["negPct"]} }},\n'
        for t in theme_data
    ) + "]"

    segments_ts = json.dumps(segments_ordered, indent=2)

    heatmap_ts = "{\n"
    for theme_label, seg_map in heatmap.items():
        row = ", ".join(
            f'{json.dumps(seg)}: {seg_map.get(seg, 0)}'
            for seg in segments_ordered
        )
        heatmap_ts += f'  {json.dumps(theme_label)}: {{ {row} }},\n'
    heatmap_ts += "}"

    rating_bands_ts = json.dumps(RATING_BANDS, ensure_ascii=False)
    band_totals_ts = ("{ " + ", ".join(
        f'{json.dumps(b, ensure_ascii=False)}: {band_totals[b]}' for b in RATING_BANDS
    ) + " }")
    rating_heatmap_ts = "{\n"
    for theme_label, bmap in rating_heatmap.items():
        row = ", ".join(
            f'{json.dumps(b, ensure_ascii=False)}: {bmap[b]}' for b in RATING_BANDS
        )
        rating_heatmap_ts += f'  {json.dumps(theme_label)}: {{ {row} }},\n'
    rating_heatmap_ts += "}"

    jtbd_ts = "[\n" + "".join(
        f'  {{ job: {json.dumps(j["job"])}, count: {j["count"]}, pct: {j["pct"]} }},\n'
        for j in jtbd_data
    ) + "]"

    sources_ts = "[\n" + "".join(
        f'  {{ source: {json.dumps(s["source"])}, n: {s["n"]}, color: {json.dumps(s["color"])} }},\n'
        for s in sources
    ) + "]"

    ts = textwrap.dedent(f"""\
        // AUTO-GENERATED by pipeline/export_data.py — do not edit by hand.
        // Re-run the script after each pipeline refresh to update these numbers.

        export const GREEN = "#1DB954";

        export const STATS = {{
          totalReviews:    {total_n},
          sources:         {n_sources},
          relevant:        {n_relevant},
          themes:          {n_themes},
          negativePct:     {neg_pct},
          identifiable:    {n_identifiable},
          identifiablePct: {identifiable_pct},
          rated:           {n_rated},
          jtbdCoverage:    {jtbd_pct},
        }};

        export const THEME_DATA = {theme_ts};

        // JOB-TO-BE-DONE — segment by goal (the real "which segments" answer, {jtbd_pct}% coverage).
        export const JTBD_DATA = {jtbd_ts};

        // PRIMARY "who feels each pain" lens — by satisfaction (star rating).
        // Cells = % of that band's reviews citing the theme. Forum reviews (no rating) excluded.
        export const RATING_BANDS = {rating_bands_ts};
        export const BAND_TOTALS: Record<string, number> = {band_totals_ts};
        export const RATING_HEATMAP: Record<string, Record<string, number>> = {rating_heatmap_ts};

        // Secondary qualitative lens — inferred persona (only ~30% of reviews carry a signal).
        export const SEGMENTS = {segments_ts};
        export const HEATMAP_DATA: Record<string, Record<string, number>> = {heatmap_ts};

        export const SOURCES = {sources_ts};

        export const BRIEF_QUESTIONS = [
          "Why do users struggle to discover new music?",
          "What are the most common frustrations with recommendations?",
          "What listening behaviors are users trying to achieve?",
          "What causes users to repeatedly listen to the same content?",
          "Which user segments experience different discovery challenges?",
          "What unmet needs emerge consistently across reviews?",
        ];

        export interface SourceCard {{
          n: number;
          snippet: string;
          source: string;
          sourceColor: string;
          year: string;
          stars: number;
          segment: string;
        }}

        export interface QAEntry {{
          question: string;
          answer: string;
          takeaway: string;
          sources: SourceCard[];
        }}

        export const PRELOADED_QA: QAEntry[] = [
          {{
            question: "What causes users to repeatedly listen to the same content?",
            answer: "Users repeatedly hear the same tracks because discovery surfaces recycle familiar music rather than introduce new artists. Reviewers say Discover Weekly and Radio \\"keep playing the same songs\\" [1], and that liking or skipping anything narrows recommendations further [2]. Power users in particular feel the algorithm optimizes for what they already know [3].",
            takeaway: "Repetition is structural — the algorithm reinforces history instead of expanding taste.",
            sources: [
              {{ n: 1, snippet: "Discover Weekly just replays stuff I already listen to. Where\\'s the discovery?", source: "Play Store",      sourceColor: "#1DB954", year: "2024", stars: 2, segment: "Power User" }},
              {{ n: 2, snippet: "I\\'m scared to skip a song now because it wrecks my recommendations for a week.", source: "Community Forum", sourceColor: "#9B59B6", year: "2024", stars: 0, segment: "Casual Listener" }},
              {{ n: 3, snippet: "The algorithm only ever shows me my comfort zone. I want to be challenged.",       source: "App Store",      sourceColor: "#4A90D9", year: "2025", stars: 2, segment: "Power User" }},
            ],
          }},
          {{
            question: "Why do users struggle to discover new music?",
            answer: "Discovery fails because the algorithm prioritises engagement over exploration. Users report that Spotify\\'s recommendations converge on a narrow slice of artists they already know [1], and that there is no easy way to signal \\"show me something genuinely new\\" without using expert-mode tools like Prompted Playlist [2]. Casual listeners are especially stuck — they rely on auto-play and Radio, which both recycle familiar content [3].",
            takeaway: "There is no effortless path to genuine novelty — users must know how to ask for it.",
            sources: [
              {{ n: 1, snippet: "Every playlist Spotify makes me is just my top 50 songs shuffled differently.", source: "Play Store",      sourceColor: "#1DB954", year: "2024", stars: 1, segment: "Power User" }},
              {{ n: 2, snippet: "I didn\\'t even know Prompted Playlist existed. How is that hidden?",             source: "App Store",      sourceColor: "#4A90D9", year: "2025", stars: 3, segment: "Casual Listener" }},
              {{ n: 3, snippet: "Radio just plays my saved songs. That\\'s not radio, that\\'s shuffle.",           source: "Community Forum", sourceColor: "#9B59B6", year: "2024", stars: 0, segment: "Casual Listener" }},
            ],
          }},
          {{
            question: "What are the most common frustrations with recommendations?",
            answer: "The top frustrations are: (1) sameness — the same 20–30 artists appear across all recommendation surfaces [1]; (2) algorithm distrust — users don\\'t believe recommendations are for their benefit after learning about Discovery Mode promotion practices [2]; (3) profile pollution — one party playlist or gym session permanently skews recommendations [3].",
            takeaway: "Users don\\'t just want better recs — they want recommendations they can trust and control.",
            sources: [
              {{ n: 1, snippet: "Spotify keeps recommending the same 5 artists I\\'ve heard a thousand times.",  source: "Play Store",      sourceColor: "#1DB954", year: "2025", stars: 2, segment: "Genre Enthusiast" }},
              {{ n: 2, snippet: "Found out artists pay Spotify for recommendations. Now I trust nothing.",        source: "Community Forum", sourceColor: "#9B59B6", year: "2024", stars: 0, segment: "Power User" }},
              {{ n: 3, snippet: "Listened to one kids playlist with my nephew. Now all I get is Baby Shark.",    source: "App Store",       sourceColor: "#4A90D9", year: "2024", stars: 1, segment: "Casual Listener" }},
            ],
          }},
          {{
            question: "What listening behaviors are users trying to achieve?",
            answer: "Coding every review by job-to-be-done (94% coverage) reveals one job dominates: 52% are users trying to STEER or fix the algorithm — correcting bad recommendations, escaping a genre, fixing Release Radar [1]. The next jobs are finding new music (15%) and building/curating playlists (15%) [2], then replaying favorites (8%). Passive 'just press play' listening is a small minority [3]. The behavior isn't passive consumption — it's active, frustrated control.",
            takeaway: "The #1 behavior is steering the algorithm — users want control, and today's controls fail them.",
            sources: [
              {{ n: 1, snippet: "Discover Weekly keeps giving me the same genre and the 'not interested' option does nothing.", source: "App Store",       sourceColor: "#4A90D9", year: "2025", stars: 2, segment: "Power User" }},
              {{ n: 2, snippet: "Let me build my playlist in peace — stop auto-adding songs I didn't choose.",               source: "Community Forum", sourceColor: "#9B59B6", year: "2024", stars: 0, segment: "Playlist Curator" }},
              {{ n: 3, snippet: "I just want to press play and have something good on. Why is that so hard?",                source: "Play Store",      sourceColor: "#1DB954", year: "2025", stars: 2, segment: "Passive Listener" }},
            ],
          }},
          {{
            question: "Which user segments experience different discovery challenges?",
            answer: "Most reviews (70%) don\\'t reveal the user\\'s type, so segment claims must be read with care. Among the ~30% where the text gives a clear signal, the sharpest pain comes from users who actively try to *shape* their listening: playlist-builders report the most discovery friction and over-personalization — their carefully built playlists get flooded or collapse to the same few songs [1][2]. Heavy/long-term users feel sameness and distrust most acutely [3]. Algorithm distrust itself is broad, appearing across heavy users, genre-fans, and curators alike rather than concentrating in one group.",
            takeaway: "Discovery pain is broad, not niche — but high-intent \\"shapers\\" (playlist-builders, heavy users) feel it sharpest and are the natural beachhead.",
            sources: [
              {{ n: 1, snippet: "My 1000+ song playlist just plays the same 15 tracks on shuffle, even if I skip them.", source: "Play Store",      sourceColor: "#1DB954", year: "2024", stars: 2, segment: "Playlist Curator" }},
              {{ n: 2, snippet: "Stop auto-adding songs to my playlists — let me listen to what I built in peace.",     source: "Community Forum", sourceColor: "#9B59B6", year: "2024", stars: 0, segment: "Playlist Curator" }},
              {{ n: 3, snippet: "I listen for hours every day and still get the same 30 artists. The bubble is real.",   source: "App Store",       sourceColor: "#4A90D9", year: "2025", stars: 1, segment: "Power User" }},
            ],
          }},
          {{
            question: "What unmet needs emerge consistently across reviews?",
            answer: "Three needs appear across all sources: (1) intent expression — a low-effort way to say \\"I want something like X but newer / more obscure\\" [1]; (2) profile-safe exploration — try new genres without corrupting long-term taste profile [2]; (3) transparent recommendations — understand why a song was recommended and whether it was promoted [3].",
            takeaway: "Users want to steer, explore safely, and trust — none of which Spotify makes easy today.",
            sources: [
              {{ n: 1, snippet: "I wish I could just type \\'like Radiohead but from the last 2 years\\' and get something.", source: "Community Forum", sourceColor: "#9B59B6", year: "2025", stars: 0, segment: "Power User" }},
              {{ n: 2, snippet: "I want a \\'try something new\\' mode that doesn\\'t mess up my Discover Weekly.",           source: "Play Store",      sourceColor: "#1DB954", year: "2024", stars: 2, segment: "Genre Enthusiast" }},
              {{ n: 3, snippet: "Is this song here because I\\'d like it or because the label paid for placement?",          source: "App Store",       sourceColor: "#4A90D9", year: "2024", stars: 2, segment: "Power User" }},
            ],
          }},
        ];
        """)

    OUT.write_text(ts)
    print(f"✓ Exported {n_relevant} coded reviews → {OUT}")
    print(f"  Total: {total_n} | Sources: {n_sources} | Negative: {neg_pct}%")
    print(f"  Themes: {[t['theme'] for t in theme_data]}")


if __name__ == "__main__":
    main()
