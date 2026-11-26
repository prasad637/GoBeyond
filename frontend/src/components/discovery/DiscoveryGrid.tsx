"use client";

import React from "react";
import { AlertCircle, RotateCcw, SearchX } from "lucide-react";
import { cn } from "@/lib/cn";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { useLocation } from "@/context/LocationContext";

export interface DiscoveryGridProps {
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  isEmpty: boolean;
  categoryLabel: string;
  hasActiveFilters?: boolean;
  onClearFilters?: () => void;
  cityWideScope?: boolean;
  skeletonAspect?: "2/3" | "16/10";
  skeletonCount?: number;
  columnsClassName?: string;
  children: React.ReactNode;
}

export function DiscoveryGrid({
  loading,
  error,
  onRetry,
  isEmpty,
  categoryLabel,
  hasActiveFilters = false,
  onClearFilters,
  cityWideScope = false,
  skeletonAspect = "16/10",
  skeletonCount = 6,
  columnsClassName = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6",
  children,
}: DiscoveryGridProps) {
  const { selectedCity, selectedLocality, selectLocality } = useLocation();
  const hasLocalityRestriction = !cityWideScope && Boolean(selectedLocality);

  if (loading) {
    return (
      <div aria-busy="true" aria-label={`Loading ${categoryLabel}`} className={columnsClassName}>
        {Array.from({ length: skeletonCount }).map((_, idx) => (
          <SkeletonCard key={idx} aspect={skeletonAspect} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        variant="error"
        icon={<AlertCircle className="w-6 h-6" />}
        title={`Unable to load ${categoryLabel}`}
        description={error}
        action={
          onRetry ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              onClick={onRetry}
            >
              Try Again
            </Button>
          ) : undefined
        }
        secondaryAction={
          hasLocalityRestriction ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => selectLocality(null)}
            >
              Show City-Wide
            </Button>
          ) : undefined
        }
      />
    );
  }

  if (isEmpty) {
    const scopeLabel =
      hasLocalityRestriction && selectedLocality
        ? `${selectedLocality.name}, ${selectedCity}`
        : selectedCity;

    return (
      <EmptyState
        icon={<SearchX className="w-6 h-6 text-champagne" />}
        title={`No ${categoryLabel} found`}
        description={
          hasActiveFilters
            ? `No listings match your current search or filter selection in ${scopeLabel}.`
            : `There are currently no active ${categoryLabel} listed in ${scopeLabel}.`
        }
        action={
          hasActiveFilters && onClearFilters ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              onClick={onClearFilters}
            >
              Clear Filters
            </Button>
          ) : undefined
        }
        secondaryAction={
          hasLocalityRestriction ? (
            <Button
              variant={hasActiveFilters ? "secondary" : "primary"}
              size="sm"
              onClick={() => selectLocality(null)}
            >
              View All Areas
            </Button>
          ) : undefined
        }
      />
    );
  }

  return <div className={cn(columnsClassName)}>{children}</div>;
}

