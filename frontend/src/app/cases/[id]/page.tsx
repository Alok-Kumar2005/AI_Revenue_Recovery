"use client";

// src/app/cases/[id]/page.tsx — Case Detail with Audit Trail + Payment Simulation

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CreditCard, ExternalLink, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { fetchCaseDetail, simulatePayment } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import CaseTimeline from "@/components/CaseTimeline";

// ── Toast types ───────────────────────────────────────────────────────────────

type ToastKind = "success" | "error" | "loading";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

// ── Toast component ───────────────────────────────────────────────────────────

function ToastBanner({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const base =
    "fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl px-5 py-3.5 shadow-2xl " +
    "text-sm font-medium backdrop-blur-sm border transition-all duration-300 animate-slide-up";

  const styles: Record<ToastKind, string> = {
    success:
      "bg-emerald-900/90 border-emerald-500/40 text-emerald-100",
    error:
      "bg-red-900/90 border-red-500/40 text-red-100",
    loading:
      "bg-slate-800/90 border-slate-600/40 text-slate-100",
  };

  const icons: Record<ToastKind, React.ReactNode> = {
    success: <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />,
    error: <XCircle size={16} className="text-red-400 shrink-0" />,
    loading: <Loader2 size={16} className="text-slate-400 shrink-0 animate-spin" />,
  };

  return (
    <div className={`${base} ${styles[toast.kind]}`} role="alert">
      {icons[toast.kind]}
      <span>{toast.message}</span>
      {toast.kind !== "loading" && (
        <button
          onClick={onDismiss}
          className="ml-2 text-current opacity-60 hover:opacity-100 transition-opacity text-xs"
          aria-label="Dismiss"
        >
          ✕
        </button>
      )}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-8 space-y-6 animate-pulse">
      <div className="skeleton h-5 w-48 rounded" />
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="card space-y-3">
            {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-4 w-full rounded" />)}
          </div>
          <div className="card space-y-3">
            {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-4 w-full rounded" />)}
          </div>
        </div>
        <div className="lg:col-span-3">
          <div className="card space-y-4">
            {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-16 w-full rounded" />)}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  // Simulation state
  const [simulating, setSimulating] = useState(false);
  const [toast, setToast]           = useState<Toast | null>(null);
  const toastTimer                  = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load case ───────────────────────────────────────────────────────────────

  const loadCase = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetchCaseDetail(id)
      .then(setCaseDetail)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load case details")
      )
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  // ── Toast helpers ───────────────────────────────────────────────────────────

  const showToast = (kind: ToastKind, message: string, autoDismissMs = 5000) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), kind, message });
    if (kind !== "loading") {
      toastTimer.current = setTimeout(() => setToast(null), autoDismissMs);
    }
  };

  const dismissToast = () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(null);
  };

  // ── Simulate payment ────────────────────────────────────────────────────────

  const handleSimulate = async () => {
    if (!caseDetail || simulating) return;

    setSimulating(true);
    showToast("loading", "Sending payment simulation…");

    try {
      const result = await simulatePayment(caseDetail.id, caseDetail.amount);

      if (result.status === "ALREADY_RECOVERED") {
        showToast("success", "Case is already marked as RECOVERED ✓");
      } else {
        const currency = caseDetail.currency === "INR" ? "₹" : caseDetail.currency + " ";
        showToast(
          "success",
          `Payment of ${currency}${caseDetail.amount.toLocaleString("en-IN")} reconciled successfully! Txn: ${result.payment_ref ?? "—"}`,
          7000,
        );
      }

      // Reload case to reflect the RECOVERED status without a manual refresh
      await fetchCaseDetail(id)
        .then(setCaseDetail)
        .catch(() => { /* non-fatal */ });
    } catch (err: unknown) {
      showToast(
        "error",
        err instanceof Error ? err.message : "Payment simulation failed. Try again.",
      );
    } finally {
      setSimulating(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) return <Skeleton />;

  if (error || !caseDetail) {
    return (
      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="card text-center py-16">
          <p className="text-red-400 font-medium mb-2">Failed to load case</p>
          <p className="text-sm text-slate-500 mb-4">{error}</p>
          <button
            onClick={() => router.back()}
            className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            Go back
          </button>
        </div>
      </div>
    );
  }

  const isAlreadyRecovered = caseDetail.status === "RECOVERED";

  return (
    <div className="mx-auto max-w-7xl px-5 py-8 space-y-6 animate-fade-in">
      {/* Breadcrumb / back */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft size={14} />
          All Cases
        </button>

        <div className="flex items-center gap-3 flex-wrap">
          {/* ── Simulate Payment button ───────────────────────────────────── */}
          <button
            id="btn-simulate-payment"
            onClick={handleSimulate}
            disabled={simulating || isAlreadyRecovered}
            title={
              isAlreadyRecovered
                ? "This case has already been recovered"
                : "Simulate a successful incoming payment to reconcile this case"
            }
            className={[
              "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold",
              "border transition-all duration-200 focus:outline-none focus:ring-2",
              "focus:ring-emerald-500/50 focus:ring-offset-1 focus:ring-offset-transparent",
              isAlreadyRecovered
                ? "border-emerald-700/40 bg-emerald-900/20 text-emerald-500 cursor-not-allowed opacity-60"
                : simulating
                ? "border-indigo-500/40 bg-indigo-900/30 text-indigo-300 cursor-wait"
                : "border-indigo-500/50 bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/40 hover:border-indigo-400/70 hover:text-indigo-100 active:scale-95",
            ].join(" ")}
          >
            {simulating ? (
              <Loader2 size={14} className="animate-spin shrink-0" />
            ) : isAlreadyRecovered ? (
              <CheckCircle2 size={14} className="shrink-0" />
            ) : (
              <CreditCard size={14} className="shrink-0" />
            )}
            {isAlreadyRecovered
              ? "Already Recovered"
              : simulating
              ? "Reconciling…"
              : "💳 Simulate Incoming Payment"}
          </button>

          <a
            href={`http://localhost:8000/api/cases/${id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            View raw JSON <ExternalLink size={11} />
          </a>
        </div>
      </div>

      {/* Case heading */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 tracking-tight">
          Case Detail
        </h1>
        <p className="text-xs text-slate-500 font-mono mt-0.5">{id}</p>
      </div>

      {/* Timeline */}
      <CaseTimeline caseDetail={caseDetail} />

      {/* Toast notification */}
      {toast && <ToastBanner toast={toast} onDismiss={dismissToast} />}
    </div>
  );
}
