interface Stat { label: string; value: string }

export default function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
      {stats.map(({ label, value }) => (
        <div
          key={label}
          style={{
            background: "#181818",
            border: "1px solid #282828",
            borderRadius: 12,
            padding: "16px 20px",
          }}
        >
          <div
            style={{
              color: "#1DB954",
              fontSize: "1.9rem",
              fontWeight: 700,
              lineHeight: 1,
              marginBottom: 6,
            }}
          >
            {value}
          </div>
          <div
            style={{
              color: "#B3B3B3",
              fontSize: "0.7rem",
              textTransform: "uppercase",
              letterSpacing: "0.07em",
            }}
          >
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}
