"""
backend/routers/chat.py
───────────────────────
FastAPI router for the interactive AI Copilot Chat Assistant.

Features:
- Dynamic Database Context Injection (KPIs, high/critical risk cases, top overdue transactions)
- Multi-Turn In-Memory Short-Term Memory (preserves recent context across turns)
- Input Token Budgeting (sliding window keeping the last 2k tokens of input context)
- Output Token Limit (configured to 512 tokens max output)
- Structured Action Extraction (DISPATCH_NUDGE, NAVIGATE_CASE, NONE)
- Real-Time Fallback Strategist (guarantees 100% reliability even if LLM is offline)

Prefix : /api   (mounted in main.py)
Endpoint: POST /api/chat
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.config import settings
from backend.database import get_db
from backend.models import AuditLog, Customer, Intervention, RecoveryMetric, RevenueCase

logger = logging.getLogger(__name__)

router = APIRouter()

# Input and Output token limits
MAX_INPUT_TOKEN_BUDGET = 2000  # Last 2k tokens for conversation history context
MAX_OUTPUT_TOKENS = 512        # Strict 512 output token limit


# ── Pydantic Request / Response Models ───────────────────────────────────────

class ChatMessageItem(BaseModel):
    role: str = Field(..., description="'user' or 'assistant' or 'system'")
    content: str = Field(..., description="Message text content")

    model_config = ConfigDict(extra="ignore")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's query or prompt")
    history: Optional[List[ChatMessageItem]] = Field(
        default=[],
        description="Prior conversation turns for in-memory short-term context",
    )

    model_config = ConfigDict(extra="ignore")


class ChatAction(BaseModel):
    type: str = Field(
        default="NONE",
        description="Action type: DISPATCH_NUDGE | NAVIGATE_CASE | NONE",
    )
    case_id: Optional[str] = Field(
        default=None,
        description="Target case UUID if action applies to a specific case",
    )
    channel: Optional[str] = Field(
        default=None,
        description="Outreach channel if DISPATCH_NUDGE: EMAIL | SMS | WHATSAPP",
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Name of the customer associated with the case",
    )
    amount: Optional[float] = Field(
        default=None,
        description="Amount of the transaction at risk",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Brief justification for the recommended action",
    )

    model_config = ConfigDict(extra="ignore")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Conversational markdown response from AI Copilot")
    action: ChatAction = Field(default_factory=ChatAction, description="Executable action metadata")
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up quick prompt chips",
    )

    model_config = ConfigDict(extra="ignore")


# ── Token Budget & Short-Term Memory Helpers ────────────────────────────────

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string (~4 characters per token + framing overhead).
    """
    if not text:
        return 0
    return max(1, (len(text) // 4) + 2)


def prune_history_to_token_budget(
    history: Optional[List[ChatMessageItem]],
    max_tokens: int = MAX_INPUT_TOKEN_BUDGET,
) -> List[ChatMessageItem]:
    """
    In-Memory Short-Term Memory Manager:
    Selects the most recent conversation turns that fit within the 2,000 input token budget.
    Iterates backward from latest turn to ensure immediate recent context is preserved.
    """
    if not history:
        return []

    accumulated_tokens = 0
    pruned_turns: List[ChatMessageItem] = []

    # Traverse from most recent to oldest
    for turn in reversed(history):
        turn_tokens = estimate_tokens(turn.content) + 4  # +4 for role metadata
        if accumulated_tokens + turn_tokens > max_tokens:
            break
        accumulated_tokens += turn_tokens
        pruned_turns.append(turn)

    # Restore chronological order
    pruned_turns.reverse()
    logger.debug(
        f"[Copilot Memory] Preserved {len(pruned_turns)}/{len(history)} turns (~{accumulated_tokens} tokens)"
    )
    return pruned_turns


# ── Context Gathering Helper ────────────────────────────────────────────────

def get_system_context(db: Session) -> dict:
    """
    Query live aggregates and critical records from the database to ground the LLM
    in real-time operational context.
    """
    # 1. Aggregate KPI metrics
    row = db.query(
        func.coalesce(
            func.sum(RevenueCase.amount).filter(
                RevenueCase.status.in_(["PENDING", "ESCALATED"])
            ),
            0.0,
        ).label("at_risk_amount"),
        func.coalesce(
            func.sum(RevenueCase.amount).filter(
                RevenueCase.status == "RECOVERED"
            ),
            0.0,
        ).label("recovered_amount"),
        func.count(RevenueCase.id).filter(
            RevenueCase.status.in_(["PENDING", "ESCALATED"])
        ).label("active_count"),
        func.count(RevenueCase.id).filter(
            RevenueCase.status == "RECOVERED"
        ).label("recovered_count"),
    ).one()

    at_risk_amount: float = float(row.at_risk_amount)
    recovered_from_cases: float = float(row.recovered_amount)
    active_cases_count: int = int(row.active_count)
    recovered_cases_count: int = int(row.recovered_count)

    metrics_row = db.query(
        func.coalesce(func.sum(RecoveryMetric.total_recovered), 0.0).label("metrics_recovered")
    ).one()
    total_recovered = max(recovered_from_cases, float(metrics_row.metrics_recovered))
    total_at_risk = at_risk_amount

    denominator = total_at_risk + total_recovered
    recovery_rate_pct = (total_recovered / denominator * 100.0) if denominator > 0 else 0.0

    # 2. High / Critical risk count
    high_risk_count = db.query(RevenueCase).filter(
        RevenueCase.status.in_(["PENDING", "ESCALATED"]),
        RevenueCase.risk_level.in_(["HIGH", "CRITICAL"]),
    ).count()

    # 3. Top at-risk cases (ordered by amount descending)
    top_cases = (
        db.query(RevenueCase)
        .options(joinedload(RevenueCase.customer))
        .filter(RevenueCase.status.in_(["PENDING", "ESCALATED"]))
        .order_by(RevenueCase.amount.desc())
        .limit(6)
        .all()
    )

    case_summaries = []
    for c in top_cases:
        cust_name = c.customer.name if c.customer else "Unknown Customer"
        cust_email = c.customer.email if c.customer else "N/A"
        cust_phone = c.customer.phone if c.customer else "N/A"
        case_summaries.append({
            "case_id": str(c.id),
            "customer_name": cust_name,
            "email": cust_email,
            "phone": cust_phone,
            "amount": c.amount,
            "currency": c.currency,
            "status": c.status,
            "risk_level": c.risk_level,
            "failure_reason": c.failure_reason or "Unknown failure",
            "root_cause": c.root_cause or "Payment timeout",
            "retry_count": c.retry_count,
        })

    # 4. Recent interventions
    recent_interventions = (
        db.query(Intervention)
        .order_by(Intervention.sent_at.desc().nullslast())
        .limit(4)
        .all()
    )
    intervention_summaries = [
        {
            "id": str(i.id),
            "case_id": str(i.case_id),
            "channel": i.channel,
            "status": i.status,
            "sent_at": i.sent_at.isoformat() if i.sent_at else None,
        }
        for i in recent_interventions
    ]

    return {
        "kpi": {
            "total_at_risk_amount": round(total_at_risk, 2),
            "total_recovered_amount": round(total_recovered, 2),
            "recovery_rate_pct": round(recovery_rate_pct, 2),
            "active_cases_count": active_cases_count,
            "recovered_cases_count": recovered_cases_count,
            "high_risk_cases_count": high_risk_count,
        },
        "top_at_risk_cases": case_summaries,
        "recent_interventions": intervention_summaries,
    }


# ── Intelligent Contextual Fallback Engine ──────────────────────────────────

def build_fallback_response(
    user_msg: str,
    context: dict,
    history: Optional[List[ChatMessageItem]] = None,
) -> ChatResponse:
    """
    Deterministic context-aware answer generator used when LLM is offline or unconfigured.
    Utilizes short-term memory from recent history to resolve pronouns or follow-up references.
    """
    msg_lower = user_msg.lower().strip()
    kpi = context["kpi"]
    top_cases = context["top_at_risk_cases"]

    # Check previous conversation turns to maintain short-term conversational context
    recent_context_text = ""
    if history:
        recent_context_text = " ".join([h.content.lower() for h in history[-3:]])

    # Intent 1: Trigger / Draft Nudge
    if any(k in msg_lower for k in ["nudge", "send outreach", "trigger nudge", "draft nudge", "contact", "remind", "outreach"]):
        if top_cases:
            target_case = top_cases[0]

            # 1. Match from current message
            matched = False
            for c in top_cases:
                if c["customer_name"].lower() in msg_lower:
                    target_case = c
                    matched = True
                    break

            # 2. If not in current message, match from recent short-term memory (e.g. "nudge him")
            if not matched and recent_context_text:
                for c in top_cases:
                    if c["customer_name"].lower() in recent_context_text:
                        target_case = c
                        break

            channel = "WHATSAPP" if target_case["amount"] > 3000 or "upi" in target_case["failure_reason"].lower() else "EMAIL"

            reply = (
                f"I've prepared a recommended recovery nudge for **{target_case['customer_name']}**.\n\n"
                f"- **Case ID**: `{target_case['case_id'][:8]}...`\n"
                f"- **Amount**: ₹{target_case['amount']:,.2f} ({target_case['currency']})\n"
                f"- **Risk Level**: `{target_case['risk_level']}`\n"
                f"- **Failure Reason**: {target_case['failure_reason']}\n"
                f"- **Recommended Channel**: **{channel}** (Highest conversion probability)\n\n"
                f"You can trigger this outreach immediately using the action card below."
            )
            action = ChatAction(
                type="DISPATCH_NUDGE",
                case_id=target_case["case_id"],
                channel=channel,
                customer_name=target_case["customer_name"],
                amount=target_case["amount"],
                reason=f"High-priority recovery nudge for failed transaction ({target_case['failure_reason']}).",
            )
            suggestions = [
                "What is our current recovery rate?",
                "Show all high-risk cases",
                "Summarize critical cases",
            ]
            return ChatResponse(reply=reply, action=action, suggestions=suggestions)
        else:
            return ChatResponse(
                reply="There are currently no active pending cases requiring a nudge.",
                action=ChatAction(type="NONE"),
                suggestions=["What is our recovery rate?", "Show metrics summary"],
            )

    # Intent 2: High-risk / Critical cases inquiry
    if any(k in msg_lower for k in ["high risk", "critical", "highest risk", "overdue", "risk"]):
        if not top_cases:
            reply = "Great news! There are currently no critical or high-risk active revenue cases."
        else:
            case_lines = []
            for idx, c in enumerate(top_cases[:4], 1):
                case_lines.append(
                    f"{idx}. **{c['customer_name']}** — **₹{c['amount']:,.2f}** "
                    f"(`{c['risk_level']}` risk, reason: _{c['failure_reason']}_)"
                )
            reply = (
                f"We currently have **{kpi['high_risk_cases_count']} high/critical risk cases** "
                f"representing **₹{kpi['total_at_risk_amount']:,.2f}** in at-risk revenue:\n\n"
                + "\n".join(case_lines)
                + "\n\nWould you like me to draft an outreach nudge for the highest at-risk customer?"
            )
        suggestions = [
            "Draft nudge for top overdue case",
            "What is our current recovery rate?",
            "How much revenue is at risk?",
        ]
        return ChatResponse(reply=reply, action=ChatAction(type="NONE"), suggestions=suggestions)

    # Intent 3: Recovery rate & Metrics inquiry
    if any(k in msg_lower for k in ["recovery rate", "rate", "metrics", "summary", "stats", "kpi", "performance", "at risk", "recovered"]):
        reply = (
            f"### 📊 Live Recovery Operations Summary\n\n"
            f"- **Recovery Rate**: **{kpi['recovery_rate_pct']}%**\n"
            f"- **Total Recovered**: **₹{kpi['total_recovered_amount']:,.2f}** ({kpi['recovered_cases_count']} cases)\n"
            f"- **Total At-Risk**: **₹{kpi['total_at_risk_amount']:,.2f}** ({kpi['active_cases_count']} active cases)\n"
            f"- **High-Risk Cases**: **{kpi['high_risk_cases_count']} cases**\n\n"
            f"The system is actively monitoring incoming Razorpay webhooks and executing compliant recovery workflows."
        )
        suggestions = [
            "Show high-risk cases",
            "Draft nudge for top overdue case",
            "What are the top failure causes?",
        ]
        return ChatResponse(reply=reply, action=ChatAction(type="NONE"), suggestions=suggestions)

    # Intent 4: Default / General assistant overview
    reply = (
        f"Hello! I am your **AI Revenue Recovery Copilot**.\n\n"
        f"I monitor real-time payment failures, analyze recovery performance, and help execute automated outreach workflows.\n\n"
        f"Currently, we are tracking **₹{kpi['total_at_risk_amount']:,.2f}** at risk with a **{kpi['recovery_rate_pct']}%** recovery rate across **{kpi['active_cases_count']}** active cases.\n\n"
        f"How can I assist you right now?"
    )
    suggestions = [
        "Summarize critical cases",
        "What is our current recovery rate?",
        "Draft nudge for top overdue case",
    ]
    return ChatResponse(reply=reply, action=ChatAction(type="NONE"), suggestions=suggestions)


# ── POST /api/chat ─────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Interactive AI Copilot chat query and action extraction",
    tags=["Chat"],
)
def chat_copilot(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Process an in-memory chat message from the operator with short-term memory management.
    - Limits input history window to the last 2k tokens so context is never lost.
    - Limits LLM generation to 512 tokens max output.
    - Dynamically injects live database metrics & top cases into the LLM prompt.
    - Returns structured reply, suggested next prompts, and optional executable action metadata.
    """
    user_query = request.message.strip()
    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )

    # Manage In-Memory Short-Term Memory within 2,000 Token Budget
    pruned_history = prune_history_to_token_budget(request.history, max_tokens=MAX_INPUT_TOKEN_BUDGET)

    # Fetch live dynamic context
    context = get_system_context(db)

    # Check if Gemini LLM is enabled and configured with a valid API key
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    use_llm = bool(api_key and api_key.startswith("AIza") and not api_key.startswith("MOCK") and api_key != "YOUR_GEMINI_API_KEY")

    if not use_llm:
        logger.info("[Copilot] Using intelligent contextual fallback engine with short-term memory.")
        return build_fallback_response(user_query, context, pruned_history)

    # Build prompt for Gemini LLM with max 512 output token constraint
    system_instruction = (
        "You are the AI Revenue Recovery Copilot, an expert financial operations strategist and executive assistant "
        "integrated into the AI Revenue Recovery dashboard.\n\n"
        "Your task is to answer operator questions clearly and concisely, analyze payment failure patterns, maintain conversation "
        "context across turns, and suggest or prepare recovery actions (such as dispatching Email, SMS, or WhatsApp nudges).\n\n"
        "=== LIVE SYSTEM CONTEXT ===\n"
        f"{json.dumps(context, indent=2)}\n"
        "===========================\n\n"
        "Guidelines:\n"
        "1. Provide clear, accurate, concise markdown answers using the live data and previous conversation history.\n"
        "2. When quoting monetary values, always use Indian Rupees (₹).\n"
        "3. Keep replies focused and compact (under 512 output tokens).\n"
        "4. If the user asks to nudge, recover, reach out to, or intervene on a case (e.g., 'nudge top case', 'nudge him', 'recover case'), set action type to 'DISPATCH_NUDGE', populate the matching case_id, recommended channel ('EMAIL' | 'SMS' | 'WHATSAPP'), customer_name, amount, and reason.\n"
        "5. If the user wants to navigate/inspect a case, set action type to 'NAVIGATE_CASE' with case_id.\n"
        "6. Otherwise, set action type to 'NONE'.\n"
        "7. Always return 3 helpful, concise follow-up prompt chips in `suggestions`.\n"
        "8. You MUST return ONLY a valid raw JSON object matching this schema:\n"
        "{\n"
        '  "reply": "Your markdown answer string",\n'
        '  "action": {\n'
        '    "type": "DISPATCH_NUDGE" | "NAVIGATE_CASE" | "NONE",\n'
        '    "case_id": "case-uuid-string or null",\n'
        '    "channel": "EMAIL" | "SMS" | "WHATSAPP" | null,\n'
        '    "customer_name": "string or null",\n'
        '    "amount": float or null,\n'
        '    "reason": "string or null"\n'
        "  },\n"
        '  "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]\n'
        "}\n"
        "Do NOT enclose your output in markdown code blocks like ```json ... ```. Return raw JSON only."
    )

    # Construct conversation history messages within token budget
    messages = [("system", system_instruction)]
    for item in pruned_history:
        role = "human" if item.role.lower() in ["user", "human"] else "ai"
        messages.append((role, item.content))
    messages.append(("human", user_query))

    try:
        # Enforce max_output_tokens=512
        llm = get_gemini_llm(max_output_tokens=MAX_OUTPUT_TOKENS)
        response = llm.invoke(messages)
        content_text = response.content.strip()

        # Clean potential markdown wrapping
        if content_text.startswith("```"):
            lines = content_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content_text = "\n".join(lines).strip()

        parsed = json.loads(content_text)

        action_data = parsed.get("action", {})
        action = ChatAction(
            type=action_data.get("type", "NONE"),
            case_id=action_data.get("case_id"),
            channel=action_data.get("channel"),
            customer_name=action_data.get("customer_name"),
            amount=action_data.get("amount"),
            reason=action_data.get("reason"),
        )

        return ChatResponse(
            reply=parsed.get("reply", "Here is the operational breakdown based on current metrics."),
            action=action,
            suggestions=parsed.get("suggestions", [
                "Summarize critical cases",
                "What is our current recovery rate?",
                "Draft nudge for top overdue case",
            ]),
        )

    except Exception as exc:
        logger.warning(f"[Copilot] Gemini LLM invocation failed ({exc}). Falling back to rule-based contextual engine.")
        return build_fallback_response(user_query, context, pruned_history)
