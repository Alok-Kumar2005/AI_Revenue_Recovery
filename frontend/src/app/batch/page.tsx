"use client";

// src/app/batch/page.tsx — Live Batch Recovery Simulation

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Circle,
  DatabaseZap,
  Play,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { fetchCases, resetTestCases, seedDemoCases, triggerBatchRecovery } from "@/lib/api";
import type { CaseListItem } from "@/lib/types";
import { useToast } from "@/components/Toast";

// ── Environment gate ───────────────────────────────────────────────────────
// Demo controls are visible in development OR when the explicit env flag is set.
const IS_DEMO_MODE =
  process.env.NEXT_PUBLIC_ENABLE_DEMO_CONTROLS === "true" ||
  process.env.NODE_ENV === "development";

// ---- Log entry --------------------------------------------------------------

interface LogEntry {
  ts: string;
  type: "info" | "success" | "error" | "warn";
  message: string;
}

function logEntry(message: string, type: LogEntry["type"] = "info"): LogEntry {
  return {
    ts: new Date().toLocaleTimeString("en-IN"),
    type,
    message,
  };
}

const LOG_COLORS: Record<LogEntry["type"], string> = {
  info:    "text-slate-400",
  success: "text-emerald-400",
  error:   "text-red-400",
  warn:    "text-amber-400",
};

const LOG_PREFIX: Record<LogEntry["type"], string> = {
  info:    "[INFO]   ",
  success: "[OK]     ",
  error:   "[ERROR]  ",
  warn:    "[WARN]   ",
};

// ---- Counters card ----------------------------------------------------------

function CounterCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="card flex flex-col gap-1 text-center">
      <p className={`text-3xl font-bold tracking-tight ${color}`}>{value}</p>
      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
    </div>
  );
}

// ---- Demo Controls bar ──────────────────────────────────────────────────────

function DemoControlsBar({
  onSeeded,
  onReset,
}: {
  onSeeded: () => void;
  onReset: () => void;
}) {
  const { showToast } = useToast();
  const [seeding, setSeeding]   = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await seedDemoCases(5);
      showToast(`${res.seeded_count} Test Cases Added`, "success");
      onSeeded();
    } catch (e: unknown) {
      showToast(
        `Seed failed: ${e instanceof Error ? e.message : String(e)}`,
        "error",
      );
    } finally {
      setSeeding(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      const res = await resetTestCases();
      showToast(
        `${res.reset_count} case${res.reset_count !== 1 ? "s" : ""} reset to PENDING`,
        "success",
      );
      onReset();
    } catch (e: unknown) {
      showToast(
        `Reset failed: ${e instanceof Error ? e.message : String(e)}`,
        "error",
      );
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Divider */}
      <span className="hidden sm:block h-6 w-px bg-slate-700" />

      {/* Seed button */}
      <button
        id="seed-demo-btn"
        onClick={handleSeed}
        disabled={seeding || resetting}
        title="Seed 5 synthetic PENDING cases for demo"
        className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg
          bg-gradient-to-r from-violet-600/80 to-purple-600/80
          hover:from-violet-500 hover:to-purple-500
          text-white text-xs font-semibold shadow-md shadow-violet-900/30
          disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {seeding ? (
          <RefreshCw size={12} className="animate-spin" />
        ) : (
          <DatabaseZap size={12} />
        )}
        {seeding ? "Seeding…" : "Seed Demo Cases"}
      </button>

      {/* Reset button */}
      <button
        id="reset-cases-btn"
        onClick={handleReset}
        disabled={seeding || resetting}
        title="Reset all cases back to PENDING"
        className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg
          bg-gradient-to-r from-amber-600/80 to-orange-600/80
          hover:from-amber-500 hover:to-orange-500
          text-white text-xs font-semibold shadow-md shadow-amber-900/30
          disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {resetting ? (
          <RefreshCw size={12} className="animate-spin" />
        ) : (
          <RotateCcw size={12} />
        )}
        {resetting ? "Resetting…" : "Reset All to Pending"}
      </button>

      {/* Staging badge */}
      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider
        bg-violet-500/15 border border-violet-500/30 text-violet-300 uppercase">
        Staging
      </span>
    </div>
  );
}

