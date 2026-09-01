"use client";

// src/components/CaseList.tsx
// Searchable, filterable, paginated data table for revenue cases.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { fetchCases } from "@/lib/api";
import type { CaseListItem } from "@/lib/types";

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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ---- Status Badge -----------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  RECOVERED: "badge-green",
  PENDING:   "badge-yellow",
  FAILED:    "badge-red",
  ESCALATED: "badge-blue",
  DELAYED:   "badge-blue",
};

const STATUS_DOTS: Record<string, string> = {
  RECOVERED: "bg-emerald-400",
  PENDING:   "bg-amber-400",
  FAILED:    "bg-red-400",
  ESCALATED: "bg-blue-400",
  DELAYED:   "bg-blue-400",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "badge-slate";
  const dot = STATUS_DOTS[status] ?? "bg-slate-400";
  return (
    <span className={`badge ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}

// ---- Skeleton Row -----------------------------------------------------------

function SkeletonRow() {
  return (
    <tr>
      {[...Array(6)].map((_, i) => (
        <td key={i} className="px-4 py-3.5">
          <div className="skeleton h-4 w-full max-w-[120px] rounded" />
        </td>
      ))}
    </tr>
  );
}

// ---- Main Component ---------------------------------------------------------

const STATUS_OPTIONS = ["", "PENDING", "RECOVERED", "FAILED", "ESCALATED", "DELAYED"];
const PAGE_SIZE = 15;

export default function CaseList() {
  const router = useRouter();

  const [items, setItems]           = useState<CaseListItem[]>([]);
  const [total, setTotal]           = useState(0);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [search, setSearch]         = useState("");
  const [statusFilter, setStatus]   = useState("");
  const [page, setPage]             = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCases(
        statusFilter || undefined,
        PAGE_SIZE,
        page * PAGE_SIZE
      );
      setItems(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => { load(); }, [load]);

  // Client-side search filter (name / email)
  const filtered = search.trim()
    ? items.filter((c) => {
        const q = search.toLowerCase();
        return (
          c.customer?.name?.toLowerCase().includes(q) ||
          c.customer?.email?.toLowerCase().includes(q)
        );
      })
    : items;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="card flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100">Recovery Cases</h2>
          <p className="text-xs text-slate-500 mt-0.5">{total} total cases</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          {/* Search */}
          <div className="relative">
            <Search
              size={13}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            />
            <input
              id="case-search"
              type="text"
              placeholder="Search by name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full sm:w-56 rounded-lg bg-surface-800 border border-slate-700 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-600 transition-colors"
            />
          </div>

          {/* Status filter */}
          <div className="relative">
            <SlidersHorizontal
              size={13}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
            />
            <select
              id="case-status-filter"
              value={statusFilter}
              onChange={(e) => { setStatus(e.target.value); setPage(0); }}
              className="h-8 w-full sm:w-40 rounded-lg bg-surface-800 border border-slate-700 pl-8 pr-3 text-xs text-slate-200 focus:outline-none focus:border-emerald-600 transition-colors appearance-none"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s || "All Statuses"}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="text-sm text-red-400 bg-red-950/40 border border-red-800/40 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-surface-900/60">
              {["Customer", "Email", "Amount", "Root Cause", "Status", "Date"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading
              ? [...Array(6)].map((_, i) => <SkeletonRow key={i} />)
              : filtered.length === 0
              ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-500 text-sm">
                    No cases found
                  </td>
                </tr>
              )
              : filtered.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => router.push(`/cases/${c.id}`)}
                  className="group cursor-pointer hover:bg-white/[0.03] transition-colors"
                >
                  <td className="px-4 py-3.5 font-medium text-slate-200 group-hover:text-white transition-colors">
                    {c.customer?.name ?? "—"}
                  </td>
                  <td className="px-4 py-3.5 text-slate-400 text-xs">
                    {c.customer?.email ?? "—"}
                  </td>
                  <td className="px-4 py-3.5 font-mono text-xs text-slate-300">
                    {formatINR(c.amount, c.currency)}
                  </td>
                  <td className="px-4 py-3.5 text-slate-400 text-xs max-w-[180px] truncate">
                    {c.failure_reason ?? "—"}
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3.5 text-slate-500 text-xs whitespace-nowrap">
                    {formatDate(c.created_at)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-slate-500">
            Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-800 border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={12} /> Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-800 border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next <ChevronRight size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
