import React from "react";
import { cn } from "@/lib/cn";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  shimmer?: boolean;
}

export function Skeleton({
  className,
  shimmer = true,
  ...props
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-lg bg-surface-2",
        shimmer ? "skeleton-shimmer" : "animate-pulse",
        className
      )}
      {...props}
    />
  );
}

export interface SkeletonTextProps {
  lines?: number;
  className?: string;
}

export function SkeletonText({ lines = 3, className }: SkeletonTextProps) {
  return (
    <div className={cn("space-y-2.5", className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, idx) => (
        <Skeleton
          key={idx}
          className={cn("h-3.5", idx === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

export interface SkeletonCardProps {
  aspect?: "2/3" | "16/10";
  className?: string;
}

export function SkeletonCard({ aspect = "16/10", className }: SkeletonCardProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-xl bg-surface border border-subtle overflow-hidden flex flex-col",
        className
      )}
    >
      <Skeleton
        className={cn(
          "w-full rounded-none",
          aspect === "2/3" ? "aspect-[2/3]" : "aspect-[16/10]"
        )}
      />
      <div className="p-4 space-y-2.5">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <div className="pt-2 flex items-center justify-between gap-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-20 rounded-lg" />
        </div>
      </div>
    </div>
  );
}

export interface SkeletonKpiGridProps {
  count?: number;
  className?: string;
}

export function SkeletonKpiGrid({ count = 4, className }: SkeletonKpiGridProps) {
  return (
    <div
      aria-hidden="true"
      className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4", className)}
    >
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="rounded-xl bg-surface border border-subtle p-5 space-y-3"
        >
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

export interface SkeletonTableRowsProps {
  rows?: number;
  columns?: number;
}

export function SkeletonTableRows({ rows = 5, columns = 5 }: SkeletonTableRowsProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <tr key={rowIdx} aria-hidden="true" className="border-b border-subtle">
          {Array.from({ length: columns }).map((__, colIdx) => (
            <td key={colIdx} className="px-4 py-3.5">
              <Skeleton
                className={cn("h-3.5", colIdx === 0 ? "w-32" : "w-20")}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