// ---- Main Page --------------------------------------------------------------

type BatchPhase = "idle" | "dispatching" | "polling" | "done";

export default function BatchPage() {
  const [phase, setPhase]           = useState<BatchPhase>("idle");
  const [logs, setLogs]             = useState<LogEntry[]>([]);
  const [dispatchedIds, setDispatched] = useState<string[]>([]);
  const [snapshots, setSnapshots]   = useState<Record<string, CaseListItem>>({});
  const [recovered, setRecovered]   = useState(0);
  const [failed, setFailed]         = useState(0);
  const [processed, setProcessed]   = useState(0);
  const [refreshKey, setRefreshKey] = useState(0); // bump to re-fetch case list

  const logRef    = useRef<HTMLDivElement>(null);
  const pollRef   = useRef<NodeJS.Timeout | null>(null);
  const pollCount = useRef(0);

  const addLog = useCallback((msg: string, type: LogEntry["type"] = "info") => {
    setLogs((prev) => [...prev, logEntry(msg, type)]);
  }, []);

  // Auto-scroll log window
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Poll cases for status changes
  const pollStatus = useCallback(
    async (ids: string[]) => {
      pollCount.current += 1;
      addLog(`Polling case statuses… (round ${pollCount.current})`);

      try {
        // Fetch recent cases (large limit to cover all dispatched)
        const res = await fetchCases(undefined, 100, 0);
        const dispatched = res.items.filter((c) => ids.includes(c.id));

        let rec = 0;
        let fail = 0;
        let proc = 0;

        for (const c of dispatched) {
          const prev = snapshots[c.id];
          if (c.status !== "PENDING" && c.status !== "ESCALATED") {
            proc += 1;
            if (c.status === "RECOVERED") {
              rec += 1;
              if (!prev || prev.status !== c.status) {
                addLog(
                  `Case ${c.id.slice(0, 8)}… RECOVERED via AI agent.`,
                  "success"
                );
              }
            } else if (c.status === "FAILED" || c.status === "DELAYED") {
              fail += 1;
              if (!prev || prev.status !== c.status) {
                addLog(`Case ${c.id.slice(0, 8)}… resolved as ${c.status}.`, "warn");
              }
            }
          }
        }

        setSnapshots(Object.fromEntries(dispatched.map((c) => [c.id, c])));
        setRecovered(rec);
        setFailed(fail);
        setProcessed(proc);

        // All done?
        if (proc >= ids.length || pollCount.current >= 20) {
          stopPolling();
          setPhase("done");
          addLog(
            `Batch complete. Recovered: ${rec}  Failed/Delayed: ${fail}`,
            "success"
          );
        }
      } catch (e: unknown) {
        addLog(
          `Poll error: ${e instanceof Error ? e.message : String(e)}`,
          "error"
        );
      }
    },
    [addLog, snapshots, stopPolling]
  );

  // Start batch
  const handleStart = useCallback(async () => {
    if (phase === "dispatching" || phase === "polling") return;

    // Reset
    setLogs([]);
    setDispatched([]);
    setSnapshots({});
    setRecovered(0);
    setFailed(0);
    setProcessed(0);
    pollCount.current = 0;
    stopPolling();

    setPhase("dispatching");
    addLog("Initiating batch recovery engine…");

    try {
      const res = await triggerBatchRecovery();
      const ids = res.case_ids;
      setDispatched(ids);
      addLog(
        `Dispatched ${res.total_dispatched} Celery recovery task(s).`,
        "success"
      );

      if (ids.length === 0) {
        addLog("No PENDING cases found. Nothing to process.", "warn");
        setPhase("done");
        return;
      }

      setPhase("polling");
      addLog("Polling for case status updates every 3 seconds…");
      pollRef.current = setInterval(() => pollStatus(ids), 3000);
    } catch (e: unknown) {
      addLog(
        `Failed to start batch: ${e instanceof Error ? e.message : String(e)}`,
        "error"
      );
      setPhase("idle");
    }
  }, [addLog, phase, pollStatus, stopPolling]);

  // Clean up on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  const total = dispatchedIds.length;
  const progressPct = total > 0 ? Math.round((processed / total) * 100) : 0;

  // Handlers for demo controls — trigger UI refresh
  const handleSeeded  = () => setRefreshKey((k) => k + 1);
  const handleReset   = () => {
    setLogs([]);
    setDispatched([]);
    setSnapshots({});
    setRecovered(0);
    setFailed(0);
    setProcessed(0);
    setPhase("idle");
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 tracking-tight">
          Live Batch Recovery Simulation
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Dispatch Celery recovery tasks for all PENDING cases and track real-time progress.
        </p>
      </div>

      {/* Control bar: Start + Demo Controls (env-gated) */}
      <div className="card flex flex-col sm:flex-row items-start sm:items-center gap-4 flex-wrap">
        {/* Start button */}
        <button
          id="batch-start-btn"
          onClick={handleStart}
          disabled={phase === "dispatching" || phase === "polling"}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-sm font-semibold shadow-lg shadow-emerald-900/30 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {phase === "dispatching" || phase === "polling" ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          {phase === "dispatching"
            ? "Dispatching…"
            : phase === "polling"
            ? "Processing…"
            : "Start Recovery Batch Engine"}
        </button>

        {phase === "done" && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-400 font-medium">
            <CheckCircle2 size={14} />
            Batch complete
          </span>
        )}

        {phase === "idle" && logs.length === 0 && !IS_DEMO_MODE && (
          <p className="text-xs text-slate-500">
            Will fetch all PENDING cases and dispatch async Celery tasks.
          </p>
        )}

        {/* Demo Controls — only rendered in dev / staging */}
        {IS_DEMO_MODE && (
          <DemoControlsBar onSeeded={handleSeeded} onReset={handleReset} />
        )}
      </div>

      {/* Hidden refresh signal for external consumers (e.g. refreshKey logs) */}
      {refreshKey > 0 && logs.length === 0 && (
        <p className="text-xs text-slate-600 -mt-3">
          Case list refreshed ({refreshKey} update{refreshKey !== 1 ? "s" : ""})
        </p>
      )}

      {/* Counters */}
      {total > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <CounterCard label="Dispatched" value={total}     color="text-slate-200" />
          <CounterCard label="Processed"  value={processed} color="text-blue-300" />
          <CounterCard label="Recovered"  value={recovered} color="text-emerald-300" />
        </div>
      )}

      {/* Progress bar */}
      {total > 0 && (
        <div className="card space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Recovery Progress</span>
            <span className="font-mono">{processed} / {total} ({progressPct}%)</span>
          </div>
          <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-teal-500 transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <CheckCircle2 size={11} className="text-emerald-400" />
              Recovered: {recovered}
            </span>
            <span className="flex items-center gap-1">
              <XCircle size={11} className="text-red-400" />
              Failed/Delayed: {failed}
            </span>
            <span className="flex items-center gap-1">
              <Circle size={11} className="text-slate-500" />
              Remaining: {Math.max(0, total - processed)}
            </span>
          </div>
        </div>
      )}

      {/* Live event log */}
      {logs.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-200 mb-3">
            Live Event Log
          </h2>
          <div
            ref={logRef}
            className="h-72 overflow-y-auto rounded-lg bg-surface-950 border border-slate-800 p-3 font-mono text-[11px] space-y-0.5"
          >
            {logs.map((entry, i) => (
              <p key={i} className={LOG_COLORS[entry.type]}>
                <span className="text-slate-600">{entry.ts} </span>
                <span className="text-slate-600">{LOG_PREFIX[entry.type]}</span>
                {entry.message}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
