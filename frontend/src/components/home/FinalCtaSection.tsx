"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { useLocation } from "@/context/LocationContext";

export function FinalCtaSection() {
  const { selectedCity, selectedLocality } = useLocation();
  const areaLabel = selectedLocality
    ? `${selectedLocality.name}, ${selectedCity}`
    : selectedCity || "Hyderabad";

  return (
    <section aria-labelledby="final-cta-heading" className="pb-6">
      <div className="relative rounded-2xl bg-surface border border-subtle px-6 py-10 sm:px-10 sm:py-12 overflow-hidden shadow-surface">
        {/* Subtle top hairline accent */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-500/50 to-transparent"
        />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-champagne">
              <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Ready Across {areaLabel}</span>
            </div>

            <h2
              id="final-cta-heading"
              className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-primary"
            >
              Make Every Day an Experience.
            </h2>

            <p className="text-sm text-secondary leading-relaxed">
              Reserve upcoming movie seats, neighbourhood dining tables, stadium concerts, or floodlit courts in minutes.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Link
              href="/movies"
              className="inline-flex items-center justify-center gap-2 h-11 px-6 rounded-lg bg-brand-500 hover:bg-brand-600 text-sm font-semibold text-white shadow-brand-sm transition-colors"
            >
              <span>Start Exploring</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>

            <a
              href="#explore-categories"
              className="inline-flex items-center justify-center h-11 px-5 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle hover:border-strong text-sm font-semibold text-primary transition-colors"
            >
              Browse Categories
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

