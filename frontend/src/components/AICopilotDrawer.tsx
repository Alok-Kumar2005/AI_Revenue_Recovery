"use client";

// src/components/AICopilotDrawer.tsx
// Interactive AI Copilot Chat Assistant slide-over drawer with in-memory React state.

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  Sparkles,
  X,
  Trash2,
  Send,
  Loader2,
  Zap,
  CheckCircle2,
  AlertCircle,
  MessageSquare,
  Mail,
  Smartphone,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { dispatchNudge, sendChatMessage } from "@/lib/api";
import type { ChatAction, ChatMessageItem, CopilotMessage } from "@/lib/types";

interface AICopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const INITIAL_SUGGESTIONS = [
  "Summarize critical cases",
  "What is our current recovery rate?",
  "Draft nudge for top overdue case",
  "How much revenue is at risk?",
];

const INITIAL_MESSAGES: CopilotMessage[] = [
  {
    id: "welcome-1",
    sender: "assistant",
    text: "Hello! I am your **AI Revenue Recovery Copilot**.\n\nI monitor real-time payment drop-offs, evaluate recovery KPIs, and can help you immediately trigger smart outreach nudges.\n\nHow can I help you optimize revenue today?",
    suggestions: INITIAL_SUGGESTIONS,
    timestamp: "Just now",
  },
];

// Helper to format simple markdown-like text (bold, monospace code, bullets)
function FormattedMessage({ content }: { content: string }) {
  const lines = content.split("\n");

  return (
    <div className="space-y-1.5 text-sm leading-relaxed text-slate-200">
      {lines.map((line, idx) => {
        if (!line.trim()) {
          return <div key={idx} className="h-1.5" />;
        }

        // Heading markdown
        if (line.startsWith("### ")) {
          return (
            <h4 key={idx} className="font-semibold text-white text-base mt-2 mb-1">
              {line.replace("### ", "")}
            </h4>
          );
        }

        // Bullet point
        const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("* ");
        const cleanLine = isBullet ? line.trim().substring(2) : line;

        // Parse bold **text** and `code` tokens
        const parts = cleanLine.split(/(\*\*.*?\*\*|`.*?`)/g);

        const renderedLine = parts.map((part, pIdx) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={pIdx} className="font-semibold text-white">
                {part.slice(2, -2)}
              </strong>
            );
          }
          if (part.startsWith("`") && part.endsWith("`")) {
            return (
              <code
                key={pIdx}
                className="px-1.5 py-0.5 rounded bg-surface-900 border border-white/[0.1] font-mono text-xs text-emerald-300"
              >
                {part.slice(1, -1)}
              </code>
            );
          }
          return part;
        });

        if (isBullet) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="text-emerald-400 mt-1 text-xs">•</span>
              <span>{renderedLine}</span>
            </div>
          );
        }

        return <p key={idx}>{renderedLine}</p>;
      })}
    </div>
  );
}

