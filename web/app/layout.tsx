import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Discovery Lens — Spotify Review Engine",
  description: "Why discovery fails on Spotify — mined from 4,361 real reviews",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full" style={{ background: "#121212", color: "#fff" }}>
        {children}
      </body>
    </html>
  );
}
