"use client";

import React, { useEffect, useRef, useState } from "react";
import { Bell, CheckCheck, Circle } from "lucide-react";
import { cn } from "@/lib/cn";

export interface ConsoleNotificationItem {
  id: number | string;
  title: string;
  message: string;
  type?: string;
  is_read?: boolean;
  created_at?: string;
}

export interface NotificationPanelProps {
  notifications: ConsoleNotificationItem[];
  onMarkAllRead?: () => void;
  onMarkOneRead?: (id: number | string) => void;
  onViewAll?: () => void;
}

/**
 * Header notification trigger & popover panel.
 * IMPORTANT: Intentionally uses `<span className="relative">` instead of `<div className="relative">`
 * so Playwright's `header div.relative > button` selector continues to target the account profile menu cleanly.
 */
export function NotificationPanel({
  notifications,
  onMarkAllRead,
  onMarkOneRead,
  onViewAll,
}: NotificationPanelProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLSpanElement>(null);

  const unreadCount = notifications.filter((n) => n.is_read === false).length;

  useEffect(() => {
    if (!open) return;
    const handleOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    window.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      window.removeEventListener("keydown", handleEsc);
    };
  }, [open]);

  return (
    <span ref={panelRef} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Open notifications panel"
        aria-expanded={open}
        className="relative w-9 h-9 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle hover:border-strong text-secondary hover:text-primary flex items-center justify-center transition-colors"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-brand-500 text-white text-[10px] font-bold flex items-center justify-center tabular-nums-lining">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed sm:absolute right-3 sm:right-0 top-14 sm:top-full sm:mt-2 w-[calc(100vw-1.5rem)] sm:w-88 max-w-sm rounded-2xl bg-surface border border-strong shadow-modal z-50 overflow-hidden animate-fadeIn">
          <div className="px-4 py-3 border-b border-subtle bg-surface-2/70 flex items-center justify-between gap-2">
            <div>
              <h4 className="text-xs font-bold text-primary">Notifications</h4>
              <p className="text-[11px] text-muted">
                {unreadCount > 0
                  ? `${unreadCount} unread update${unreadCount === 1 ? "" : "s"}`
                  : `${notifications.length} recent alert${notifications.length === 1 ? "" : "s"}`}
              </p>
            </div>
            {onMarkAllRead && unreadCount > 0 && (
              <button
                type="button"
                onClick={() => onMarkAllRead()}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-console-300 hover:text-console-200 transition-colors"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all</span>
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-subtle">
            {notifications.slice(0, 8).map((n) => (
              <div
                key={n.id}
                onClick={() => {
                  if (n.is_read === false && onMarkOneRead) {
                    onMarkOneRead(n.id);
                  }
                }}
                className={cn(
                  "px-4 py-3 text-xs transition-colors",
                  n.is_read === false
                    ? "bg-console-500/8 hover:bg-console-500/12 cursor-pointer"
                    : "hover:bg-surface-2/60"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {n.is_read === false && (
                      <Circle className="w-2 h-2 fill-brand-500 text-brand-500 shrink-0" />
                    )}
                    <span className="font-semibold text-primary truncate">
                      {n.title}
                    </span>
                  </div>
                  {n.created_at && (
                    <span className="text-[10px] text-muted font-mono shrink-0">
                      {n.created_at.slice(0, 16).replace("T", " ")}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-secondary mt-1 line-clamp-2 leading-relaxed">
                  {n.message}
                </p>
              </div>
            ))}

            {notifications.length === 0 && (
              <div className="px-4 py-8 text-center text-xs text-muted">
                No notifications available yet.
              </div>
            )}
          </div>

          {onViewAll && (
            <div className="px-4 py-2.5 border-t border-subtle bg-surface-2/40">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onViewAll();
                }}
                className="w-full text-center text-xs font-semibold text-console-300 hover:text-console-200 transition-colors"
              >
                Open Full Notifications Feed
              </button>
            </div>
          )}
        </div>
      )}
    </span>
  );
}

