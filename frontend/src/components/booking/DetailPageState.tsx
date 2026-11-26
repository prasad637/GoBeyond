"use client";

import React from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Compass, RotateCcw } from "lucide-react";
import { Skeleton, SkeletonText } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export interface DetailPageStateProps {
  mode: "loading" | "not-found" | "error";
  backHref: string;
  backLabel: string;
  entityLabel?: string;
  errorMessage?: string | null;
  onRetry?: () => void;
}

export function DetailPageState({
  mode,
  backHref,
  backLabel,
  entityLabel = "experience",
  errorMessage,
  onRetry,
}: DetailPageStateProps) {
  if (mode === "loading") {
    return (
      <div
        aria-busy="true"
        aria-label={`Loading ${entityLabel}`}
        className="min-h-screen bg-canvas"
      >
        {/* Hero skeleton */}
        <div className="border-b border-subtle bg-surface/60">
          <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
            <Skeleton className="h-5 w-44" />
            <div className="space-y-3 max-w-2xl">
              <Skeleton className="h-6 w-28" />
              <Skeleton className="h-10 w-3/4" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </div>
        </div>

        {/* Main 2-col skeleton */}
        <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="p-6 rounded-2xl bg-surface border border-subtle space-y-4">
              <Skeleton className="h-6 w-48" />
              <SkeletonText lines={4} />
            </div>
            <div className="p-6 rounded-2xl bg-surface border border-subtle space-y-4">
              <Skeleton className="h-6 w-56" />
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-20 w-full rounded-xl" />
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-surface border border-subtle space-y-4 h-72">
            <Skeleton className="h-6 w-40" />
            <SkeletonText lines={3} />
            <Skeleton className="h-11 w-full rounded-xl mt-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[70vh] bg-canvas flex items-center justify-center px-4 py-16">
      <div className="max-w-lg w-full">
        <EmptyState
          variant={mode === "error" ? "error" : "default"}
          icon={
            mode === "error" ? (
              <AlertCircle className="w-6 h-6" />
            ) : (
              <Compass className="w-6 h-6 text-champagne" />
            )
          }
          title={
            mode === "error"
              ? `Could not load this ${entityLabel}`
              : `${entityLabel.charAt(0).toUpperCase() + entityLabel.slice(1)} not found`
          }
          description={
            mode === "error"
              ? errorMessage ||
                "There was a network or server problem fetching these details. Please try again."
              : `This ${entityLabel} may have ended, been removed, or the link may be incorrect.`
          }
          action={
            mode === "error" && onRetry ? (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                onClick={onRetry}
              >
                Try Again
              </Button>
            ) : (
              <Link
                href={backHref}
                className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
                <span>{backLabel}</span>
              </Link>
            )
          }
          secondaryAction={
            mode === "error" ? (
              <Link
                href={backHref}
                className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs font-semibold text-primary transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
                <span>{backLabel}</span>
              </Link>
            ) : (
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs font-semibold text-primary transition-colors"
              >
                Explore Home
              </Link>
            )
          }
        />
      </div>
    </div>
  );
}

