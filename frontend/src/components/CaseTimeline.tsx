"use client";

// src/components/CaseTimeline.tsx
// Two-panel layout: customer + diagnosis on the left, vertical audit log on the right.

import { useState } from "react";
import {
  Bell,
  Bot,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  Cpu,
  Mail,
  Search,
  ShieldCheck,
  User,
} from "lucide-react";
import type { AuditLog, CaseDetail, Intervention } from "@/lib/types";

// ---- Helpers -----------------------------------------------------------------

function formatINR(amount: number, currency: string): string {
  if (currency === "INR") {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  }
  return `${currency} ${amount.toFixed(2)}`;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---- Status Styles ----------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  RECOVERED: "badge-green",
  PENDING:   "badge-yellow",
  FAILED:    "badge-red",
  ESCALATED: "badge-blue",
  DELAYED:   "badge-blue",
};

const RISK_STYLES: Record<string, string> = {
  HIGH:   "badge-red",
  MEDIUM: "badge-yellow",
  LOW:    "badge-green",
};

// ---- Event Icon + Color map -------------------------------------------------

interface EventMeta {
  icon: React.ReactNode;
  label: string;
  accent: string; // Tailwind ring/border color
  dotColor: string;
}

function getEventMeta(event: string): EventMeta {
  const upper = event.toUpperCase();
  if (upper.includes("WEBHOOK") || upper.includes("RECEIVED")) {
    return {
      icon: <Bell size={13} strokeWidth={2} />,
      label: "Webhook Received",
      accent: "ring-slate-600",
      dotColor: "bg-slate-400",
    };
  }
  if (upper.includes("DIAGNOS") || upper.includes("FAILURE")) {
    return {
      icon: <Search size={13} strokeWidth={2} />,
      label: "Failure Diagnosed",
      accent: "ring-amber-700",
      dotColor: "bg-amber-400",
    };
  }
  if (upper.includes("STRATEGY") || upper.includes("ORCHESTR") || upper.includes("DECISION")) {
    return {
      icon: <Bot size={13} strokeWidth={2} />,
      label: "AI Strategy Selected",
      accent: "ring-purple-700",
      dotColor: "bg-purple-400",
    };
  }
  if (upper.includes("POLICY") || upper.includes("COMPLIANCE") || upper.includes("GATE")) {
    return {
      icon: <ShieldCheck size={13} strokeWidth={2} />,
      label: "Policy Gate Validated",
      accent: "ring-blue-700",
      dotColor: "bg-blue-400",
    };
  }
  if (upper.includes("OUTREACH") || upper.includes("DISPATCH") || upper.includes("SENT") || upper.includes("NUDGE")) {
    return {
      icon: <Mail size={13} strokeWidth={2} />,
      label: "Outreach Dispatched",
      accent: "ring-teal-700",
      dotColor: "bg-teal-400",
    };
  }
  if (upper.includes("PIPELINE") || upper.includes("EXECUTED")) {
    return {
      icon: <Cpu size={13} strokeWidth={2} />,
      label: "Recovery Pipeline Executed",
      accent: "ring-emerald-700",
      dotColor: "bg-emerald-400",
    };
  }
  return {
    icon: <CheckCheck size={13} strokeWidth={2} />,
    label: event,
    accent: "ring-slate-700",
    dotColor: "bg-slate-400",
  };
}

// ---- Timeline Event Card ----------------------------------------------------

