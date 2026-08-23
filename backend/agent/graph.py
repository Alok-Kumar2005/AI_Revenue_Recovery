import json
import logging
import os
from typing import Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END

from backend.config import settings
from backend.agent.compliance import check_compliance
from backend.agent.llm import get_gemini_llm
from backend.agent.prompts import get_recovery_prompt

logger = logging.getLogger("agent.graph")


class AgentState(TypedDict):
    case_data: Dict[str, Any]
    diagnosis: Dict[str, Any]
    compliance: Dict[str, Any]
    decision: Dict[str, Any]
    outreach_content: Dict[str, Any]


def evaluate_compliance_node(state: AgentState) -> AgentState:
    """
    Node 1: Evaluates compliance stopping rules for the given payment case.
    """
    case_data = state.get("case_data", {})
    compliance_result = check_compliance(case_data)
    logger.info(f"Compliance check result: {compliance_result}")

    new_state = dict(state)
    new_state["compliance"] = compliance_result
    return new_state  # type: ignore


def plan_recovery_node(state: AgentState) -> AgentState:
    """
    Node 2: If compliant, invokes Gemini LLM to select intervention channel and
    draft outreach content. If non-compliant, sets forced stopping decision.
    """
    compliance = state.get("compliance", {})
    case_data = state.get("case_data", {})
    diagnosis = state.get("diagnosis", {})

    new_state = dict(state)

    if not compliance.get("is_compliant", True):
        forced_action = compliance.get("forced_action", "STOP")
        reason = compliance.get("reason", "NON_COMPLIANT")
        logger.info(f"Case non-compliant ({reason}). Forcing action: {forced_action}")

        new_state["decision"] = {
            "chosen_channel": forced_action,
            "urgency_level": "LOW",
            "reasoning": f"Compliance rule triggered: {reason}",
            "is_forced": True,
        }
        new_state["outreach_content"] = {
            "message_subject": "",
            "message_body": "",
        }
        return new_state  # type: ignore

    # Case is compliant -> Invoke Gemini LLM for recovery planning
    amount = case_data.get("amount", 0.0)
    customer_name = case_data.get("customer_name", "Valued Customer")
    failure_reason = case_data.get("failure_reason") or diagnosis.get(
        "failure_reason", "Payment processing failure"
    )
    root_cause = diagnosis.get("root_cause") or diagnosis.get(
        "predicted_cause", "Technical error / Gateway timeout"
    )
    payment_method = case_data.get("payment_method", "UPI")
    retry_count = case_data.get("retry_count", 0)

    prompt = get_recovery_prompt()
    chain_input = {
        "customer_name": customer_name,
        "amount": amount,
        "payment_method": payment_method,
        "failure_reason": failure_reason,
        "root_cause": root_cause,
        "retry_count": retry_count,
    }

    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    use_llm = bool(api_key and not api_key.startswith("MOCK") and api_key != "YOUR_GEMINI_API_KEY")

    try:
        if not use_llm:
            raise ValueError("GEMINI_API_KEY not configured or is a mock key; using recovery logic fallback.")

        llm = get_gemini_llm()
        prompt_value = prompt.format_messages(**chain_input)
        response = llm.invoke(prompt_value)
        content_text = response.content.strip()

        # Clean potential markdown wrapping if present
        if content_text.startswith("```"):
            lines = content_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content_text = "\n".join(lines).strip()

        parsed = json.loads(content_text)

        decision = {
            "chosen_channel": parsed.get("chosen_channel", "WHATSAPP"),
            "urgency_level": parsed.get("urgency_level", "MEDIUM"),
            "reasoning": parsed.get("reasoning", "LLM-recommended recovery strategy."),
            "is_forced": False,
        }
        outreach_content = {
            "message_subject": parsed.get("message_subject", "Payment Action Required"),
            "message_body": parsed.get("message_body", f"Hi {customer_name}, please retry your payment of ₹{amount} here: {{payment_link}}"),
        }
    except Exception as e:
        logger.warning(f"LLM call skipped or failed ({e}). Using recovery strategist logic.")
        # Fallback intelligent strategy when API key is missing or offline
        if payment_method.upper() in ["UPI", "GPAY", "PHONEPE"]:
            chosen_channel = "WHATSAPP"
            urgency = "HIGH"
            reasoning = "UPI payment failure context indicates high mobile conversion on WhatsApp nudge."
            subject = "Quick update on your UPI Payment"
            body = f"Hi {customer_name}, your payment of ₹{amount} via {payment_method} couldn't be completed due to {root_cause}. Tap here to retry easily: {{payment_link}}"
        elif payment_method.upper() == "CARD":
            chosen_channel = "EMAIL"
            urgency = "MEDIUM"
            reasoning = "Card payment failures require detailed instructions via Email."
            subject = "Action Required: Complete your card payment"
            body = f"Dear {customer_name}, your transaction of ₹{amount} failed. Please update your payment details or retry here: {{payment_link}}"
        else:
            chosen_channel = "SMS"
            urgency = "MEDIUM"
            reasoning = "Standard SMS reminder for netbanking/other payment failures."
            subject = "Payment Pending"
            body = f"Hi {customer_name}, retry your payment of ₹{amount} using this link: {{payment_link}}"

        decision = {
            "chosen_channel": chosen_channel,
            "urgency_level": urgency,
            "reasoning": reasoning,
            "is_forced": False,
        }
        outreach_content = {
            "message_subject": subject,
            "message_body": body,
        }

    new_state["decision"] = decision
    new_state["outreach_content"] = outreach_content
    return new_state  # type: ignore


def finalize_decision_node(state: AgentState) -> AgentState:
    """
    Node 3: Formats the final execution payload.
    """
    new_state = dict(state)
    return new_state  # type: ignore


def build_recovery_graph() -> StateGraph:
    """
    Builds the LangGraph StateGraph workflow.
    """
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("evaluate_compliance", evaluate_compliance_node)
    workflow.add_node("plan_recovery", plan_recovery_node)
    workflow.add_node("finalize_decision", finalize_decision_node)

    # Define Edges
    workflow.set_entry_point("evaluate_compliance")
    workflow.add_edge("evaluate_compliance", "plan_recovery")
    workflow.add_edge("plan_recovery", "finalize_decision")
    workflow.add_edge("finalize_decision", END)

    return workflow


def run_recovery_agent(case_data: Dict[str, Any], diagnosis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point to run the AI Decision & Recovery Agent on a case.
    """
    graph = build_recovery_graph()
    app = graph.compile()

    initial_state: AgentState = {
        "case_data": case_data,
        "diagnosis": diagnosis,
        "compliance": {},
        "decision": {},
        "outreach_content": {},
    }

    final_state = app.invoke(initial_state)

    payment_link = case_data.get("payment_link", "https://pay.example.com/retry/default")
    outreach = final_state.get("outreach_content", {})
    body = outreach.get("message_body", "")
    if "{payment_link}" in body:
        body = body.format(payment_link=payment_link)

    return {
        "case_id": case_data.get("case_id") or case_data.get("transaction_id", "N/A"),
        "compliance": final_state.get("compliance"),
        "decision": final_state.get("decision"),
        "outreach_content": {
            "message_subject": outreach.get("message_subject", ""),
            "message_body": body,
            "raw_template": outreach.get("message_body", ""),
            "payment_link": payment_link,
        },
    }
