import React from "react";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/cn";

export type KpiAccent =
  | "console"
  | "brand"
  | "success"
  | "warning"
  | "info"
  | "danger"
  | "gold";

export interface DashboardKpiCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  accent?: KpiAccent;
  onClick?: () => void;
  className?: string;
}

const accentStyles: Record<
  KpiAccent,
  { borderTop: string; iconBg: string; valueColor: string }
> = {
  console: {
    borderTop: "before:bg-console-500",
    iconBg: "bg-console-500/12 text-console-300 border-console-500/25",
    valueColor: "text-primary",
  },
  brand: {
    borderTop: "before:bg-brand-500",
    iconBg: "bg-brand-500/12 text-brand-400 border-brand-500/25",
    valueColor: "text-primary",
  },
  success: {
    borderTop: "before:bg-emerald-500",
    iconBg: "bg-emerald-500/12 text-emerald-400 border-emerald-500/25",
    valueColor: "text-emerald-300",
  },
  warning: {
    borderTop: "before:bg-amber-500",
    iconBg: "bg-amber-500/12 text-amber-300 border-amber-500/25",
    valueColor: "text-amber-300",
  },
  info: {
    borderTop: "before:bg-sky-500",
    iconBg: "bg-sky-500/12 text-sky-300 border-sky-500/25",
    valueColor: "text-sky-300",
  },
  danger: {
    borderTop: "before:bg-red-500",
    iconBg: "bg-red-500/12 text-red-400 border-red-500/25",
    valueColor: "text-red-300",
  },
  gold: {
    borderTop: "before:bg-gold-500",
    iconBg: "bg-gold-500/12 text-gold-400 border-gold-500/25",
    valueColor: "text-gold-400",
  },
};

export function DashboardKpiCard({
  label,
  value,
  subtext,
  badge,
  icon,
  accent = "console",
  onClick,
  className,
}: DashboardKpiCardProps) {
  const tone = accentStyles[accent];
  const Comp = onClick ? "button" : "div";

  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "relative overflow-hidden rounded-2xl bg-surface border border-subtle p-4 sm:p-[18px] text-left transition-all duration-200 flex flex-col justify-between",
        "before:content-[''] before:absolute before:inset-x-0 before:top-0 before:h-[2px]",
        tone.borderTop,
        onClick &&
          "hover:border-strong hover:bg-surface-2/80 cursor-pointer group focus:outline-none focus-visible:ring-2 focus-visible:ring-console-500/60",
        className
      )}
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1 flex items-center gap-1.5 flex-wrap pt-0.5">
            <span className="text-[10.5px] sm:text-[11px] font-semibold uppercase tracking-[0.06em] text-muted leading-snug">
              {label}
            </span>
            {badge}
          </div>

          {(icon || onClick) && (
            <div className="flex items-center gap-1 shrink-0">
              {icon ? (
                <div
                  className={cn(
                    "w-8 h-8 rounded-xl border flex items-center justify-center shrink-0",
                    tone.iconBg
                  )}
                >
                  {icon}
                </div>
              ) : null}
              {onClick ? (
                <ArrowUpRight className="w-3.5 h-3.5 text-muted group-hover:text-primary transition-colors" />
              ) : null}
            </div>
          )}
        </div>

        <div
          title={
            typeof value === "string" || typeof value === "number"
              ? String(value)
              : undefined
          }
          className={cn(
            "mt-2 font-display text-xl sm:text-[22px] font-bold tracking-tight tabular-nums-lining leading-tight whitespace-nowrap truncate",
            tone.valueColor
          )}
        >
          {value}
        </div>
      </div>

      {subtext ? (
        <p className="mt-2 text-xs text-secondary leading-snug line-clamp-2">
          {subtext}
        </p>
      ) : null}
    </Comp>
  );
}