function TimelineEvent({ log, index }: { log: AuditLog; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const meta = getEventMeta(log.event);

  return (
    <div className="relative flex gap-4 animate-slide-up" style={{ animationDelay: `${index * 60}ms` }}>
      {/* Vertical line */}
      <div className="flex flex-col items-center">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 ${meta.accent} bg-surface-900 text-slate-300 z-10`}
        >
          {meta.icon}
        </span>
        <div className="w-px flex-1 bg-slate-800 mt-1" />
      </div>

      {/* Content */}
      <div className="pb-6 flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-slate-200">{meta.label}</p>
            <p className="text-xs text-slate-500 mt-0.5 font-mono">{log.event}</p>
          </div>
          <time className="text-xs text-slate-500 whitespace-nowrap shrink-0 pt-0.5">
            {formatDateTime(log.created_at)}
          </time>
        </div>

        <p className="text-xs text-slate-500 mt-1">Actor: <span className="text-slate-400">{log.actor}</span></p>

        {/* Expandable JSON */}
        {log.details && Object.keys(log.details).length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {expanded ? "Hide" : "Show"} raw payload
            </button>
            {expanded && (
              <pre className="mt-2 p-3 rounded-lg bg-surface-900 border border-slate-800 text-[11px] text-slate-400 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-64">
                {JSON.stringify(log.details, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Intervention Chips -----------------------------------------------------

function InterventionChip({ iv }: { iv: Intervention }) {
  const channelColor: Record<string, string> = {
    EMAIL:    "badge-blue",
    SMS:      "badge-yellow",
    WHATSAPP: "badge-green",
    RETRY:    "badge-purple",
    ESCALATE: "badge-red",
  };
  const cls = channelColor[iv.channel.toUpperCase()] ?? "badge-slate";
  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-900 border border-slate-800 px-3 py-2 text-xs">
      <span className={`badge ${cls}`}>{iv.channel}</span>
      <span className={`badge ${iv.status === "SENT" ? "badge-green" : "badge-slate"}`}>
        {iv.status}
      </span>
      {iv.sent_at && (
        <span className="text-slate-500">{formatDateTime(iv.sent_at)}</span>
      )}
    </div>
  );
}

// ---- Main Component ---------------------------------------------------------

export default function CaseTimeline({ caseDetail }: { caseDetail: CaseDetail }) {
  const {
    customer,
    audit_logs,
    interventions,
    status,
    risk_level,
    amount,
    currency,
    root_cause,
    failure_reason,
    retry_count,
    razorpay_payment_id,
  } = caseDetail;

  // Extract diagnosis confidence from the first pipeline-executed audit log
  const pipelineLog = audit_logs.find((l) =>
    l.event.toUpperCase().includes("PIPELINE")
  );
  const confidence: number | null =
    (pipelineLog?.details as Record<string, { confidence?: number }> | null)
      ?.diagnosis?.confidence ?? null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* ---- Left panel ---- */}
      <div className="lg:col-span-2 flex flex-col gap-4">
        {/* Customer card */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-slate-700 to-slate-800 ring-1 ring-slate-600">
              <User size={16} className="text-slate-300" />
            </span>
            <div>
              <p className="font-semibold text-slate-100">{customer?.name ?? "Unknown"}</p>
              <p className="text-xs text-slate-400">{customer?.email ?? "—"}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Phone</span>
              <span className="text-slate-300">{customer?.phone ?? "—"}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Amount</span>
              <span className="text-slate-300 font-mono">{formatINR(amount, currency)}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Status</span>
              <span className={`badge ${STATUS_STYLES[status] ?? "badge-slate"} w-fit`}>{status}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Risk Level</span>
              <span className={`badge ${RISK_STYLES[risk_level] ?? "badge-slate"} w-fit`}>{risk_level}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Retry Count</span>
              <span className="text-slate-300">{retry_count}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Payment ID</span>
              <span className="text-slate-300 font-mono truncate">{razorpay_payment_id ?? "—"}</span>
            </div>
          </div>
        </div>

        {/* AI Diagnosis card */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Bot size={14} className="text-purple-400" />
            <h3 className="text-sm font-semibold text-slate-200">AI Diagnosis</h3>
          </div>
          <div className="space-y-2.5 text-xs">
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Root Cause Classification</span>
              <span className="text-slate-200 font-medium">{root_cause ?? failure_reason ?? "Not diagnosed"}</span>
            </div>
            {confidence !== null && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-slate-500">Confidence Score</span>
                  <span className="text-slate-300 font-mono">{(confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-purple-600 to-purple-400 transition-all duration-700"
                    style={{ width: `${confidence * 100}%` }}
                  />
                </div>
              </div>
            )}
            <div className="flex flex-col gap-0.5">
              <span className="text-slate-500">Failure Reason</span>
              <span className="text-slate-300">{failure_reason ?? "—"}</span>
            </div>
          </div>
        </div>

        {/* Interventions */}
        {interventions.length > 0 && (
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Outreach Interventions</h3>
            <div className="space-y-2">
              {interventions.map((iv) => (
                <InterventionChip key={iv.id} iv={iv} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ---- Right panel: Timeline ---- */}
      <div className="lg:col-span-3">
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-5">
            Audit Trail
            <span className="ml-2 badge badge-slate">{audit_logs.length} events</span>
          </h3>

          {audit_logs.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-8">
              No audit events recorded for this case.
            </p>
          ) : (
            <div className="space-y-0">
              {audit_logs.map((log, i) => (
                <TimelineEvent key={log.id} log={log} index={i} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
