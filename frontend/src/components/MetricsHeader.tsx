"use client";

// src/components/MetricsHeader.tsx
// 4 KPI summary cards: At-Risk Revenue, Recovered, Recovery Rate, Active Cases.

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, TrendingUp } from "lucide-react";
import type { MetricsSummary } from "@/lib/types";

// ---- Helpers -----------------------------------------------------------------

function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function useCountUp(target: number, duration = 900) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (target === 0) { setValue(0); return; }
    const start = performance.now();
    function step(now: number) {
      const progress = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setValue(target * ease);
      if (progress < 1) rafRef.current = requestAnimationFrame(step);
    }
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}

// ---- Arc progress indicator --------------------------------------------------

function ArcProgress({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const r = 26;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <svg width="70" height="70" viewBox="0 0 70 70" className="-rotate-90">
      <circle cx="35" cy="35" r={r} fill="none" strokeWidth="5" className="stroke-slate-700" />
      <circle
        cx="35"
        cy="35"
        r={r}
        fill="none"
        strokeWidth="5"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="stroke-emerald-400 transition-all duration-1000"
      />
    </svg>
  );
}

// ---- Skeleton ----------------------------------------------------------------

function CardSkeleton() {
  return (
    <div className="card flex flex-col gap-4 animate-pulse">
      <div className="skeleton h-4 w-24 rounded" />
      <div className="skeleton h-8 w-36 rounded" />
      <div className="skeleton h-3 w-20 rounded" />
    </div>
  );
}

// ---- Individual Cards --------------------------------------------------------

function AtRiskCard({ amount }: { amount: number }) {
  const animated = useCountUp(amount);
  return (
    <div className="card group flex flex-col gap-3 hover:bg-white/[0.06] transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
          Total Revenue at Risk
        </p>
        <span className="p-2 rounded-lg bg-amber-950/60 ring-1 ring-amber-700/30">
          <AlertTriangle size={14} className="text-amber-400" strokeWidth={2} />
        </span>
      </div>
      <p className="text-2xl font-bold tracking-tight text-amber-300">
        {formatINR(animated)}
      </p>
      <p className="text-xs text-slate-500">Pending + escalated cases</p>
    </div>
  );
}

function RecoveredCard({ amount }: { amount: number }) {
  const animated = useCountUp(amount);
  return (
    <div className="card group flex flex-col gap-3 hover:bg-white/[0.06] transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
          Total Recovered
        </p>
        <span className="p-2 rounded-lg bg-emerald-950/60 ring-1 ring-emerald-700/30">
          <CheckCircle2 size={14} className="text-emerald-400" strokeWidth={2} />
        </span>
      </div>
      <p className="text-2xl font-bold tracking-tight text-emerald-300">
        {formatINR(animated)}
      </p>
      <p className="text-xs text-slate-500">Successfully recovered payments</p>
    </div>
  );
}

function RecoveryRateCard({ pct, recoveredCount }: { pct: number; recoveredCount: number }) {
  return (
    <div className="card group flex flex-col gap-3 hover:bg-white/[0.06] transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
          Recovery Rate
        </p>
        <span className="p-2 rounded-lg bg-blue-950/60 ring-1 ring-blue-700/30">
          <TrendingUp size={14} className="text-blue-400" strokeWidth={2} />
        </span>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative flex items-center justify-center">
          <ArcProgress pct={pct} />
          <span className="absolute text-sm font-bold text-white rotate-90">
            {pct.toFixed(1)}%
          </span>
        </div>
        <div>
          <p className="text-2xl font-bold tracking-tight text-blue-300">
            {pct.toFixed(1)}%
          </p>
          <p className="text-xs text-slate-500 mt-0.5">{recoveredCount} cases recovered</p>
        </div>
      </div>
    </div>
  );
}

function ActiveCasesCard({ count }: { count: number }) {
  const animated = useCountUp(count);
  return (
    <div className="card group flex flex-col gap-3 hover:bg-white/[0.06] transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
          Active Cases
        </p>
        <span className="p-2 rounded-lg bg-purple-950/60 ring-1 ring-purple-700/30">
          <RefreshCw size={14} className="text-purple-400 animate-spin-slow" strokeWidth={2} />
        </span>
      </div>
      <p className="text-2xl font-bold tracking-tight text-purple-300">
        {Math.round(animated)}
      </p>
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
        <p className="text-xs text-slate-500">Pending + escalated</p>
      </div>
    </div>
  );
}

// ---- Main Component ----------------------------------------------------------

interface MetricsHeaderProps {
  metrics: MetricsSummary | null;
  loading: boolean;
  error?: string | null;
}

export default function MetricsHeader({ metrics, loading, error }: MetricsHeaderProps) {
  if (error) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="card col-span-full text-center py-8 text-red-400 text-sm">
          Failed to load metrics: {error}
        </div>
      </div>
    );
  }

  if (loading || !metrics) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 animate-fade-in">
      <AtRiskCard amount={metrics.total_at_risk_amount} />
      <RecoveredCard amount={metrics.total_recovered_amount} />
      <RecoveryRateCard pct={metrics.recovery_rate_pct} recoveredCount={metrics.recovered_cases_count} />
      <ActiveCasesCard count={metrics.active_cases_count} />
    </div>
  );
}
