import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (nextPage: number) => void;
  className?: string;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  className,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const startIdx = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const endIdx = Math.min(total, safePage * pageSize);

  return (
    <div
      className={cn(
        "flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-t border-subtle bg-surface-2/30 text-xs text-secondary",
        className
      )}
    >
      <div className="tabular-nums-lining">
        {total === 0 ? (
          <span>Showing 0 results</span>
        ) : (
          <span>
            Showing <strong className="text-primary">{startIdx}</strong>–
            <strong className="text-primary">{endIdx}</strong> of{" "}
            <strong className="text-primary">{total.toLocaleString("en-IN")}</strong>
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 self-end sm:self-auto">
        <button
          type="button"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          aria-label="Previous page"
          className="h-8 px-2.5 rounded-lg bg-surface-2 border border-subtle hover:border-strong text-primary disabled:opacity-40 disabled:pointer-events-none inline-flex items-center gap-1 transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Prev</span>
        </button>
        <span className="px-2 font-mono text-[11px] text-secondary tabular-nums-lining">
          {safePage} / {totalPages}
        </span>
        <button
          type="button"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
          aria-label="Next page"
          className="h-8 px-2.5 rounded-lg bg-surface-2 border border-subtle hover:border-strong text-primary disabled:opacity-40 disabled:pointer-events-none inline-flex items-center gap-1 transition-colors"
        >
          <span>Next</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

