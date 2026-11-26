import React from "react";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import {
  HorizontalDiscoveryRail,
  RailItemWrapper,
} from "@/components/discovery/HorizontalDiscoveryRail";

export interface DiscoverySectionSkeletonProps {
  aspect?: "2/3" | "16/10";
  count?: number;
  ariaLabel?: string;
}

export function DiscoverySectionSkeleton({
  aspect = "16/10",
  count = 4,
  ariaLabel = "Loading experiences",
}: DiscoverySectionSkeletonProps) {
  const density = aspect === "2/3" ? "poster" : "landscape";

  return (
    <section aria-label={ariaLabel} aria-busy="true">
      <div className="flex items-end justify-between mb-6 gap-4">
        <div className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-7 w-52 sm:w-64" />
          <Skeleton className="h-3.5 w-72 max-w-full" />
        </div>
        <Skeleton className="h-8 w-24 rounded-lg shrink-0" />
      </div>

      <HorizontalDiscoveryRail ariaLabel={ariaLabel} itemDensity={density}>
        {Array.from({ length: count }).map((_, idx) => (
          <RailItemWrapper key={idx} variant={density}>
            <SkeletonCard aspect={aspect} className="h-full" />
          </RailItemWrapper>
        ))}
      </HorizontalDiscoveryRail>
    </section>
  );
}

