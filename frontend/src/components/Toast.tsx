"use client";

// src/components/Toast.tsx
// Lightweight toast notification system — no external library required.
//
// Usage:
//   1. Wrap your app with <ToastProvider> (done in layout.tsx)
//   2. In any client component:
//        const { showToast } = useToast();
//        showToast("5 Test Cases Added", "success");

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CheckCircle2, Info, XCircle, X } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  /** Whether the toast is in the exit animation phase */
  exiting: boolean;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

// ── Context ───────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

// ── Hook ──────────────────────────────────────────────────────────────────

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return ctx;
}

// ── Config ─────────────────────────────────────────────────────────────────

const DISMISS_MS   = 3500; // time until exit animation starts
const ANIMATE_MS   = 300;  // duration of exit animation (matches CSS)

const TOAST_STYLES: Record<ToastType, { bar: string; icon: JSX.Element }> = {
  success: {
    bar: "border-emerald-500/50 bg-emerald-500/10",
    icon: <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />,
  },
  error: {
    bar: "border-red-500/50 bg-red-500/10",
    icon: <XCircle size={16} className="text-red-400 shrink-0" />,
  },
  info: {
    bar: "border-slate-500/40 bg-slate-700/30",
    icon: <Info size={16} className="text-slate-400 shrink-0" />,
  },
};

// ── Individual Toast item ─────────────────────────────────────────────────

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (id: string) => void;
}) {
  const styles = TOAST_STYLES[toast.type];

  return (
    <div
      className={`
        flex items-start gap-3 w-80 max-w-[90vw] px-4 py-3 rounded-xl
        border backdrop-blur-md shadow-2xl shadow-black/40
        text-sm text-slate-100 font-medium
        transition-all duration-300 ease-out
        ${styles.bar}
        ${
          toast.exiting
            ? "opacity-0 translate-x-8 scale-95"
            : "opacity-100 translate-x-0 scale-100"
        }
      `}
      role="alert"
      aria-live="polite"
    >
      {styles.icon}
      <span className="flex-1 leading-snug">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-slate-500 hover:text-slate-300 transition-colors mt-0.5 shrink-0"
        aria-label="Dismiss notification"
      >
        <X size={13} />
      </button>
    </div>
  );
}

// ── Toaster (renders all active toasts) ───────────────────────────────────

function Toaster({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="fixed top-[68px] right-4 z-[9999] flex flex-col gap-2.5"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ── Provider ──────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  // Track per-toast dismiss timers so we can clean them up on unmount
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: string) => {
    // Start exit animation
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)),
    );
    // Remove from DOM after animation completes
    const removeTimer = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      timers.current.delete(id);
    }, ANIMATE_MS);
    timers.current.set(`${id}-remove`, removeTimer);
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { id, message, type, exiting: false }]);

      // Auto-dismiss after DISMISS_MS
      const t = setTimeout(() => removeToast(id), DISMISS_MS);
      timers.current.set(id, t);
    },
    [removeToast],
  );

  // Clear all timers on unmount
  useEffect(() => {
    const captured = timers.current;
    return () => {
      captured.forEach((t) => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <Toaster toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  );
}
