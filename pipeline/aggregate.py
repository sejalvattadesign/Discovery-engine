"""Stage 5 / Phase 5 — aggregation & analysis.

Turns coded_reviews into the artifacts that *select* a root cause:
  1. Theme frequency overall and by segment.
  2. Sentiment per theme (negative share = "pain").
  3. A ranked table: theme x frequency x pain x segment concentration.
  4. Colorblind-safe charts exported to data/ for the deck (slide 4).

The canonical 8-theme taxonomy carries ~95% of the signal; the model's long tail of
one-off invented themes is collapsed into "other" so the rollups stay readable.

No LLM here — pure pandas/SQL. Outputs:
  data/agg_theme_ranking.csv        the ranked root-cause table
  data/agg_theme_by_segment.csv     theme x segment counts
  data/chart_theme_frequency.png
  data/chart_theme_sentiment.png
  data/chart_theme_by_segment.png
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reviews.db"
OUT = ROOT / "data"

CANONICAL = [
    "discovery_friction", "sameness_fatigue", "algorithm_distrust",
    "profile_pollution_fear", "intent_expression_gap", "context_mood_mismatch",
    "passive_discovery_failure", "over_personalization",
]

# Colorblind-safe palette (Okabe-Ito).
CB = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00",
      "#F0E442", "#999999"]


def load_rows() -> pd.DataFrame:
    """One row per (review, theme) with sentiment + segment, themes exploded."""
    conn = sqlite3.connect(DB_PATH)
    coded = pd.read_sql_query(
        "SELECT id, themes, sentiment, segment FROM coded_reviews", conn
    )
    reviews = pd.read_sql_query(
        "SELECT id, source, country FROM reviews WHERE relevant=1", conn
    )
    conn.close()

    df = coded.merge(reviews, on="id", how="left")
    df["themes"] = df["themes"].apply(lambda s: json.loads(s or "[]"))
    df = df.explode("themes").rename(columns={"themes": "theme"})
    df = df[df["theme"].notna()]
    # collapse the long tail of one-off invented themes into "other"
    df["theme"] = df["theme"].where(df["theme"].isin(CANONICAL), "other")
    return df


def theme_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """Rank themes by frequency x pain x segment concentration."""
    rows = []
    total_reviews = df["id"].nunique()
    for theme, g in df.groupby("theme"):
        n = g["id"].nunique()
        neg = (g["sentiment"] == "negative").sum()
        pain = neg / len(g) if len(g) else 0.0
        # segment concentration = share held by the theme's top segment (Herfindahl-ish)
        seg_counts = g["segment"].value_counts(normalize=True)
        top_segment = seg_counts.index[0] if len(seg_counts) else "unknown"
        concentration = float(seg_counts.iloc[0]) if len(seg_counts) else 0.0
        rows.append(
            {
                "theme": theme,
                "frequency": n,
                "freq_share": round(n / total_reviews, 3),
                "pain_negative_share": round(pain, 3),
                "top_segment": top_segment,
                "segment_concentration": round(concentration, 3),
            }
        )
    rank = pd.DataFrame(rows)
    # composite score: how often x how painful x how concentrated
    rank["score"] = (
        rank["frequency"]
        * rank["pain_negative_share"]
        * rank["segment_concentration"]
    ).round(1)
    rank = rank[rank["theme"] != "other"].sort_values("score", ascending=False)
    return rank.reset_index(drop=True)


def theme_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    canon = df[df["theme"] != "other"]
    pivot = (
        canon.groupby(["theme", "segment"])["id"]
        .nunique()
        .unstack(fill_value=0)
    )
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    return pivot


# ---------- charts ----------

def chart_frequency(rank: pd.DataFrame) -> None:
    d = rank.sort_values("frequency")
    plt.figure(figsize=(9, 5))
    plt.barh(d["theme"], d["frequency"], color=CB[0])
    plt.xlabel("Reviews mentioning theme")
    plt.title("Discovery pain themes by frequency")
    plt.tight_layout()
    plt.savefig(OUT / "chart_theme_frequency.png", dpi=150)
    plt.close()


def chart_sentiment(df: pd.DataFrame) -> None:
    canon = df[df["theme"] != "other"]
    ct = (
        canon.groupby(["theme", "sentiment"])["id"].nunique().unstack(fill_value=0)
    )
    for col in ["negative", "neutral", "positive"]:
        if col not in ct:
            ct[col] = 0
    ct = ct[["negative", "neutral", "positive"]]
    ct = ct.loc[ct.sum(axis=1).sort_values().index]
    plt.figure(figsize=(9, 5))
    bottom = [0] * len(ct)
    colors = {"negative": CB[5], "neutral": CB[7], "positive": CB[2]}
    for col in ["negative", "neutral", "positive"]:
        plt.barh(ct.index, ct[col], left=bottom, label=col, color=colors[col])
        bottom = [b + v for b, v in zip(bottom, ct[col])]
    plt.xlabel("Reviews")
    plt.title("Sentiment composition per theme")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "chart_theme_sentiment.png", dpi=150)
    plt.close()


def chart_by_segment(pivot: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 6))
    bottom = [0] * len(pivot)
    for i, seg in enumerate(pivot.columns):
        plt.barh(pivot.index, pivot[seg], left=bottom, label=seg,
                 color=CB[i % len(CB)])
        bottom = [b + v for b, v in zip(bottom, pivot[seg])]
    plt.xlabel("Reviews")
    plt.title("Theme distribution across user segments")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(OUT / "chart_theme_by_segment.png", dpi=150)
    plt.close()


def main() -> None:
    df = load_rows()
    rank = theme_ranking(df)
    pivot = theme_by_segment(df)

    rank.to_csv(OUT / "agg_theme_ranking.csv", index=False)
    pivot.to_csv(OUT / "agg_theme_by_segment.csv")
    chart_frequency(rank)
    chart_sentiment(df)
    chart_by_segment(pivot)

    print("=== Ranked theme table (root-cause selection) ===")
    print(rank.to_string(index=False))

    print("\n=== Theme x segment (unique reviews) ===")
    print(pivot.to_string())

    top = rank.iloc[0]
    print("\n=== Candidate root cause ===")
    print(
        f"-> {top['theme']}  (freq={top['frequency']}, "
        f"pain={top['pain_negative_share']:.0%} negative, "
        f"concentrated in {top['top_segment']} @ {top['segment_concentration']:.0%}, "
        f"score={top['score']})"
    )

    print("\nWrote:")
    for f in [
        "agg_theme_ranking.csv", "agg_theme_by_segment.csv",
        "chart_theme_frequency.png", "chart_theme_sentiment.png",
        "chart_theme_by_segment.png",
    ]:
        print(f"  data/{f}")


if __name__ == "__main__":
    main()
