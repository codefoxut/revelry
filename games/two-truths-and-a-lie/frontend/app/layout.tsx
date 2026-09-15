import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Revelry — Two Truths and a Lie",
  description: "Share two truths and one lie — can your friends guess which is which?",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-dvh flex-col bg-zinc-950 text-zinc-50 antialiased">{children}</body>
    </html>
  );
}
