"use client";

// src/components/Navbar.tsx
// Fixed top navigation bar with live backend health polling.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, LayoutDashboard, Sparkles, Zap } from "lucide-react";
import AICopilotDrawer from "./AICopilotDrawer";

type HealthStatus = "checking" | "connected" | "disconnected";

function useHealthStatus() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    async function ping() {
      try {
        // /health is proxied by Next.js rewrites → no CORS issue
        const res = await fetch("/health", {
          cache: "no-store",
          signal: AbortSignal.timeout(4000),
        });
        const json = await res.json();
        if (!cancelled) {
          setStatus(json.status === "healthy" ? "connected" : "disconnected");
        }
      } catch {
        if (!cancelled) setStatus("disconnected");
      }
    }

    ping();
    const interval = setInterval(ping, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return status;
}

const NAV_LINKS = [
  { href: "/",       label: "Dashboard",       icon: LayoutDashboard },
  { href: "/batch",  label: "Live Simulation",  icon: Zap },
];

export default function Navbar() {
  const pathname = usePathname();
  const health = useHealthStatus();
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  const statusColor =
    health === "connected"
      ? "bg-emerald-400"
      : health === "disconnected"
      ? "bg-red-400"
      : "bg-amber-400 animate-pulse";

  const statusLabel =
    health === "connected"
      ? "Backend: Connected"
      : health === "disconnected"
      ? "Backend: Disconnected"
      : "Backend: Checking…";

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-40 h-[60px] glass-heavy border-b border-white/[0.06]">
        <nav className="mx-auto flex h-full max-w-7xl items-center justify-between px-5">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2.5 group focus-ring rounded-lg"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-900/40 group-hover:shadow-emerald-700/50 transition-shadow">
              <Activity size={16} className="text-white" strokeWidth={2.5} />
            </span>
            <span className="text-sm font-semibold tracking-tight text-slate-100">
              AI Revenue Recovery
            </span>
          </Link>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`relative flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors focus-ring
                    ${
                      isActive
                        ? "text-white bg-white/[0.08]"
                        : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]"
                    }`}
                >
                  <Icon size={14} strokeWidth={2} />
                  {label}
                  {isActive && (
                    <span className="absolute inset-x-3 bottom-1 h-px rounded-full bg-gradient-to-r from-emerald-500 to-teal-500" />
                  )}
                </Link>
              );
            })}
          </div>

          {/* Right Side: Copilot button + Health status */}
          <div className="flex items-center gap-3">
            {/* AI Copilot Trigger Button */}
            <button
              id="ai-copilot-toggle-btn"
              onClick={() => setIsCopilotOpen((prev) => !prev)}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-emerald-500/15 to-teal-500/15 border border-emerald-500/40 hover:border-emerald-400 hover:bg-emerald-500/25 text-emerald-300 shadow-sm shadow-emerald-950/50 transition-all focus-ring group"
            >
              <Sparkles size={13} className="text-emerald-400 group-hover:rotate-12 transition-transform" />
              <span>AI Copilot</span>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            </button>

            {/* Health status */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full glass ring-1 ring-white/[0.06] text-xs text-slate-400">
              <span className={`h-1.5 w-1.5 rounded-full ${statusColor}`} />
              {statusLabel}
            </div>
          </div>
        </nav>
      </header>

      {/* Slide-over Copilot Drawer */}
      <AICopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
    </>
  );
}

