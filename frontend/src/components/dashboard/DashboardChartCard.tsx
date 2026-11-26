"use client";

import React, { useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupees } from "@/lib/pricing";

export interface TrendDataPoint {
  label: string;
  fullLabel?: string;
  revenue: number;
  bookings: number;
}

export interface TrendBarChartProps {
  title: string;
  subtitle?: string;
  series: TrendDataPoint[];
  secondarySeries?: TrendDataPoint[];
  primaryPeriodLabel?: string;
  secondaryPeriodLabel?: string;
  defaultMetric?: "revenue" | "bookings";
  emptyMessage?: string;
  className?: string;
}

function compactMetric(value: number, metric: "revenue" | "bookings"): string {
  if (metric === "bookings") {
    return `${value}`;
  }
  if (value === 0) return "₹0";
  if (value >= 100000) return `₹${(value / 100000).toFixed(1)}L`;
  if (value >= 1000) return `₹${(value / 1000).toFixed(1)}k`;
  return formatRupees(value);
}

export function TrendBarChart({
  title,
  subtitle,
  series,
  secondarySeries,
  primaryPeriodLabel = "Daily",
  secondaryPeriodLabel = "Monthly",
  defaultMetric = "revenue",
  emptyMessage = "No activity recorded in this window yet.",
  className,
}: TrendBarChartProps) {
  const [metric, setMetric] = useState<"revenue" | "bookings">(defaultMetric);
  const [granularity, setGranularity] = useState<"primary" | "secondary">("primary");

  const activeData =
    granularity === "secondary" && secondarySeries?.length ? secondarySeries : series;

  const { maxVal, totalVal } = useMemo(() => {
    const values = activeData.map((d) =>
      metric === "revenue" ? Number(d.revenue || 0) : Number(d.bookings || 0)
    );
    const max = Math.max(0, ...values);
    const sum = values.reduce((acc, v) => acc + v, 0);
    return { maxVal: max > 0 ? max : 1, totalVal: sum };
  }, [activeData, metric]);

  const hasNonZeroData = activeData.some((d) =>
    metric === "revenue" ? d.revenue > 0 : d.bookings > 0
  );

  return (
    <section
      className={cn(
        "rounded-2xl bg-surface border border-subtle p-5 sm:p-6 flex flex-col justify-between gap-4",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-console-400 shrink-0" />
            <h3 className="font-display text-sm sm:text-base font-bold text-primary tracking-tight">
              {title}
            </h3>
          </div>
          {subtitle ? (
            <p className="text-xs text-muted mt-0.5">{subtitle}</p>
          ) : null}
          <p className="text-xs text-secondary mt-1.5 tabular-nums-lining">
            Window total:{" "}
            <span className="font-semibold text-primary">
              {metric === "revenue"
                ? formatRupees(totalVal, { decimals: 2 })
                : `${totalVal.toLocaleString("en-IN")} bookings`}
            </span>
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2 shrink-0">
          {secondarySeries && secondarySeries.length > 0 && (
            <div className="inline-flex rounded-lg bg-surface-2 border border-subtle p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setGranularity("primary")}
                className={cn(
                  "px-2.5 py-1 rounded-md font-medium transition-colors",
                  granularity === "primary"
                    ? "bg-console-600 text-white"
                    : "text-secondary hover:text-primary"
                )}
              >
                {primaryPeriodLabel}
              </button>
              <button
                type="button"
                onClick={() => setGranularity("secondary")}
                className={cn(
                  "px-2.5 py-1 rounded-md font-medium transition-colors",
                  granularity === "secondary"
                    ? "bg-console-600 text-white"
                    : "text-secondary hover:text-primary"
                )}
              >
                {secondaryPeriodLabel}
              </button>
            </div>
          )}

          <div className="inline-flex rounded-lg bg-surface-2 border border-subtle p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => setMetric("revenue")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium transition-colors",
                metric === "revenue"
                  ? "bg-brand-500 text-white"
                  : "text-secondary hover:text-primary"
              )}
            >
              Revenue
            </button>
            <button
              type="button"
              onClick={() => setMetric("bookings")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium transition-colors",
                metric === "bookings"
                  ? "bg-brand-500 text-white"
                  : "text-secondary hover:text-primary"
              )}
            >
              Bookings
            </button>
          </div>
        </div>
      </div>

      {activeData.length === 0 ? (
        <div className="h-44 rounded-xl bg-surface-2/40 border border-dashed border-subtle flex items-center justify-center text-xs text-muted px-4 text-center">
          {emptyMessage}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="relative h-48 pt-6 pb-2 px-1 rounded-xl bg-surface-2/35 border border-subtle flex items-end justify-between gap-1.5 sm:gap-2.5">
            {/* Subtle horizontal reference gridlines */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-3 top-6 bottom-2 flex flex-col justify-between"
            >
              <div className="border-t border-dashed border-white/[0.06] w-full" />
              <div className="border-t border-dashed border-white/[0.06] w-full" />
              <div className="border-t border-white/[0.08] w-full" />
            </div>

            {activeData.map((point, idx) => {
              const rawVal =
                metric === "revenue"
                  ? Number(point.revenue || 0)
                  : Number(point.bookings || 0);
              const pct = hasNonZeroData ? Math.round((rawVal / maxVal) * 100) : 0;
              const barHeight = rawVal > 0 ? Math.max(pct, 8) : 3;

              return (
                <div
                  key={`${point.label}-${idx}`}
                  title={`${point.fullLabel || point.label}: ${
                    metric === "revenue"
                      ? formatRupees(point.revenue, { decimals: 2 })
                      : `${point.bookings} bookings`
                  }`}
                  className="relative z-10 flex-1 min-w-0 h-full flex flex-col items-center justify-end group"
                >
                  <span className="mb-1 text-[10px] font-mono text-secondary group-hover:text-primary tabular-nums-lining whitespace-nowrap">
                    {compactMetric(rawVal, metric)}
                  </span>

                  <div className="w-full max-w-[38px] flex-1 flex items-end justify-center">
                    <div
                      style={{ height: `${barHeight}%` }}
                      className={cn(
                        "w-full rounded-t-md transition-all duration-300",
                        rawVal > 0
                          ? metric === "revenue"
                            ? "bg-gradient-to-t from-console-600/80 to-console-400 group-hover:from-brand-600 group-hover:to-brand-400"
                            : "bg-gradient-to-t from-brand-600/80 to-brand-400 group-hover:from-console-600 group-hover:to-console-400"
                          : "bg-surface-3/60"
                      )}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between gap-1.5 sm:gap-2.5 px-1">
            {activeData.map((point, idx) => (
              <div
                key={`lbl-${point.label}-${idx}`}
                className="flex-1 min-w-0 text-center text-[10px] sm:text-[11px] font-medium text-muted truncate"
              >
                {point.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export interface BreakdownItem {
  label: string;
  count: number;
  sublabel?: string;
  tone?: "console" | "brand" | "success" | "warning" | "info" | "danger" | "gold";
}

export interface DistributionBreakdownCardProps {
  title: string;
  subtitle?: string;
  items: BreakdownItem[];
  emptyMessage?: string;
  footer?: React.ReactNode;
  className?: string;
}

const barToneClasses: Record<NonNullable<BreakdownItem["tone"]>, string> = {
  console: "bg-console-500",
  brand: "bg-brand-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
  danger: "bg-red-500",
  gold: "bg-gold-500",
};

export function DistributionBreakdownCard({
  title,
  subtitle,
  items,
  emptyMessage = "No breakdown data available.",
  footer,
  className,
}: DistributionBreakdownCardProps) {
  const total = items.reduce((acc, item) => acc + Number(item.count || 0), 0);

  return (
    <section
      className={cn(
        "rounded-2xl bg-surface border border-subtle p-5 sm:p-6 flex flex-col justify-between gap-4",
        className
      )}
    >
      <div>
        <h3 className="font-display text-sm sm:text-base font-bold text-primary tracking-tight">
          {title}
        </h3>
        {subtitle ? (
          <p className="text-xs text-muted mt-0.5">{subtitle}</p>
        ) : null}
      </div>

      {items.length === 0 || total === 0 ? (
        <div className="py-10 rounded-xl bg-surface-2/35 border border-dashed border-subtle flex items-center justify-center text-xs text-muted text-center px-4">
          {emptyMessage}
        </div>
      ) : (
        <div className="space-y-3.5">
          {items.map((item) => {
            const pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
            const fill = barToneClasses[item.tone || "console"];
            return (
              <div key={item.label} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <div className="min-w-0">
                    <span className="font-semibold text-primary capitalize">
                      {item.label.replace(/_/g, " ").toLowerCase()}
                    </span>
                    {item.sublabel ? (
                      <span className="text-muted ml-1.5">{item.sublabel}</span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 tabular-nums-lining">
                    <span className="font-bold text-primary">
                      {item.count.toLocaleString("en-IN")}
                    </span>
                    <span className="text-[11px] font-mono text-muted w-9 text-right">
                      {pct}%
                    </span>
                  </div>
                </div>
                <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all duration-300", fill)}
                    style={{ width: `${Math.max(pct, item.count > 0 ? 3 : 0)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {footer ? (
        <div className="pt-3 border-t border-subtle text-xs text-secondary">
          {footer}
        </div>
      ) : null}
    </section>
  );
}

