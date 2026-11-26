"use client";

import React from "react";
import Link from "next/link";
import { ChevronRight, MapPin, RotateCcw } from "lucide-react";
import { useLocation } from "@/context/LocationContext";

export interface ListingPageHeaderProps {
  eyebrow: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  breadcrumbLabel: string;
  resultCount?: number;
  resultLabel?: string;
  loading?: boolean;
  cityWideScope?: boolean;
  rightSlot?: React.ReactNode;
}

export function ListingPageHeader({
  eyebrow,
  icon,
  title,
  subtitle,
  breadcrumbLabel,
  resultCount,
  resultLabel = "experiences",
  loading = false,
  cityWideScope = false,
  rightSlot,
}: ListingPageHeaderProps) {
  const { selectedCity, selectedLocality, openLocationModal, selectLocality } =
    useLocation();

  return (
    <section className="relative border-b border-subtle bg-gradient-to-b from-surface/80 via-canvas to-canvas">
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-7 sm:pt-8 sm:pb-9">
        {/* Breadcrumb + Active Location Context */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-1.5 text-xs text-muted"
          >
            <Link
              href="/"
              className="hover:text-primary transition-colors font-medium"
            >
              Home
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-muted/60" aria-hidden="true" />
            <span className="text-secondary font-medium">{breadcrumbLabel}</span>
          </nav>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={openLocationModal}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-2 hover:bg-surface-3 border border-subtle hover:border-strong text-xs text-secondary hover:text-primary transition-colors"
            >
              <MapPin className="w-3.5 h-3.5 text-brand-500 shrink-0" aria-hidden="true" />
              <span>
                {cityWideScope
                  ? `${selectedCity} • City-Wide`
                  : selectedLocality
                  ? `${selectedLocality.name}, ${selectedCity}`
                  : `${selectedCity} • All Areas`}
              </span>
            </button>

            {!cityWideScope && selectedLocality ? (
              <button
                type="button"
                onClick={() => selectLocality(null)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-brand-500/10 hover:bg-brand-500/20 border border-brand-500/25 text-[11px] font-semibold text-brand-400 transition-colors"
              >
                <RotateCcw className="w-3 h-3" aria-hidden="true" />
                <span>View All Areas</span>
              </button>
            ) : null}
          </div>
        </div>

        {/* Title & Summary Row */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2 max-w-3xl min-w-0">
            <div className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-champagne">
              <span className="shrink-0">{icon}</span>
              <span>{eyebrow}</span>
            </div>

            <h1 className="font-display text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-primary leading-tight">
              {title}
            </h1>

            <p className="text-xs sm:text-sm text-secondary leading-relaxed">
              {subtitle}
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {rightSlot}
            {!loading && typeof resultCount === "number" ? (
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-surface border border-subtle text-xs text-secondary">
                <span className="font-mono font-bold text-primary tabular-nums-lining">
                  {resultCount}
                </span>
                <span>{resultCount === 1 ? resultLabel.replace(/s$/, "") : resultLabel}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

