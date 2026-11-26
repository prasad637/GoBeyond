import React from "react";
import { Calendar, X } from "lucide-react";
import { cn } from "@/lib/cn";

export interface DateRangeFilterProps {
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onClear?: () => void;
  className?: string;
}

export function DateRangeFilter({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onClear,
  className,
}: DateRangeFilterProps) {
  const hasValue = Boolean(startDate || endDate);

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <div className="relative flex items-center">
        <Calendar
          className="pointer-events-none absolute left-2.5 w-3.5 h-3.5 text-muted"
          aria-hidden="true"
        />
        <input
          type="date"
          aria-label="Start date"
          value={startDate}
          onChange={(e) => onStartDateChange(e.target.value)}
          className="h-9 pl-8 pr-2.5 rounded-lg bg-surface-2 border border-subtle focus:outline-none focus:border-console-500 text-xs text-primary"
        />
      </div>
      <span className="text-xs text-muted">to</span>
      <input
        type="date"
        aria-label="End date"
        value={endDate}
        onChange={(e) => onEndDateChange(e.target.value)}
        className="h-9 px-2.5 rounded-lg bg-surface-2 border border-subtle focus:outline-none focus:border-console-500 text-xs text-primary"
      />
      {hasValue && onClear && (
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear date range"
          className="h-9 px-2.5 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs text-secondary hover:text-primary inline-flex items-center gap-1 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          <span>Clear</span>
        </button>
      )}
    </div>
  );
}

