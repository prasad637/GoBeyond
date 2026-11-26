"use client";

import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface DashboardNavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: number | string;
  section?: string;
}

export interface DashboardSidebarProps {
  title: string;
  subtitle?: string;
  navItems: DashboardNavItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  headerIdentity?: React.ReactNode;
  footer?: React.ReactNode;
}

export function DashboardSidebar({
  title,
  subtitle,
  navItems,
  activeTab,
  onTabChange,
  collapsed = false,
  onToggleCollapse,
  headerIdentity,
  footer,
}: DashboardSidebarProps) {
  const groupedSections = React.useMemo(() => {
    const groups: { section: string | null; items: DashboardNavItem[] }[] = [];
    for (const item of navItems) {
      const sec = item.section || null;
      const last = groups[groups.length - 1];
      if (!last || last.section !== sec) {
        groups.push({ section: sec, items: [item] });
      } else {
        last.items.push(item);
      }
    }
    return groups;
  }, [navItems]);

  return (
    <aside
      aria-label={`${title} sidebar`}
      className={cn(
        "hidden lg:flex lg:flex-col shrink-0 bg-surface border-r border-subtle justify-between transition-all duration-200",
        collapsed ? "w-[74px] p-3" : "w-64 p-4 sm:p-5"
      )}
    >
      <div className="space-y-5 min-w-0">
        {!collapsed ? (
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="font-display text-sm sm:text-base font-bold text-primary tracking-tight truncate">
                {title}
              </h2>
              {subtitle ? (
                <p className="text-xs text-muted leading-snug mt-0.5 line-clamp-2">
                  {subtitle}
                </p>
              ) : null}
            </div>
            {onToggleCollapse && (
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
                className="w-7 h-7 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-muted hover:text-primary flex items-center justify-center shrink-0 transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ) : (
          onToggleCollapse && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Expand sidebar"
                title="Expand sidebar"
                className="w-9 h-9 rounded-xl bg-surface-2 hover:bg-surface-3 border border-subtle text-secondary hover:text-primary flex items-center justify-center transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )
        )}

        {!collapsed && headerIdentity ? <div>{headerIdentity}</div> : null}

        <nav aria-label={`${title} navigation`} className="space-y-4">
          {groupedSections.map((group, gIdx) => (
            <div key={`${group.section || "default"}-${gIdx}`} className="space-y-1">
              {!collapsed && group.section ? (
                <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-muted">
                  {group.section}
                </div>
              ) : null}

              {group.items.map((item) => {
                const isActive = item.id === activeTab;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onTabChange(item.id)}
                    title={collapsed ? item.label : undefined}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "w-full flex items-center rounded-xl transition-colors text-xs font-medium",
                      collapsed
                        ? "justify-center p-2.5 relative"
                        : "justify-between gap-2.5 px-3 py-2.5 text-left",
                      isActive
                        ? "bg-console-600/20 text-console-200 border border-console-500/30 font-semibold shadow-console-sm"
                        : "text-secondary hover:text-primary hover:bg-surface-2 border border-transparent"
                    )}
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <span
                        className={cn(
                          "shrink-0 flex items-center",
                          isActive ? "text-console-300" : "text-muted"
                        )}
                      >
                        {item.icon}
                      </span>
                      {/* Keep accessible text in DOM even when sidebar is collapsed */}
                      <span className={collapsed ? "sr-only" : "truncate"}>
                        {item.label}
                      </span>
                    </span>

                    {!collapsed && item.badge !== undefined && Number(item.badge) > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-bold tabular-nums-lining shrink-0">
                        {item.badge}
                      </span>
                    )}

                    {collapsed && item.badge !== undefined && Number(item.badge) > 0 && (
                      <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-500" />
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
      </div>

      {!collapsed && footer ? (
        <div className="pt-4 mt-4 border-t border-subtle">{footer}</div>
      ) : null}
    </aside>
  );
}

