"use client";

import React from "react";
import { cn } from "@/lib/cn";

export interface AvailabilityOption {
  value: string;
  label: string;
  sublabel?: string;
  disabled?: boolean;
}

export interface AvailabilitySelectorProps {
  label: string;
  options: AvailabilityOption[];
  selectedValue: string | null;
  onSelect: (value: string) => void;
  columnsClassName?: string;
  className?: string;
}

export function AvailabilitySelector({
  label,
  options,
  selectedValue,
  onSelect,
  columnsClassName = "flex flex-wrap gap-2",
  className,
}: AvailabilitySelectorProps) {
  if (options.length === 0) return null;

  return (
    <div className={cn("space-y-2", className)}>
      <span className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary">
        {label}
      </span>

      <div role="group" aria-label={label} className={columnsClassName}>
        {options.map((opt) => {
          const isSelected = selectedValue === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={opt.disabled}
              aria-pressed={isSelected}
              onClick={() => onSelect(opt.value)}
              className={cn(
                "px-3 py-2 rounded-xl border text-xs font-semibold transition-all text-center",
                opt.disabled
                  ? "bg-canvas/50 border-subtle text-muted opacity-45 cursor-not-allowed"
                  : isSelected
                  ? "bg-brand-500 border-brand-500 text-white shadow-brand-sm"
                  : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:border-strong"
              )}
            >
              <span className="block">{opt.label}</span>
              {opt.sublabel ? (
                <span
                  className={cn(
                    "block text-[10px] font-normal mt-0.5",
                    isSelected ? "text-white/85" : "text-muted"
                  )}
                >
                  {opt.sublabel}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