export default function AICopilotDrawer({ isOpen, onClose }: AICopilotDrawerProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<CopilotMessage[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Track dispatched actions: caseId -> status ("dispatching" | "success" | "error")
  const [actionStatus, setActionStatus] = useState<Record<string, { status: string; detail?: string }>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [messages, isOpen, isLoading]);

  // Handle ESC key to close drawer
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Extract conversation history for multi-turn prompt
  const getChatHistory = (): ChatMessageItem[] => {
    return messages
      .filter((m) => m.id !== "welcome-1")
      .map((m) => ({
        role: m.sender,
        content: m.text,
      }));
  };

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText ?? input).trim();
    if (!textToSend || isLoading) return;

    const userMessage: CopilotMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const history = getChatHistory();
      const response = await sendChatMessage(textToSend, history);

      const assistantMessage: CopilotMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: response.reply,
        action: response.action?.type !== "NONE" ? response.action : undefined,
        suggestions: response.suggestions?.length ? response.suggestions : INITIAL_SUGGESTIONS,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const errorMsg: CopilotMessage = {
        id: `error-${Date.now()}`,
        sender: "assistant",
        text: "I encountered an issue retrieving real-time data. Please check your backend connection or retry in a moment.",
        suggestions: INITIAL_SUGGESTIONS,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        sender: "assistant",
        text: "Chat cleared! How can I assist you with revenue recovery operations right now?",
        suggestions: INITIAL_SUGGESTIONS,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    setActionStatus({});
  };

  const handleTriggerNudge = async (action: ChatAction) => {
    if (!action.case_id) return;
    const caseId = action.case_id;
    const channel = (action.channel?.toUpperCase() ?? "EMAIL") as "EMAIL" | "SMS" | "WHATSAPP";

    setActionStatus((prev) => ({
      ...prev,
      [caseId]: { status: "dispatching" },
    }));

    try {
      const result = await dispatchNudge(caseId, channel);
      setActionStatus((prev) => ({
        ...prev,
        [caseId]: {
          status: "success",
          detail: `Dispatched via ${channel} (${result.status})`,
        },
      }));
    } catch (err: unknown) {
      setActionStatus((prev) => ({
        ...prev,
        [caseId]: {
          status: "error",
          detail: err instanceof Error ? err.message : "Dispatch failed",
        },
      }));
    }
  };

  const activeSuggestions =
    messages[messages.length - 1]?.suggestions && messages[messages.length - 1]?.suggestions?.length
      ? messages[messages.length - 1].suggestions!
      : INITIAL_SUGGESTIONS;

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Slide-over Panel */}
      <aside
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[460px] glass-heavy border-l border-white/[0.08] shadow-2xl flex flex-col bg-surface-950/95 backdrop-blur-2xl transition-transform duration-300 ease-out transform ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="h-[64px] px-5 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-surface-900/50">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-900/30">
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-white tracking-tight">
                  AI Recovery Copilot
                </span>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-300 ring-1 ring-emerald-600/40">
                  Live Ops
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Context-Aware Financial Assistant</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleClearChat}
              title="Clear chat history"
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors focus-ring"
            >
              <Trash2 size={15} />
            </button>
            <button
              onClick={onClose}
              title="Close Copilot"
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors focus-ring"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => {
            const isUser = msg.sender === "user";

            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isUser ? "items-end" : "items-start"} animate-fade-in`}
              >
                <div
                  className={`flex gap-2.5 max-w-[90%] ${
                    isUser ? "flex-row-reverse" : "flex-row"
                  }`}
                >
                  {/* Bot Avatar */}
                  {!isUser && (
                    <div className="h-7 w-7 rounded-full bg-surface-800 border border-white/[0.1] flex items-center justify-center shrink-0 mt-0.5 text-emerald-400">
                      <Bot size={15} />
                    </div>
                  )}

                  <div className="space-y-2">
                    {/* Message Bubble */}
                    <div
                      className={`p-3.5 rounded-2xl shadow-sm ${
                        isUser
                          ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-tr-sm text-sm"
                          : "glass rounded-tl-sm border border-white/[0.08] bg-surface-900/70"
                      }`}
                    >
                      {isUser ? (
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                      ) : (
                        <FormattedMessage content={msg.text} />
                      )}
                    </div>

                    {/* Interactive Action Card if DISPATCH_NUDGE */}
                    {msg.action?.type === "DISPATCH_NUDGE" && msg.action.case_id && (
                      <div className="p-3.5 rounded-xl bg-surface-900 border border-emerald-500/30 shadow-lg space-y-2.5 text-xs animate-slide-up">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5 font-semibold text-emerald-400 text-xs">
                            <Zap size={13} className="text-amber-400" />
                            Recommended Action: Outreach Nudge
                          </span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] bg-emerald-950 text-emerald-300 ring-1 ring-emerald-600/40">
                            {msg.action.channel ?? "WHATSAPP"}
                          </span>
                        </div>

                        <div className="p-2.5 rounded-lg bg-surface-950/60 border border-white/[0.04] space-y-1">
                          <div className="flex justify-between text-slate-300">
                            <span className="text-slate-500">Recipient:</span>
                            <span className="font-medium text-slate-200">
                              {msg.action.customer_name ?? "Valued Customer"}
                            </span>
                          </div>
                          {msg.action.amount && (
                            <div className="flex justify-between text-slate-300">
                              <span className="text-slate-500">Amount:</span>
                              <span className="font-semibold text-emerald-400">
                                ₹{msg.action.amount.toLocaleString("en-IN")}
                              </span>
                            </div>
                          )}
                          {msg.action.reason && (
                            <p className="text-[11px] text-slate-400 italic pt-1 border-t border-white/[0.04]">
                              &ldquo;{msg.action.reason}&rdquo;
                            </p>
                          )}
                        </div>

                        {/* Action status or Trigger Button */}
                        {actionStatus[msg.action.case_id]?.status === "success" ? (
                          <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-950/60 border border-emerald-600/40 text-emerald-300">
                            <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                            <span className="font-medium text-xs">
                              {actionStatus[msg.action.case_id]?.detail ?? "Nudge Dispatched Successfully"}
                            </span>
                          </div>
                        ) : actionStatus[msg.action.case_id]?.status === "error" ? (
                          <div className="flex items-center gap-2 p-2 rounded-lg bg-red-950/60 border border-red-600/40 text-red-300">
                            <AlertCircle size={15} className="text-red-400 shrink-0" />
                            <span className="text-xs">
                              {actionStatus[msg.action.case_id]?.detail ?? "Failed to dispatch nudge"}
                            </span>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleTriggerNudge(msg.action!)}
                            disabled={actionStatus[msg.action.case_id]?.status === "dispatching"}
                            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-surface-950 font-semibold text-xs transition-colors shadow-md shadow-emerald-900/30 disabled:opacity-50"
                          >
                            {actionStatus[msg.action.case_id]?.status === "dispatching" ? (
                              <>
                                <Loader2 size={13} className="animate-spin" />
                                Dispatching {msg.action.channel ?? "Nudge"}…
                              </>
                            ) : (
                              <>
                                {msg.action.channel === "WHATSAPP" ? (
                                  <MessageSquare size={13} />
                                ) : msg.action.channel === "SMS" ? (
                                  <Smartphone size={13} />
                                ) : (
                                  <Mail size={13} />
                                )}
                                Trigger {msg.action.channel ?? "Outreach"} Nudge Now
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Interactive Action Card if NAVIGATE_CASE */}
                    {msg.action?.type === "NAVIGATE_CASE" && msg.action.case_id && (
                      <button
                        onClick={() => {
                          onClose();
                          router.push(`/cases/${msg.action!.case_id}`);
                        }}
                        className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg bg-surface-900 border border-white/[0.1] text-emerald-400 hover:text-emerald-300 text-xs font-medium transition-colors"
                      >
                        <span>Inspect Case #{msg.action.case_id.slice(0, 8)}</span>
                        <ExternalLink size={12} />
                      </button>
                    )}

                    {/* Timestamp */}
                    <p
                      suppressHydrationWarning
                      className={`text-[10px] text-slate-500 px-1 ${isUser ? "text-right" : "text-left"}`}
                    >
                      {msg.timestamp}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex items-start gap-2.5 animate-fade-in">
              <div className="h-7 w-7 rounded-full bg-surface-800 border border-white/[0.1] flex items-center justify-center shrink-0 text-emerald-400">
                <Bot size={15} />
              </div>
              <div className="glass p-3.5 rounded-2xl rounded-tl-sm border border-white/[0.08] bg-surface-900/70 flex items-center gap-2 text-xs text-slate-400">
                <Loader2 size={14} className="animate-spin text-emerald-400" />
                <span>Copilot is analyzing recovery data…</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        {activeSuggestions.length > 0 && (
          <div className="px-4 py-2 border-t border-white/[0.05] bg-surface-900/30">
            <p className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider mb-1.5">
              Suggested Queries
            </p>
            <div className="flex flex-wrap gap-1.5">
              {activeSuggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(suggestion)}
                  disabled={isLoading}
                  className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full glass border border-white/[0.06] text-slate-300 hover:text-emerald-300 hover:border-emerald-500/40 hover:bg-emerald-950/30 transition-all text-left disabled:opacity-50"
                >
                  <span>{suggestion}</span>
                  <ChevronRight size={10} className="text-slate-500 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Bar */}
        <div className="p-4 border-t border-white/[0.08] bg-surface-900/70 shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Copilot anything… (e.g. 'Draft nudge for top case')"
              disabled={isLoading}
              className="flex-1 bg-surface-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="h-10 w-10 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 flex items-center justify-center text-white shadow-md shadow-emerald-900/30 hover:shadow-emerald-700/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all focus-ring shrink-0"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </form>
        </div>
      </aside>
    </>
  );
}
