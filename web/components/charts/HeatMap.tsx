import { RATING_HEATMAP, RATING_BANDS, BAND_TOTALS, THEME_DATA } from "@/lib/data";

const THEME_ORDER = THEME_DATA.map((t) => t.theme);
const MAX_VAL = Math.max(
  ...Object.values(RATING_HEATMAP).flatMap((row) => Object.values(row))
);

function opacity(n: number) {
  return MAX_VAL ? 0.1 + (n / MAX_VAL) * 0.9 : 0.1;
}

export default function HeatMap() {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 4 }}>
        <thead>
          <tr>
            <th style={{ width: 180 }} />
            {RATING_BANDS.map((band) => (
              <th
                key={band}
                style={{
                  color: "#fff",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  textAlign: "center",
                  padding: "0 4px 2px",
                  whiteSpace: "nowrap",
                }}
              >
                {band}
                <div style={{ color: "#666", fontSize: "0.66rem", fontWeight: 400 }}>
                  n={BAND_TOTALS[band]}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {THEME_ORDER.map((theme) => (
            <tr key={theme}>
              <td
                style={{
                  color: "#B3B3B3",
                  fontSize: "0.8rem",
                  paddingRight: 12,
                  whiteSpace: "nowrap",
                }}
              >
                {theme}
              </td>
              {RATING_BANDS.map((band) => {
                const pct = RATING_HEATMAP[theme]?.[band] ?? 0;
                const op = opacity(pct);
                const textColor = op > 0.6 ? "#000" : "#fff";
                return (
                  <td key={band} style={{ padding: 2 }}>
                    <div
                      title={`${theme} · ${band}: ${pct}% of that band's reviews`}
                      style={{
                        background: `rgba(29,185,84,${op})`,
                        borderRadius: 6,
                        height: 38,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.82rem",
                        fontWeight: 600,
                        color: textColor,
                      }}
                    >
                      {pct}%
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
