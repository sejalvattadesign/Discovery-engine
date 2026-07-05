"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { THEME_DATA } from "@/lib/data";

export default function PainBars({ onSelect }: { onSelect?: (theme: string) => void }) {
  const data = [...THEME_DATA].sort((a, b) => b.mentions - a.mentions);
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 32, left: 8, bottom: 0 }}
      >
        <XAxis
          type="number"
          tick={{ fill: "#B3B3B3", fontSize: 11 }}
          axisLine={{ stroke: "#282828" }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="theme"
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
          formatter={(v) => [v, "Mentions"]}
        />
        <Bar
          dataKey="mentions"
          radius={[0, 4, 4, 0]}
          label={{ position: "right", fill: "#B3B3B3", fontSize: 11 }}
          cursor={onSelect ? "pointer" : undefined}
          onClick={(d) => {
            const t = (d as unknown as { theme?: string })?.theme;
            if (t) onSelect?.(t);
          }}
        >
          {data.map((entry) => (
            <Cell key={entry.theme} fill="#1DB954" />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
