import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Beach, Please",
  description:
    "A sassy AI beach concierge that aggregates waves, rip currents, alerts, tides, water quality, sharks, and amenities for US beaches.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
