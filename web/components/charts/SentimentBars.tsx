import { THEME_DATA } from "@/lib/data";

export default function SentimentBars() {
  const sorted = [...THEME_DATA].sort((a, b) => b.negPct - a.negPct);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
      {sorted.map(({ theme, negPct }) => {
        const color = negPct >= 80 ? "#1DB954" : "#F59E0B";
        return (
          <div key={theme}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ color: "#fff", fontSize: "0.83rem" }}>{theme}</span>
              <span style={{ color, fontSize: "0.79rem", fontWeight: 700 }}>
                {negPct}% negative
              </span>
            </div>
            <div style={{ background: "#282828", borderRadius: 4, height: 6 }}>
              <div
                style={{
                  background: color,
                  borderRadius: 4,
                  height: 6,
                  width: `${negPct}%`,
                  transition: "width 0.4s ease",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
