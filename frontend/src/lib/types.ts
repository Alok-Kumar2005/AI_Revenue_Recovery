// src/lib/types.ts
// TypeScript interfaces mirroring backend Pydantic schemas (backend/schemas.py)

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
}

export interface Intervention {
  id: string;
  channel: string;
  status: string;
  message_payload?: string | null;
  sent_at?: string | null;
}

export interface AuditLog {
  id: string;
  event: string;
  actor: string;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface MetricsSummary {
  total_at_risk_amount: number;
  total_recovered_amount: number;
  recovery_rate_pct: number;
  active_cases_count: number;
  recovered_cases_count: number;
}

export interface CaseListItem {
  id: string;
  amount: number;
  currency: string;
  status: string;
  risk_level: string;
  failure_reason?: string | null;
  retry_count: number;
  created_at: string;
  customer?: Customer | null;
}

export interface CaseListResponse {
  total: number;
  limit: number;
  offset: number;
  items: CaseListItem[];
}

export interface CaseDetail {
  id: string;
  razorpay_payment_id?: string | null;
  razorpay_order_id?: string | null;
  amount: number;
  currency: string;
  status: string;
  risk_level: string;
  failure_reason?: string | null;
  root_cause?: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  customer?: Customer | null;
  interventions: Intervention[];
  audit_logs: AuditLog[];
}

export interface BatchStartResponse {
  status: string;
  total_dispatched: number;
  case_ids: string[];
}

// ── Chat Copilot Types ──────────────────────────────────────────────────────

export interface ChatAction {
  type: "DISPATCH_NUDGE" | "NAVIGATE_CASE" | "NONE";
  case_id?: string | null;
  channel?: "EMAIL" | "SMS" | "WHATSAPP" | null;
  customer_name?: string | null;
  amount?: number | null;
  reason?: string | null;
}

export interface ChatMessageItem {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  message: string;
  history?: ChatMessageItem[];
}

export interface ChatResponse {
  reply: string;
  action: ChatAction;
  suggestions: string[];
}

export interface CopilotMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  action?: ChatAction;
  suggestions?: string[];
  timestamp: string;
}

