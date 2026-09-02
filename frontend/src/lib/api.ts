// src/lib/api.ts
// Native-fetch API client for the AI Revenue Recovery backend.
//
// Browser calls go through the Next.js /api/* rewrite proxy so no hard-coded
// port appears in client-side requests.
// Server-side calls (RSC / Route Handlers) fall back to NEXT_PUBLIC_API_URL
// because the rewrite proxy only runs in the browser.

import type {
  BatchStartResponse,
  CaseDetail,
  CaseListResponse,
  ChatMessageItem,
  ChatResponse,
  MetricsSummary,
} from "./types";

// ── Base URL resolution ────────────────────────────────────────────────────

const SERVER_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Resolves to "" (relative) in the browser (rewrite proxy applies) or the
 *  full server URL when running in a Node.js RSC context. */
function base(): string {
  return typeof window === "undefined" ? SERVER_BASE : "";
}

// ── Generic fetch helper ────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${base()}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    // 15-second hard timeout via AbortSignal
    signal: options.signal ?? AbortSignal.timeout(15_000),
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.message ?? detail;
    } catch {
      /* ignore JSON parse errors */
    }
    throw new ApiError(res.status, `[${res.status}] ${detail}`);
  }

  return res.json() as Promise<T>;
}

// ── Metrics ────────────────────────────────────────────────────────────────

export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  return apiFetch<MetricsSummary>("/api/metrics/summary");
}

// ── Cases ──────────────────────────────────────────────────────────────────

export async function fetchCases(
  status?: string,
  limit = 20,
  offset = 0,
): Promise<CaseListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) params.set("status", status);
  return apiFetch<CaseListResponse>(`/api/cases?${params.toString()}`);
}

export async function fetchCaseDetail(id: string): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/api/cases/${id}`);
}

// ── Nudge Dispatch ─────────────────────────────────────────────────────────

export interface NudgeResult {
  case_id: string;
  channel: string;
  status: string;
  message_id?: string | null;
  detail?: string | null;
}

/**
 * Trigger a manual outreach nudge for a specific case.
 * @param caseId - UUID of the RevenueCase
 * @param channel - "EMAIL" | "SMS" | "WHATSAPP"
 */
export async function dispatchNudge(
  caseId: string,
  channel: "EMAIL" | "SMS" | "WHATSAPP",
): Promise<NudgeResult> {
  return apiFetch<NudgeResult>(`/api/cases/${caseId}/nudge`, {
    method: "POST",
    body: JSON.stringify({ channel }),
  });
}

// ── Batch Recovery ─────────────────────────────────────────────────────────

export async function triggerBatchRecovery(): Promise<BatchStartResponse> {
  return apiFetch<BatchStartResponse>("/api/batch/start-recovery", {
    method: "POST",
  });
}

// ── Health ─────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{
  status: string;
  database: string;
}> {
  // Health endpoint is NOT under /api, so we always use the full server URL
  // (it won't be rewritten by Next.js). In the browser we call it directly.
  const url = `${SERVER_BASE}/health`;
  const res = await fetch(url, {
    cache: "no-store",
    signal: AbortSignal.timeout(4_000),
  });
  return res.json();
}

// ── AI Copilot Chat ────────────────────────────────────────────────────────

/**
 * Send a user query to the AI Copilot backend router with conversation history.
 * @param message - The user's prompt
 * @param history - Array of previous chat message objects
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessageItem[] = [],
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

// ── PDF Demand Letter ──────────────────────────────────────────────────────

/**
 * Returns the direct URL to the demand-letter PDF for a given case.
 * Opens in a new browser tab via window.open or an <a target="_blank"> link.
 * Always points to the backend at 127.0.0.1:8000 (not the Next.js proxy)
 * so the browser can render the PDF natively.
 * @param caseId - UUID of the RevenueCase
 */
export function getCasePdfUrl(caseId: string): string {
  return `${SERVER_BASE}/api/cases/${caseId}/pdf`;
}

// ── Admin / Demo Controls ──────────────────────────────────────────────────

export interface SeedDemoResponse {
  status: string;
  seeded_count: number;
  case_ids: string[];
}

export interface ResetCasesResponse {
  status: string;
  reset_count: number;
}

/**
 * Seed synthetic PENDING revenue cases for demo/staging purposes.
 * Calls POST /api/admin/seed-test-cases?count=N
 * @param count - Number of cases to seed (1–100, default 5)
 */
export async function seedDemoCases(count = 5): Promise<SeedDemoResponse> {
  return apiFetch<SeedDemoResponse>(
    `/api/admin/seed-test-cases?count=${count}`,
    { method: "POST" },
  );
}

/**
 * Reset all revenue cases to PENDING status.
 * Calls POST /api/admin/reset-test-cases
 */
export async function resetTestCases(): Promise<ResetCasesResponse> {
  return apiFetch<ResetCasesResponse>("/api/admin/reset-test-cases", {
    method: "POST",
  });
}

// ── Payment Reconciliation Simulation ──────────────────────────────────────

export interface SimulatePaymentResult {
  status: string;          // "RECOVERED" | "ALREADY_RECOVERED"
  case_id: string;
  amount_paid: number;
  provider: string;
  payment_ref?: string | null;
  message?: string | null;
}

/**
 * Trigger the UI-driven payment simulation for a specific case.
 * Calls POST /api/webhooks/simulate and returns the reconciliation result.
 * @param caseId   - UUID of the RevenueCase to reconcile
 * @param amount   - Amount that was paid (e.g. 4999.00)
 * @param provider - Payment provider label (default "Razorpay")
 */
export async function simulatePayment(
  caseId: string,
  amount: number,
  provider: string = "Razorpay",
): Promise<SimulatePaymentResult> {
  return apiFetch<SimulatePaymentResult>("/api/webhooks/simulate", {
    method: "POST",
    body: JSON.stringify({
      case_id: caseId,
      amount_paid: amount,
      provider,
    }),
  });
}
