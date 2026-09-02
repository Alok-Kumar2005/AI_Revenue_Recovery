// src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: {
    template: "%s | AI Revenue Recovery",
    default: "AI Revenue Recovery — Dashboard",
  },
  description:
    "Agent-powered platform that detects at-risk revenue and executes compliant recovery workflows across payment failures.",
  keywords: ["revenue recovery", "payment failure", "AI agent", "fintech"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface-950 text-slate-100 font-sans">
        <ToastProvider>
          <Navbar />
          <main className="pt-[60px] min-h-screen">{children}</main>
        </ToastProvider>
      </body>
    </html>
  );
}
