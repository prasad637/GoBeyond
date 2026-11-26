import React from "react";
import { Skeleton, SkeletonKpiGrid } from "@/components/ui/Skeleton";

export function LoadingSkeleton({ showSidebar = false }: { showSidebar?: boolean }) {
  return (
    <div className="min-h-[70vh] p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1440px] mx-auto w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-subtle">
        <div className="space-y-2">
          <Skeleton className="h-3 w-36" />
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-3 w-80 max-w-full" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-24 rounded-lg" />
          <Skeleton className="h-9 w-32 rounded-lg" />
        </div>
      </div>

      <SkeletonKpiGrid count={4} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-surface border border-subtle p-6 space-y-4">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-44 w-full rounded-xl" />
        </div>
        <div className="rounded-2xl bg-surface border border-subtle p-6 space-y-4">
          <Skeleton className="h-5 w-48" />
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
      </div>

      {showSidebar && <Skeleton className="h-32 w-full rounded-2xl" />}
    </div>
  );
}

