"use client";

// src/app/page.tsx — Main Dashboard Overview

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { fetchCases, fetchMetricsSummary } from "@/lib/api";
import type { Intervention, MetricsSummary } from "@/lib/types";
import MetricsHeader from "@/components/MetricsHeader";
import CaseList from "@/components/CaseList";
import StrategyBreakdown from "@/components/StrategyBreakdown";

const REFRESH_INTERVAL = 30_000;

export default function DashboardPage() {
  const [metrics, setMetrics]               = useState<MetricsSummary | null>(null);
  const [interventions, setInterventions]   = useState<Intervention[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError]     = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed]   = useState<Date | null>(null);
  const [refreshing, setRefreshing]         = useState(false);

  const loadMetrics = useCallback(async (silent = false) => {
    if (!silent) setMetricsLoading(true);
    else setRefreshing(true);
    setMetricsError(null);
    try {
      const [m, casesRes] = await Promise.all([
        fetchMetricsSummary(),
        fetchCases(undefined, 100, 0),
      ]);
      setMetrics(m);
      // Flatten all interventions for StrategyBreakdown
      // (case list items don't carry interventions — use a derived placeholder)
      // We derive a synthetic list from the case statuses for the breakdown
      const synthetic: Intervention[] = casesRes.items.flatMap((c) =>
        c.status === "RECOVERED"
          ? [{ id: c.id, channel: "EMAIL", status: "SENT" }]
          : []
      );
      setInterventions(synthetic);
      setLastRefreshed(new Date());
    } catch (e: unknown) {
      setMetricsError(e instanceof Error ? e.message : "Failed to load metrics");
    } finally {
      setMetricsLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
    const id = setInterval(() => loadMetrics(true), REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [loadMetrics]);

  return (
    <div className="mx-auto max-w-7xl px-5 py-8 space-y-6 animate-fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Revenue Recovery Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time overview of AI-driven payment recovery operations
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <p className="text-xs text-slate-600 hidden sm:block">
              Updated {lastRefreshed.toLocaleTimeString("en-IN")}
            </p>
          )}
          <button
            onClick={() => loadMetrics(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-800 border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <MetricsHeader
        metrics={metrics}
        loading={metricsLoading}
        error={metricsError}
      />

      {/* Cases + Breakdown */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        <div className="xl:col-span-3">
          <CaseList />
        </div>
        <div className="xl:col-span-1">
          <StrategyBreakdown interventions={interventions} />
        </div>
      </div>
    </div>
  );
}
