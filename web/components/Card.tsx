import { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode;
  style?: React.CSSProperties;
}

export default function Card({ title, subtitle, children, style }: Props) {
  return (
    <div
      style={{
        background: "#181818",
        border: "1px solid #282828",
        borderRadius: 16,
        padding: "20px 22px",
        ...style,
      }}
    >
      <div style={{ fontWeight: 700, fontSize: "1rem", color: "#fff", marginBottom: 4 }}>
        {title}
      </div>
      {subtitle && (
        <div style={{ fontSize: "0.8rem", color: "#B3B3B3", marginBottom: 14 }}>
          {subtitle}
        </div>
      )}
      {children}
    </div>
  );
}
