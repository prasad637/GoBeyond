"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronRight } from "lucide-react";
import {
  MediaCategoryFallback,
  SafeMediaImage,
} from "@/components/ui/SafeMediaImage";
import { MetadataItem, MetadataRow } from "@/components/booking/MetadataRow";
import { ImageGallery } from "@/components/booking/ImageGallery";
import { cn } from "@/lib/cn";

export interface DetailPageHeroProps {
  backHref: string;
  backLabel: string;
  verticalLabel: string;
  title: string;
  subtitle?: React.ReactNode;
  heroImages?: (string | null | undefined)[];
  posterSrc?: string | null;
  fallbackCategory: MediaCategoryFallback;
  badges?: React.ReactNode;
  metadata?: MetadataItem[];
  rightCallout?: React.ReactNode;
  actionsSlot?: React.ReactNode;
  blurBackdrop?: boolean;
  className?: string;
}

export function DetailPageHero({
  backHref,
  backLabel,
  verticalLabel,
  title,
  subtitle,
  heroImages = [],
  posterSrc,
  fallbackCategory,
  badges,
  metadata = [],
  rightCallout,
  actionsSlot,
  blurBackdrop = false,
  className,
}: DetailPageHeroProps) {
  const cleanImages = heroImages.filter(
    (img): img is string => typeof img === "string" && img.trim().length > 0
  );
  const [activeImageIdx, setActiveImageIdx] = useState(0);
  const activeHeroSrc = cleanImages[activeImageIdx] || cleanImages[0] || null;

  return (
    <section
      className={cn(
        "relative w-full overflow-hidden border-b border-subtle bg-surface",
        className
      )}
    >
      {/* Background Media Layer */}
      <div className="absolute inset-0">
        <SafeMediaImage
          src={activeHeroSrc}
          alt={title}
          fallbackCategory={fallbackCategory}
          priority
          sizes="100vw"
          showFallbackWatermark={false}
          className={cn(
            "w-full h-full object-cover",
            blurBackdrop ? "opacity-35 blur-sm scale-105" : "opacity-45"
          )}
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-canvas via-canvas/80 to-canvas/45"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-canvas/95 via-canvas/60 to-transparent"
        />
      </div>

      {/* Foreground Content */}
      <div className="relative z-10 max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 sm:pt-8 sm:pb-10">
        {/* Top Breadcrumb Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6 sm:mb-8">
          <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-1.5 text-xs text-secondary min-w-0"
          >
            <Link
              href="/"
              className="hover:text-primary transition-colors shrink-0"
            >
              Home
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" aria-hidden="true" />
            <Link
              href={backHref}
              className="hover:text-primary transition-colors shrink-0"
            >
              {verticalLabel}
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" aria-hidden="true" />
            <span className="text-primary font-medium truncate max-w-[180px] sm:max-w-xs">
              {title}
            </span>
          </nav>

          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface/85 hover:bg-surface-2 border border-strong text-xs font-semibold text-primary backdrop-blur-md transition-colors shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-brand-400" aria-hidden="true" />
            <span>{backLabel}</span>
          </Link>
        </div>

        {/* Main Hero Row */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="flex flex-col sm:flex-row sm:items-end gap-5 sm:gap-7 min-w-0 flex-1">
            {posterSrc !== undefined ? (
              <div className="relative w-32 sm:w-44 md:w-48 aspect-[2/3] rounded-2xl overflow-hidden bg-surface-2 border border-strong shadow-modal shrink-0">
                <SafeMediaImage
                  src={posterSrc}
                  alt={title}
                  fallbackCategory={fallbackCategory}
                  priority
                  sizes="(max-width: 640px) 128px, 192px"
                />
              </div>
            ) : null}

            <div className="space-y-3 min-w-0 flex-1">
              {badges ? (
                <div className="flex flex-wrap items-center gap-2">{badges}</div>
              ) : null}

              <h1 className="font-display text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-primary leading-[1.12]">
                {title}
              </h1>

              {subtitle ? (
                <div className="text-sm sm:text-base text-secondary leading-relaxed max-w-2xl">
                  {subtitle}
                </div>
              ) : null}

              {metadata.length > 0 ? <MetadataRow items={metadata} className="pt-1" /> : null}

              {actionsSlot ? (
                <div className="flex flex-wrap items-center gap-3 pt-2">{actionsSlot}</div>
              ) : null}

              {cleanImages.length > 1 ? (
                <ImageGallery
                  images={cleanImages}
                  altPrefix={title}
                  activeIndex={activeImageIdx}
                  onSelectIndex={setActiveImageIdx}
                  fallbackCategory={fallbackCategory}
                  className="pt-1"
                />
              ) : null}
            </div>
          </div>

          {rightCallout ? <div className="shrink-0">{rightCallout}</div> : null}
        </div>
      </div>
    </section>
  );
}

