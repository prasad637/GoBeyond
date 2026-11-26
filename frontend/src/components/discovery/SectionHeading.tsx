import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface SectionHeadingProps {
  headingId?: string;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  viewAllHref?: string;
  viewAllLabel?: string;
  icon?: React.ReactNode;
  rightSlot?: React.ReactNode;
  className?: string;
}

export function SectionHeading({
  headingId,
  eyebrow,
  title,
  subtitle,
  viewAllHref,
  viewAllLabel = "View All",
  icon,
  rightSlot,
  className,
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        "flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-6",
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        {eyebrow ? (
          <div className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-champagne">
            {icon ? <span className="shrink-0">{icon}</span> : null}
            <span>{eyebrow}</span>
          </div>
        ) : null}

        <h2
          id={headingId}
          className="font-display text-xl sm:text-2xl font-bold tracking-tight text-primary leading-tight"
        >
          {title}
        </h2>

        {subtitle ? (
          <p className="text-xs sm:text-sm text-secondary max-w-2xl leading-relaxed">
            {subtitle}
          </p>
        ) : null}
      </div>

      {(rightSlot || viewAllHref) && (
        <div className="flex items-center gap-3 shrink-0 self-start sm:self-end">
          {rightSlot}
          {viewAllHref ? (
            <Link
              href={viewAllHref}
              className="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-2 border border-subtle hover:border-strong text-xs font-semibold text-primary hover:text-brand-400 transition-colors"
            >
              <span>{viewAllLabel}</span>
              <ArrowRight
                className="w-3.5 h-3.5 text-brand-400 group-hover:translate-x-0.5 transition-transform"
                aria-hidden="true"
              />
            </Link>
          ) : null}
        </div>
      )}
    </div>
  );
}

