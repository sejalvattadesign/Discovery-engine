"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { SOURCES } from "@/lib/data";

export default function SourcesDonut() {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={SOURCES}
          dataKey="n"
          nameKey="source"
          cx="40%"
          cy="50%"
          innerRadius={65}
          outerRadius={100}
          paddingAngle={2}
          label={false}
        >
          {SOURCES.map((entry) => (
            <Cell key={entry.source} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#282828", border: "1px solid #383838", borderRadius: 8 }}
          labelStyle={{ color: "#fff", fontWeight: 600 }}
          itemStyle={{ color: "#1DB954", fontWeight: 600 }}
          formatter={(v, name) => [Number(v).toLocaleString(), String(name)]}
        />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          formatter={(value, entry) => (
            <span style={{ color: "#B3B3B3", fontSize: "0.83rem" }}>
              {value}{" "}
              <strong style={{ color: "#fff" }}>
                {/* @ts-ignore */}
                {entry.payload?.n?.toLocaleString()}
              </strong>
            </span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
