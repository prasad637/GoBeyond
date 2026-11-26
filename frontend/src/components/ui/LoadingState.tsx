import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export type LoadingStateVariant = "page" | "section" | "inline";
export type LoadingStateSize = "sm" | "md" | "lg";

export interface LoadingStateProps {
  label?: string;
  variant?: LoadingStateVariant;
  size?: LoadingStateSize;
  className?: string;
}

const variantClasses: Record<LoadingStateVariant, string> = {
  page: "min-h-[55vh] flex flex-col items-center justify-center gap-3 px-4 py-16 text-center",
  section:
    "rounded-xl bg-surface border border-subtle flex flex-col items-center justify-center gap-3 px-6 py-12 text-center",
  inline: "inline-flex items-center gap-2 text-sm text-secondary",
};

const spinnerSizes: Record<LoadingStateSize, string> = {
  sm: "w-4 h-4",
  md: "w-6 h-6",
  lg: "w-8 h-8",
};

export function LoadingState({
  label = "Loading...",
  variant = "section",
  size = variant === "inline" ? "sm" : "md",
  className,
}: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(variantClasses[variant], className)}
    >
      <Loader2
        className={cn("animate-spin text-brand-500 shrink-0", spinnerSizes[size])}
        aria-hidden="true"
      />
      {label ? (
        <span
          className={cn(
            "text-secondary font-medium",
            variant === "inline" ? "text-sm" : "text-sm"
          )}
        >
          {label}
        </span>
      ) : (
        <span className="sr-only">Loading</span>
      )}
    </div>
  );
}

