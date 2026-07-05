"use client";

interface Props {
  totalReviews: number;
  view: "Insights" | "Ask";
  onViewChange: (v: "Insights" | "Ask") => void;
}

export default function TopBar({ totalReviews, view, onViewChange }: Props) {
  return (
    <header
      style={{
        background: "#121212",
        borderBottom: "1px solid #282828",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div
        style={{
          maxWidth: 1380,
          margin: "0 auto",
          padding: "0 24px",
          height: 60,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        {/* logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div
            style={{
              width: 28,
              height: 28,
              background: "#1DB954",
              borderRadius: "50%",
            }}
          />
          <span style={{ fontWeight: 700, fontSize: "1.15rem", letterSpacing: "-0.01em" }}>
            Discovery Lens
          </span>
        </div>

        {/* tagline */}
        <span style={{ color: "#B3B3B3", fontSize: "0.87rem", textAlign: "center" }}>
          Why discovery fails on Spotify — mined from{" "}
          <strong style={{ color: "#fff" }}>{totalReviews.toLocaleString()}</strong> real reviews
        </span>

        {/* right: live pill + toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          <span
            style={{
              border: "1px solid #1DB954",
              color: "#1DB954",
              borderRadius: 20,
              padding: "3px 12px",
              fontSize: "0.75rem",
              fontWeight: 600,
            }}
          >
            ● Live data
          </span>

          {/* pill toggle */}
          <div
            style={{
              background: "#282828",
              borderRadius: 8,
              padding: 4,
              display: "flex",
              gap: 2,
            }}
          >
            {(["Insights", "Ask"] as const).map((v) => (
              <button
                key={v}
                onClick={() => onViewChange(v)}
                style={{
                  padding: "6px 18px",
                  borderRadius: 6,
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.88rem",
                  fontWeight: view === v ? 700 : 500,
                  background: view === v ? "#1DB954" : "transparent",
                  color: view === v ? "#000" : "#B3B3B3",
                  transition: "all 0.15s",
                }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}
