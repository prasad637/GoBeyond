"use client";

import React from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pagination, PaginationProps } from "./Pagination";

export interface DataTableColumn<T> {
  key: string;
  header: React.ReactNode;
  align?: "left" | "center" | "right";
  headerClassName?: string;
  cellClassName?: string;
  render: (item: T, index: number) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  keyExtractor: (item: T, index: number) => string | number;
  renderMobileRow?: (item: T, index: number) => React.ReactNode;
  loading?: boolean;
  skeletonRows?: number;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: React.ReactNode;
  onRowClick?: (item: T) => void;
  selectedKey?: string | number | null;
  pagination?: PaginationProps;
  headerBanner?: React.ReactNode;
  className?: string;
}

const alignClass = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  renderMobileRow,
  loading = false,
  skeletonRows = 5,
  emptyTitle = "No records found",
  emptyDescription = "Try adjusting your search query or active filters.",
  emptyIcon,
  onRowClick,
  selectedKey,
  pagination,
  headerBanner,
  className,
}: DataTableProps<T>) {
  return (
    <div
      className={cn(
        "rounded-2xl bg-surface border border-subtle overflow-hidden shadow-surface",
        className
      )}
    >
      {headerBanner}

      {loading && data.length === 0 ? (
        <div className="p-4 sm:p-5 space-y-3">
          {Array.from({ length: skeletonRows }).map((_, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between gap-4 py-2 border-b border-subtle last:border-0"
            >
              <Skeleton className="h-4 w-36 sm:w-52" />
              <Skeleton className="h-4 w-24 hidden sm:block" />
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      ) : data.length === 0 ? (
        <div className="p-4">
          <EmptyState
            variant="compact"
            icon={emptyIcon || <Inbox className="w-6 h-6" />}
            title={emptyTitle}
            description={emptyDescription}
          />
        </div>
      ) : (
        <>
          {/* Desktop / Tablet horizontal-safe data table */}
          <div className={cn("w-full overflow-x-auto", renderMobileRow && "hidden md:block")}>
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-subtle bg-surface-2/70 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      className={cn(
                        "py-3 px-4 whitespace-nowrap",
                        alignClass[col.align || "left"],
                        col.headerClassName
                      )}
                    >
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle text-xs sm:text-sm">
                {data.map((item, idx) => {
                  const key = keyExtractor(item, idx);
                  const isSelected = selectedKey !== undefined && selectedKey === key;
                  return (
                    <tr
                      key={key}
                      onClick={onRowClick ? () => onRowClick(item) : undefined}
                      className={cn(
                        "transition-colors",
                        onRowClick
                          ? "cursor-pointer hover:bg-surface-2/70"
                          : "hover:bg-surface-2/40",
                        isSelected && "bg-console-500/10"
                      )}
                    >
                      {columns.map((col) => (
                        <td
                          key={col.key}
                          className={cn(
                            "py-3.5 px-4 align-middle",
                            alignClass[col.align || "left"],
                            col.cellClassName
                          )}
                        >
                          {col.render(item, idx)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked card layout when renderMobileRow is provided */}
          {renderMobileRow && (
            <div className="md:hidden divide-y divide-subtle">
              {data.map((item, idx) => {
                const key = keyExtractor(item, idx);
                const isSelected = selectedKey !== undefined && selectedKey === key;
                return (
                  <div
                    key={key}
                    onClick={onRowClick ? () => onRowClick(item) : undefined}
                    className={cn(
                      "p-4 transition-colors",
                      onRowClick && "cursor-pointer hover:bg-surface-2/60",
                      isSelected && "bg-console-500/10"
                    )}
                  >
                    {renderMobileRow(item, idx)}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {pagination && <Pagination {...pagination} />}
    </div>
  );
}

