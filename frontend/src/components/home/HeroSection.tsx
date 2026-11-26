"use client";

import React from "react";
import { ArrowRight, ChevronRight, MapPin, Sparkles } from "lucide-react";
import { useLocation } from "@/context/LocationContext";
import { SearchBar } from "@/components/discovery/SearchBar";
import { SafeMediaImage } from "@/components/ui/SafeMediaImage";

export function HeroSection() {
  const {
    selectedCity,
    selectedLocality,
    gpsStatus,
    openLocationModal,
  } = useLocation();

  const locationDisplay = selectedLocality
    ? `${selectedLocality.name}, ${selectedCity}`
    : `All ${selectedCity}`;

  const areaNoun = selectedLocality ? selectedLocality.name : selectedCity || "Hyderabad";

  return (
    <section
      aria-labelledby="hero-heading"
      className="relative z-30 border-b border-subtle bg-canvas"
    >
      {/* Dedicated overflow-hidden backdrop layer so foreground SearchBar dropdown never clips */}
      <div aria-hidden="true" className="absolute inset-0 overflow-hidden pointer-events-none">
        <SafeMediaImage
          src="/images/hero-hyderabad.jpg"
          alt="Moody twilight atmosphere across Hyderabad"
          fallbackCategory="default"
          priority
          sizes="100vw"
          showFallbackWatermark={false}
          className="object-[72%_center] md:object-center opacity-75"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/85 sm:via-canvas/80 to-canvas/45 md:to-canvas/25" />
        <div className="absolute inset-0 bg-gradient-to-b from-canvas/55 via-transparent to-canvas" />
      </div>

      {/* Hero Foreground Container */}
      <div className="relative z-20 max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-10 sm:pt-12 sm:pb-14 lg:pt-14 lg:pb-16">
        <div className="max-w-2xl lg:max-w-3xl space-y-5">
          {/* Brand Eyebrow + Live Location Trigger */}
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface/85 backdrop-blur-md border border-subtle font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-champagne">
              <Sparkles className="w-3 h-3" aria-hidden="true" />
              <span>GO BEYOND</span>
            </span>

            <button
              type="button"
              onClick={openLocationModal}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface/85 hover:bg-surface-2 backdrop-blur-md border border-subtle hover:border-strong text-xs font-medium text-primary transition-colors max-w-full"
            >
              <MapPin className="w-3.5 h-3.5 text-brand-500 shrink-0" aria-hidden="true" />
              <span className="truncate max-w-[190px] sm:max-w-[260px]">
                {locationDisplay}
              </span>
              {gpsStatus === "granted" && (
                <span
                  className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"
                  title="GPS active"
                  aria-label="GPS active"
                />
              )}
              <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" aria-hidden="true" />
            </button>
          </div>

          {/* Primary Display Headline */}
          <div className="space-y-3">
            <h1
              id="hero-heading"
              className="font-display text-3xl sm:text-5xl lg:text-[3.5rem] font-extrabold tracking-tight text-primary leading-[1.06]"
            >
              Your City.{" "}
              <span className="text-champagne">Your Experiences.</span>
            </h1>

            <p className="text-sm sm:text-base lg:text-lg text-secondary max-w-2xl leading-relaxed">
              Discover the best things to do around you. From premier cinema shows and sought-after dining tables to live concerts, floodlit arenas, and weekend activities across {areaNoun}.
            </p>
          </div>

          {/* Primary & Secondary CTAs */}
          <div className="flex flex-wrap items-center gap-3 pt-0.5">
            <a
              href="#explore-categories"
              className="inline-flex items-center justify-center gap-2 h-11 px-5 sm:px-6 rounded-lg bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-sm font-semibold text-white shadow-brand-sm transition-colors"
            >
              <span>Explore Experiences</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </a>

            <a
              href="#trending-movies"
              className="inline-flex items-center justify-center gap-2 h-11 px-4 sm:px-5 rounded-lg bg-surface/85 hover:bg-surface-2 backdrop-blur-md border border-strong text-sm font-semibold text-primary transition-colors"
            >
              <span>Discover What&rsquo;s Trending</span>
            </a>
          </div>

          {/* Responsive Global Search Integration */}
          <div className="pt-2 max-w-2xl">
            <SearchBar className="mx-0 max-w-none" />
          </div>
        </div>
      </div>
    </section>
  );
}

