"use client";

import { useState } from "react";
import TopBar from "@/components/TopBar";
import StatStrip from "@/components/StatStrip";
import InsightsView from "@/components/InsightsView";
import AskView from "@/components/AskView";
import { STATS } from "@/lib/data";

const STAT_ITEMS = [
  { label: "Reviews analyzed",   value: STATS.totalReviews.toLocaleString() },
  { label: "Sources",            value: String(STATS.sources) },
  { label: "Discovery-relevant", value: STATS.relevant.toLocaleString() },
  { label: "Themes coded",       value: String(STATS.themes) },
  { label: "Negative sentiment", value: `${STATS.negativePct}%` },
];

export default function Home() {
  const [view, setView] = useState<"Insights" | "Ask">("Insights");

  return (
    <div style={{ minHeight: "100vh", background: "#121212" }}>
      <TopBar totalReviews={STATS.totalReviews} view={view} onViewChange={setView} />

      <main
        style={{
          maxWidth: 1380,
          margin: "0 auto",
          padding: "24px 24px 48px",
        }}
      >
        {/* stat strip */}
        <div style={{ marginBottom: 20 }}>
          <StatStrip stats={STAT_ITEMS} />
        </div>

        {/* view content */}
        {view === "Insights" ? <InsightsView /> : <AskView />}
      </main>
    </div>
  );
}
