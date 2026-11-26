import React from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/cn";

export interface TableToolbarProps {
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  filters?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function TableToolbar({
  searchValue = "",
  onSearchChange,
  searchPlaceholder = "Search records...",
  filters,
  actions,
  className,
}: TableToolbarProps) {
  return (
    <div
      className={cn(
        "rounded-2xl bg-surface border border-subtle p-3.5 sm:p-4 flex flex-col xl:flex-row xl:items-center justify-between gap-3",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center flex-wrap gap-2.5 flex-1 min-w-0">
        {onSearchChange && (
          <div className="relative flex items-center w-full sm:w-72 md:w-80">
            <Search
              className="pointer-events-none absolute left-3 w-3.5 h-3.5 text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full h-9 pl-9 pr-8 rounded-lg bg-surface-2 border border-subtle focus:outline-none focus:border-console-500 text-xs text-primary placeholder:text-muted transition-colors"
            />
            {searchValue && (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                aria-label="Clear search"
                className="absolute right-2 p-1 rounded text-muted hover:text-primary"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}

        {filters ? (
          <div className="flex items-center flex-wrap gap-2">{filters}</div>
        ) : null}
      </div>

      {actions ? (
        <div className="flex items-center flex-wrap gap-2 shrink-0">{actions}</div>
      ) : null}
    </div>
  );
}

