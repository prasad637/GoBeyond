"use client";

import React from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, RotateCcw, Sparkles } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export interface DiscoveryEmptyStateProps {
  mode?: "empty" | "error";
  categoryName?: string;
  locationLabel?: string;
  cityName?: string;
  exploreHref?: string;
  exploreLabel?: string;
  hasLocalityFilter?: boolean;
  onResetLocality?: () => void;
  errorMessage?: string | null;
  onRetry?: () => void;
}

export function DiscoveryEmptyState({
  mode = "empty",
  categoryName = "Experiences",
  locationLabel = "Hyderabad",
  cityName = "Hyderabad",
  exploreHref = "/movies",
  exploreLabel = "Browse All",
  hasLocalityFilter = false,
  onResetLocality,
  errorMessage,
  onRetry,
}: DiscoveryEmptyStateProps) {
  if (mode === "error") {
    return (
      <EmptyState
        variant="error"
        icon={<AlertCircle className="w-6 h-6" />}
        title="Unable to load live experiences right now"
        description={
          errorMessage ||
          "We could not reach the discovery feed. Check your connection and try again."
        }
        action={
          onRetry ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              onClick={onRetry}
            >
              Retry
            </Button>
          ) : undefined
        }
        secondaryAction={
          hasLocalityFilter && onResetLocality ? (
            <Button variant="secondary" size="sm" onClick={onResetLocality}>
              Show All {cityName}
            </Button>
          ) : undefined
        }
      />
    );
  }

  return (
    <EmptyState
      variant="compact"
      icon={<Sparkles className="w-5 h-5 text-champagne" />}
      title={`No ${categoryName.toLowerCase()} currently available in ${locationLabel}`}
      description={
        hasLocalityFilter
          ? `There are no active ${categoryName.toLowerCase()} in ${locationLabel} right now. Switch back to all localities across ${cityName} or browse the full catalogue.`
          : `Check back shortly for new ${categoryName.toLowerCase()} across ${cityName}.`
      }
      action={
        hasLocalityFilter && onResetLocality ? (
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={onResetLocality}
          >
            View All {cityName}
          </Button>
        ) : undefined
      }
      secondaryAction={
        <Link
          href={exploreHref}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm transition-colors"
        >
          <span>{exploreLabel}</span>
          <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
        </Link>
      }
    />
  );
}

