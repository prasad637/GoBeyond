import React from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/cn";

export type EmptyStateVariant = "default" | "compact" | "error";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  variant?: EmptyStateVariant;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  variant = "default",
  className,
}: EmptyStateProps) {
  const isCompact = variant === "compact";
  const isError = variant === "error";

  return (
    <div
      className={cn(
        "rounded-2xl bg-surface border text-center flex flex-col items-center justify-center",
        isError ? "border-red-500/25 bg-red-500/5" : "border-subtle",
        isCompact ? "px-5 py-8" : "px-6 py-12 sm:py-16",
        className
      )}
    >
      <div
        className={cn(
          "rounded-xl border flex items-center justify-center mb-4",
          isCompact ? "w-10 h-10" : "w-12 h-12",
          isError
            ? "bg-red-500/10 border-red-500/25 text-red-400"
            : "bg-surface-2 border-subtle text-secondary"
        )}
        aria-hidden="true"
      >
        {icon ?? <Inbox className={isCompact ? "w-5 h-5" : "w-6 h-6"} />}
      </div>

      <h3
        className={cn(
          "font-display font-bold tracking-tight text-primary",
          isCompact ? "text-base" : "text-lg sm:text-xl"
        )}
      >
        {title}
      </h3>

      {description ? (
        <p
          className={cn(
            "mt-1.5 text-secondary max-w-md leading-relaxed",
            isCompact ? "text-xs" : "text-sm"
          )}
        >
          {description}
        </p>
      ) : null}

      {(action || secondaryAction) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}

