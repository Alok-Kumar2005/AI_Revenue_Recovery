"use client";

// src/components/StrategyBreakdown.tsx
// Channel distribution progress bars derived from interventions data.

import type { Intervention } from "@/lib/types";

interface StrategyBreakdownProps {
  interventions: Intervention[];
}

const CHANNEL_COLORS: Record<string, { bar: string; label: string }> = {
  EMAIL:    { bar: "bg-blue-500",    label: "Email" },
  SMS:      { bar: "bg-amber-500",   label: "SMS" },
  WHATSAPP: { bar: "bg-emerald-500", label: "WhatsApp" },
  RETRY:    { bar: "bg-purple-500",  label: "Retry" },
  ESCALATE: { bar: "bg-red-500",     label: "Escalate" },
  STOP:     { bar: "bg-slate-500",   label: "Stop" },
};

export default function StrategyBreakdown({ interventions }: StrategyBreakdownProps) {
  if (!interventions || interventions.length === 0) {
    return (
      <div className="card">
        <h2 className="text-base font-semibold text-slate-100 mb-1">Strategy Breakdown</h2>
        <p className="text-xs text-slate-500">No intervention data available yet.</p>
      </div>
    );
  }

  // Tally by channel
  const counts: Record<string, number> = {};
  for (const iv of interventions) {
    const ch = iv.channel.toUpperCase();
    counts[ch] = (counts[ch] ?? 0) + 1;
  }

  const total = interventions.length;
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  return (
    <div className="card">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-base font-semibold text-slate-100">Strategy Breakdown</h2>
        <span className="text-xs text-slate-500">{total} total interventions</span>
      </div>

      <div className="space-y-3">
        {sorted.map(([channel, count]) => {
          const meta = CHANNEL_COLORS[channel] ?? { bar: "bg-slate-500", label: channel };
          const pct = ((count / total) * 100).toFixed(1);
          return (
            <div key={channel}>
              <div className="flex items-center justify-between mb-1 text-xs">
                <span className="text-slate-300 font-medium">{meta.label}</span>
                <span className="text-slate-500 font-mono">
                  {count} &mdash; {pct}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full ${meta.bar} transition-all duration-700 ease-out`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
