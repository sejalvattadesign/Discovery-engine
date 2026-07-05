"use client";

import { useState } from "react";
import Card from "./Card";
import PainBars from "./charts/PainBars";
import SentimentBars from "./charts/SentimentBars";
import HeatMap from "./charts/HeatMap";
import JtbdBars from "./charts/JtbdBars";
import SourcesDonut from "./charts/SourcesDonut";
import ThemeDrawer from "./ThemeDrawer";
import { STATS } from "@/lib/data";

const CHAIN = [
  "Intent gap",
  "Over-personalization",
  "Sameness",
  "Distrust",
  "Repeat listening",
];

export default function InsightsView() {
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      <ThemeDrawer theme={selectedTheme} onClose={() => setSelectedTheme(null)} />

      {/* row 1 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card
          title="Top discovery pains"
          subtitle="Click any theme to see the sub-problems and real quotes behind it."
        >
          <PainBars onSelect={setSelectedTheme} />
        </Card>

        <Card
          title="Sentiment by theme"
          subtitle="Share of each theme's reviews that are negative — distrust, profile-fear and sameness skew hardest; only intent gap is mixed."
        >
          <SentimentBars />
        </Card>
      </div>

      {/* row 1.5 — JTBD: segmentation by goal → the Discovery Skeptics (green) vs passive (grey) */}
      <Card
        title="What users are trying to do — and who the Discovery Skeptics are"
        subtitle={`Segmented by goal, not identity — coded from review text (${STATS.jtbdCoverage}% coverage). The three green jobs = our target segment (Discovery Skeptics); grey = passive listeners we don't target.`}
      >
        {/* legend */}
        <div style={{ display: "flex", gap: 18, margin: "0 0 8px 4px", fontSize: "0.76rem" }}>
          <span style={{ color: "#B3B3B3" }}>
            <span style={{ color: "#1DB954", fontWeight: 700 }}>■</span> ★ Discovery Skeptics — target (steer · find · curate)
          </span>
          <span style={{ color: "#B3B3B3" }}>
            <span style={{ color: "#555", fontWeight: 700 }}>■</span> Comfort Loop + Passive — not targeted (replay · background · mood)
          </span>
        </div>
        <JtbdBars />
        <p style={{ color: "#666", fontSize: "0.74rem", marginTop: 8, marginBottom: 0 }}>
          <strong style={{ color: "#1DB954" }}>The Discovery Skeptics try to fix discovery themselves</strong> — steering the algorithm (41%), hunting new music (27%), or building their own playlists to bypass it (12%). The controls are blunt and don&apos;t stick, so they give up and fall back to the familiar.
        </p>
      </Card>

      {/* row 2 — heatmap */}
      <Card
        title="Who feels each pain — by satisfaction"
        subtitle={`Share of each rating band's reviews citing the theme (${STATS.rated} store reviews with a star rating). Distrust & over-personalization pull ratings down — but discovery friction stays high even among 4–5★ promoters.`}
      >
        <HeatMap />
        <p style={{ color: "#666", fontSize: "0.74rem", marginTop: 12, marginBottom: 0 }}>
          Rating band (detractor / passive / promoter) is real metadata on every store review — a far stronger signal than inferred persona. The takeaway: even your happiest users still can&apos;t discover. Forum reviews have no rating and are excluded here.
        </p>
      </Card>

      {/* row 3 — causal chain */}
      <Card
        title="The one causal chain"
        subtitle="Not 8 separate problems — one chain with two roots: no voice (intent gap) + no trust."
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", margin: "10px 0 14px" }}>
          {CHAIN.map((node, i) => (
            <div key={node} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  padding: "9px 20px",
                  borderRadius: 22,
                  fontSize: "0.92rem",
                  fontWeight: i === 0 ? 700 : 400,
                  background: i === 0 ? "#1DB954" : "transparent",
                  color: i === 0 ? "#000" : "#fff",
                  border: i === 0 ? "none" : "1px solid #444",
                }}
              >
                {node}
              </div>
              {i < CHAIN.length - 1 && (
                <span style={{ color: "#1DB954", fontSize: "1.4rem", fontWeight: 700 }}>→</span>
              )}
            </div>
          ))}
        </div>
        <p style={{ color: "#B3B3B3", fontSize: "0.87rem", margin: 0 }}>
          Two roots feed the loop: <strong style={{ color: "#fff" }}>no voice</strong> (users can&apos;t
          express intent) and <strong style={{ color: "#fff" }}>no trust</strong> (picks come with no
          &quot;why&quot;). Together they turn repeat-listening into a structural outcome.
        </p>
      </Card>

      {/* row 4 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card
          title="Sources"
          subtitle="Four independent surfaces — same recurring complaints."
        >
          <SourcesDonut />
        </Card>

        {/* headline insight */}
        <div
          style={{
            background: "#181818",
            border: "1px solid #282828",
            borderRadius: 16,
            padding: "24px 24px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              border: "1px solid #1DB954",
              color: "#1DB954",
              borderRadius: 20,
              padding: "4px 12px",
              fontSize: "0.7rem",
              fontWeight: 700,
              letterSpacing: "0.07em",
              width: "fit-content",
              marginBottom: 16,
            }}
          >
            ✦ HEADLINE INSIGHT
          </span>
          <div
            style={{
              fontSize: "1.35rem",
              fontWeight: 700,
              color: "#fff",
              lineHeight: 1.4,
              marginBottom: 14,
            }}
          >
            {STATS.negativePct}% of discovery feedback is negative — and the loudest voice is the
            Discovery Skeptic.
          </div>
          <p style={{ color: "#B3B3B3", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
            Our target segment — the <strong style={{ color: "#fff" }}>Discovery Skeptics</strong> —
            wanted new music, tried Spotify&apos;s discovery features, and{" "}
            <strong style={{ color: "#fff" }}>lost trust</strong> when the recs felt repetitive. They
            don&apos;t want more recommendations; they want to{" "}
            <strong style={{ color: "#fff" }}>trust what they&apos;re given and steer it</strong> —
            without poisoning their profile.
          </p>
        </div>
      </div>

      {/* footer */}
      <p style={{ textAlign: "center", color: "#444", fontSize: "0.74rem", marginTop: 8, paddingTop: 16, borderTop: "1px solid #282828" }}>
        Built on 4,361 anonymized reviews · Play Store · App Store · Community Forum · themes coded by an LLM · answers retrieved via RAG with citations.
      </p>
    </div>
  );
}
