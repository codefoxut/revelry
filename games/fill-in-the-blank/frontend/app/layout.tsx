import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Revelry — Fill in the Blank",
  description: "A mad-libs party game — fill in the blank with the funniest answer, then vote!",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-dvh flex-col bg-zinc-950 text-zinc-50 antialiased">{children}</body>
    </html>
  );
}
