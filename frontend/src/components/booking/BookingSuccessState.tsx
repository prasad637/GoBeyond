"use client";

import React from "react";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface SuccessSummaryRow {
  label: string;
  value: React.ReactNode;
  accent?: "brand" | "success" | "default";
}

export interface BookingSuccessStateProps {
  headingTag?: "h3" | "h4";
  title: string;
  subtitle: string;
  rows: SuccessSummaryRow[];
  primaryCtaLabel: string;
  onPrimaryClick: () => void;
  onSecondaryClick: () => void;
  secondaryCtaLabel?: string;
}

export function BookingSuccessState({
  headingTag = "h4",
  title,
  subtitle,
  rows,
  primaryCtaLabel,
  onPrimaryClick,
  onSecondaryClick,
  secondaryCtaLabel = "My Bookings",
}: BookingSuccessStateProps) {
  const Heading = headingTag;

  return (
    <div className="py-5 text-center space-y-4">
      <div className="w-14 h-14 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
        <CheckCircle2 className="w-8 h-8" aria-hidden="true" />
      </div>

      <div className="space-y-1">
        <Heading className="font-display text-xl sm:text-2xl font-extrabold text-primary tracking-tight">
          {title}
        </Heading>
        <p className="text-xs sm:text-sm text-secondary max-w-sm mx-auto leading-relaxed">
          {subtitle}
        </p>
      </div>

      <div className="p-3.5 bg-canvas/90 border border-subtle rounded-xl text-xs space-y-2 text-left max-w-sm mx-auto">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <span className="text-secondary">{row.label}</span>
            <span
              className={
                row.accent === "brand"
                  ? "font-mono font-bold text-brand-400 text-right"
                  : row.accent === "success"
                  ? "font-mono font-bold text-emerald-400 text-right"
                  : "font-semibold text-primary text-right"
              }
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row justify-center gap-2.5 pt-2 max-w-sm mx-auto">
        <Button
          variant="primary"
          size="md"
          fullWidth
          rightIcon={<ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />}
          onClick={onPrimaryClick}
        >
          {primaryCtaLabel}
        </Button>

        <Button
          variant="secondary"
          size="md"
          fullWidth
          onClick={onSecondaryClick}
        >
          {secondaryCtaLabel}
        </Button>
      </div>
    </div>
  );
}

