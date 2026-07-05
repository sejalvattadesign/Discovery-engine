"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from "recharts";
import { JTBD_DATA, GREEN } from "@/lib/data";

// The three "active discovery" jobs = our target segment, the Discovery Skeptics.
// The rest (replay / background / mood) are passive listeners we don't target.
const SKEPTIC_JOBS = new Set([
  "Steer / fix the algorithm",
  "Find new music",
  "Build & curate playlists",
]);

export default function JtbdBars() {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart
        data={JTBD_DATA}
        layout="vertical"
        margin={{ top: 0, right: 48, left: 8, bottom: 0 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="job"
          width={160}
          tick={{ fill: "#B3B3B3", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{ background: "#282828", border: "1px solid #383838", borderRadius: 8 }}
          labelStyle={{ color: "#fff", fontWeight: 600 }}
          itemStyle={{ color: "#1DB954", fontWeight: 600 }}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          formatter={(v, _n, item) => {
            const pct = (item as { payload?: { pct?: number } })?.payload?.pct;
            return [`${v} reviews (${pct}%)`, "Count"];
          }}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {JTBD_DATA.map((entry) => (
            <Cell key={entry.job} fill={SKEPTIC_JOBS.has(entry.job) ? GREEN : "#555"} />
          ))}
          <LabelList
            dataKey="pct"
            position="right"
            formatter={(v) => `${v}%`}
            fill="#B3B3B3"
            fontSize={12}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
