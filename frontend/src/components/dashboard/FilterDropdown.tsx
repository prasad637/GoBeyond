import React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export interface FilterOption {
  label: string;
  value: string;
}

export interface FilterDropdownProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
}

export function FilterDropdown({
  label,
  value,
  onChange,
  options,
  placeholder,
  ariaLabel,
  className,
}: FilterDropdownProps) {
  return (
    <div className={cn("relative inline-flex flex-col gap-1", className)}>
      {label ? (
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
          {label}
        </span>
      ) : null}
      <div className="relative flex items-center">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={ariaLabel || label || placeholder || "Filter"}
          className="appearance-none h-9 pl-3 pr-8 rounded-lg bg-surface-2 border border-subtle hover:border-strong focus:outline-none focus:border-console-500 text-xs font-medium text-primary transition-colors w-full cursor-pointer"
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-2.5 w-3.5 h-3.5 text-muted"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}

