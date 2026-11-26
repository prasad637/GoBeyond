"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { DashboardNavItem } from "./DashboardSidebar";

export interface DashboardMobileNavProps {
  title: string;
  subtitle?: string;
  navItems: DashboardNavItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  headerIdentity?: React.ReactNode;
  footer?: React.ReactNode;
}

export function DashboardMobileNav({
  title,
  subtitle,
  navItems,
  activeTab,
  onTabChange,
  drawerOpen,
  onCloseDrawer,
  headerIdentity,
  footer,
}: DashboardMobileNavProps) {
  useEffect(() => {
    if (!drawerOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseDrawer();
    };
    window.addEventListener("keydown", handleEsc);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", handleEsc);
    };
  }, [drawerOpen, onCloseDrawer]);

  if (!navItems.length) return null;

  return (
    <>
      {/* Responsive Quick Pill Strip (<lg) contained safely to avoid horizontal page overflow */}
      <div className="lg:hidden w-full overflow-hidden bg-surface/75 border-b border-subtle">
        <div className="px-3 py-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {navItems.map((item) => {
            const isActive = item.id === activeTab;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap border transition-colors shrink-0",
                  isActive
                    ? "bg-console-600 border-console-500 text-white font-semibold"
                    : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                )}
              >
                <span className="shrink-0 flex items-center">{item.icon}</span>
                <span>{item.label}</span>
                {item.badge !== undefined && Number(item.badge) > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-brand-500 text-white text-[10px] font-bold leading-none tabular-nums-lining">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Mobile / Tablet Slide-over Drawer */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden flex"
          role="dialog"
          aria-modal="true"
          aria-label={`${title} navigation drawer`}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onCloseDrawer();
          }}
        >
          <div
            aria-hidden="true"
            onClick={onCloseDrawer}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm animate-fadeIn"
          />

          <div className="relative z-10 w-72 max-w-[85vw] bg-surface border-r border-strong h-full p-5 flex flex-col justify-between overflow-y-auto shadow-modal">
            <div className="space-y-5">
              <div className="flex items-center justify-between pb-3 border-b border-subtle">
                <div className="min-w-0">
                  <div className="font-display font-bold text-sm text-primary truncate">
                    {title}
                  </div>
                  {subtitle && (
                    <div className="text-[11px] text-muted mt-0.5 truncate">
                      {subtitle}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onCloseDrawer}
                  aria-label="Close console navigation"
                  className="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-2 shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {headerIdentity}

              <div className="space-y-1 text-xs font-medium">
                {navItems.map((item) => {
                  const isActive = item.id === activeTab;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        onTabChange(item.id);
                        onCloseDrawer();
                      }}
                      className={cn(
                        "w-full flex items-center justify-between gap-2.5 px-3 py-2.5 rounded-xl transition-colors text-left",
                        isActive
                          ? "bg-console-600/20 text-console-200 border border-console-500/30 font-semibold"
                          : "text-secondary hover:text-primary hover:bg-surface-2 border border-transparent"
                      )}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <span className="shrink-0">{item.icon}</span>
                        <span className="truncate">{item.label}</span>
                      </span>
                      {item.badge !== undefined && Number(item.badge) > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-bold tabular-nums-lining">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="pt-4 border-t border-subtle space-y-3">
              {footer}
              <Link
                href="/"
                onClick={onCloseDrawer}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-surface-2 border border-subtle text-xs font-semibold text-primary hover:border-strong transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Customer App</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

