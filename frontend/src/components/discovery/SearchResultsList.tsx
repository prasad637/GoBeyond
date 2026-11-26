"use client";

import React from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, RotateCcw, Search, Star } from "lucide-react";
import { SearchResultItem } from "@/types/discovery";
import { Badge, Button, Skeleton } from "@/components/ui";
import { SafeMediaImage, MediaCategoryFallback } from "@/components/ui/SafeMediaImage";
import { cn } from "@/lib/cn";

export interface SearchResultsListProps {
  query: string;
  results: SearchResultItem[];
  totalCount: number;
  isLoading: boolean;
  error: string | null;
  localityName?: string | null;
  highlightedIndex?: number;
  onSelect?: (item: SearchResultItem) => void;
  onRetry?: () => void;
  onResetFilters?: () => void;
  maxHeightClassName?: string;
  emptyPromptTitle?: string;
}

function getCategoryBadgeVariant(category: string) {
  switch (category?.toUpperCase()) {
    case "MOVIES":
      return "brand" as const;
    case "DINING":
      return "gold" as const;
    case "EVENTS":
      return "console" as const;
    case "SPORTS":
      return "success" as const;
    case "ACTIVITIES":
      return "info" as const;
    default:
      return "default" as const;
  }
}

function mapSearchFallbackCategory(category?: string | null): MediaCategoryFallback {
  switch (category?.toUpperCase()) {
    case "MOVIES":
      return "movies";
    case "DINING":
      return "dining";
    case "EVENTS":
      return "events";
    case "SPORTS":
      return "sports";
    case "ACTIVITIES":
      return "activities";
    default:
      return "default";
  }
}

function ResultThumbnail({
  src,
  title,
  category,
}: {
  src?: string | null;
  title: string;
  category?: string | null;
}) {
  return (
    <div className="relative w-12 h-12 sm:w-14 sm:h-14 rounded-xl bg-surface-2 border border-subtle overflow-hidden shrink-0">
      <SafeMediaImage
        src={src}
        alt={title}
        fallbackCategory={mapSearchFallbackCategory(category)}
        eager
        sizes="56px"
        showFallbackWatermark={false}
        className="group-hover:scale-105 transition-transform duration-200"
      />
    </div>
  );
}

export function SearchResultsList({
  query,
  results,
  totalCount,
  isLoading,
  error,
  localityName,
  highlightedIndex = -1,
  onSelect,
  onRetry,
  onResetFilters,
  maxHeightClassName = "max-h-96",
  emptyPromptTitle,
}: SearchResultsListProps) {
  if (isLoading && results.length === 0) {
    return (
      <div className="p-4 space-y-3" role="status" aria-live="polite">
        <div className="flex items-center justify-between text-xs text-secondary pb-1">
          <span>Searching Hyderabad experiences...</span>
        </div>
        {[0, 1, 2].map((idx) => (
          <div
            key={idx}
            className="flex items-center gap-3 p-2.5 rounded-xl bg-surface-2/60 border border-subtle"
          >
            <Skeleton className="w-12 h-12 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-6 w-16 rounded-lg shrink-0" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center space-y-3" role="alert">
        <div className="w-10 h-10 mx-auto rounded-xl bg-red-500/10 border border-red-500/25 flex items-center justify-center text-red-400">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-primary">Search unavailable right now</p>
          <p className="text-xs text-secondary max-w-sm mx-auto">{error}</p>
        </div>
        {onRetry ? (
          <Button size="sm" variant="secondary" leftIcon={<RotateCcw className="w-3.5 h-3.5" />} onClick={onRetry}>
            Retry Search
          </Button>
        ) : null}
      </div>
    );
  }

  if (results.length > 0) {
    return (
      <div>
        <div className="px-4 py-2.5 bg-surface-2/70 border-b border-subtle flex items-center justify-between text-xs text-secondary font-medium">
          <span className="tabular-nums-lining">
            Found <strong className="text-primary font-semibold">{totalCount}</strong>{" "}
            experience{totalCount === 1 ? "" : "s"}
          </span>
          {localityName ? (
            <span className="text-muted truncate ml-3">in {localityName}</span>
          ) : null}
        </div>

        <div className={cn("overflow-y-auto divide-y divide-subtle", maxHeightClassName)}>
          {results.map((item, idx) => (
            <Link
              key={`${item.category}-${item.id}`}
              href={item.action_url}
              onClick={() => onSelect?.(item)}
              className={cn(
                "flex items-center gap-3.5 p-3 transition-colors group",
                idx === highlightedIndex
                  ? "bg-surface-3/80"
                  : "hover:bg-surface-2/80"
              )}
            >
              <ResultThumbnail src={item.image_url} title={item.title} category={item.category} />

              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
                  <Badge variant={getCategoryBadgeVariant(item.category)} size="sm">
                    {item.category_label || item.category}
                  </Badge>
                  {item.rating != null ? (
                    <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-amber-300 tabular-nums-lining">
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                      <span>{item.rating.toFixed(1)}</span>
                    </span>
                  ) : null}
                  {item.distance_km != null ? (
                    <span className="text-[11px] text-emerald-400 tabular-nums-lining">
                      • {item.distance_km.toFixed(1)} km
                    </span>
                  ) : null}
                </div>

                <h4 className="font-display font-semibold text-sm text-primary group-hover:text-brand-300 transition-colors truncate">
                  {item.title}
                </h4>

                <p className="text-xs text-secondary truncate">{item.location_name}</p>
              </div>

              <div className="text-right shrink-0 space-y-0.5">
                {item.price_label ? (
                  <div className="text-xs font-semibold text-primary tabular-nums-lining">
                    {item.price_label}
                  </div>
                ) : null}
                <span className="text-[11px] font-medium text-brand-400 inline-flex items-center justify-end gap-1 group-hover:translate-x-0.5 transition-transform">
                  <span>{item.action_label}</span>
                  <ArrowRight className="w-3 h-3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-7 text-center space-y-3">
      <div className="w-10 h-10 mx-auto rounded-xl bg-surface-2 border border-subtle flex items-center justify-center text-muted">
        <Search className="w-4 h-4" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-primary">
          {emptyPromptTitle ??
            (query.trim()
              ? `No experiences found matching "${query.trim()}"`
              : "No matching experiences right now")}
        </p>
        <p className="text-xs text-secondary max-w-sm mx-auto">
          Try searching for &ldquo;Pushpa&rdquo;, &ldquo;Biryani&rdquo;, &ldquo;Alan Walker&rdquo;, or broaden your filters.
        </p>
      </div>
      {onResetFilters ? (
        <Button size="xs" variant="outline" onClick={onResetFilters}>
          Reset Filters
        </Button>
      ) : null}
    </div>
  );
}

