"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  durationMs?: number;
}

export interface ToastContextValue {
  pushToast: (toast: Omit<ToastItem, "id">) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  dismissToast: (id: string) => void;
}

const noop = () => {};
const fallbackContext: ToastContextValue = {
  pushToast: noop,
  success: noop,
  error: noop,
  warning: noop,
  info: noop,
  dismissToast: noop,
};

const ToastContext = createContext<ToastContextValue>(fallbackContext);

const variantStyles: Record<
  ToastVariant,
  { container: string; icon: React.ReactNode; titleColor: string }
> = {
  success: {
    container: "border-emerald-500/35 bg-surface/95 shadow-elevated",
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
    titleColor: "text-emerald-300",
  },
  error: {
    container: "border-red-500/35 bg-surface/95 shadow-elevated",
    icon: <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />,
    titleColor: "text-red-300",
  },
  warning: {
    container: "border-amber-500/35 bg-surface/95 shadow-elevated",
    icon: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
    titleColor: "text-amber-300",
  },
  info: {
    container: "border-console-500/35 bg-surface/95 shadow-elevated",
    icon: <Info className="w-4 h-4 text-console-400 shrink-0" />,
    titleColor: "text-console-300",
  },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismissToast = useCallback((id: string) => {
    const existingTimer = timersRef.current.get(id);
    if (existingTimer) {
      clearTimeout(existingTimer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const duration = toast.durationMs ?? (toast.variant === "error" ? 6000 : 4000);
      setToasts((prev) => [...prev.slice(-4), { ...toast, id }]);

      if (duration > 0) {
        const timer = setTimeout(() => {
          dismissToast(id);
        }, duration);
        timersRef.current.set(id, timer);
      }
    },
    [dismissToast]
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      pushToast,
      dismissToast,
      success: (title, description) =>
        pushToast({ variant: "success", title, description }),
      error: (title, description) =>
        pushToast({ variant: "error", title, description }),
      warning: (title, description) =>
        pushToast({ variant: "warning", title, description }),
      info: (title, description) =>
        pushToast({ variant: "info", title, description }),
    }),
    [pushToast, dismissToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}

      {toasts.length > 0 && (
        <div
          aria-live="polite"
          aria-label="Console notifications"
          className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2.5 w-[calc(100vw-2rem)] max-w-sm pointer-events-none"
        >
          {toasts.map((toast) => {
            const style = variantStyles[toast.variant];
            return (
              <div
                key={toast.id}
                role="status"
                className={cn(
                  "pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border backdrop-blur-md animate-fadeIn",
                  style.container
                )}
              >
                <div className="mt-0.5">{style.icon}</div>
                <div className="flex-1 min-w-0">
                  <p className={cn("text-xs font-semibold leading-snug", style.titleColor)}>
                    {toast.title}
                  </p>
                  {toast.description ? (
                    <p className="text-[11px] text-secondary mt-0.5 leading-relaxed break-words">
                      {toast.description}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => dismissToast(toast.id)}
                  aria-label="Dismiss notification"
                  className="p-1 -m-1 rounded-md text-muted hover:text-primary hover:bg-surface-2 transition-colors shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

