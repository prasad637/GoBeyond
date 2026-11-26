"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, MapPin, Navigation, Star } from "lucide-react";
import {
  MediaCategoryFallback,
  SafeMediaImage,
} from "@/components/ui/SafeMediaImage";
import { cn } from "@/lib/cn";

export interface MediaCardProps {
  href: string;
  title: string;
  imageSrc?: string | null;
  fallbackCategory?: MediaCategoryFallback;
  aspectRatio?: "2/3" | "16/10";
  eyebrow?: React.ReactNode;
  subtitle?: string | null;
  locationLabel?: string | null;
  rating?: number | null;
  ratingSubLabel?: string | null;
  distanceKm?: number | null;
  topLeftBadge?: React.ReactNode;
  bottomLeftBadge?: React.ReactNode;
  priceLabel?: string | null;
  ctaLabel?: string;
  tags?: string[];
  className?: string;
}

export function MediaCard({
  href,
  title,
  imageSrc,
  fallbackCategory = "default",
  aspectRatio = "16/10",
  eyebrow,
  subtitle,
  locationLabel,
  rating,
  ratingSubLabel,
  distanceKm,
  topLeftBadge,
  bottomLeftBadge,
  priceLabel,
  ctaLabel = "View Details",
  tags,
  className,
}: MediaCardProps) {
  const showRating = typeof rating === "number" && !Number.isNaN(rating) && rating > 0;
  const showDistance =
    typeof distanceKm === "number" && !Number.isNaN(distanceKm) && distanceKm >= 0;

  return (
    <Link
      href={href}
      className={cn(
        "group flex flex-col h-full bg-surface border border-subtle rounded-xl overflow-hidden shadow-surface",
        "hover:border-strong hover:bg-surface-2/75 hover:-translate-y-0.5 transition-all duration-200",
        className
      )}
    >
      {/* Fixed-Aspect Media Frame */}
      <div
        className={cn(
          "relative w-full overflow-hidden bg-surface-2 shrink-0",
          aspectRatio === "2/3" ? "aspect-[2/3]" : "aspect-[16/10]"
        )}
      >
        <SafeMediaImage
          src={imageSrc}
          alt={title}
          fallbackCategory={fallbackCategory}
          eager
          sizes={
            aspectRatio === "2/3"
              ? "(max-width: 640px) 62vw, (max-width: 1024px) 32vw, 240px"
              : "(max-width: 640px) 84vw, (max-width: 1024px) 46vw, 390px"
          }
          className="group-hover:scale-105"
        />

        {/* Editorial Vignette Overlay */}
        <div
          aria-hidden="true"
          className={cn(
            "absolute inset-0 pointer-events-none",
            aspectRatio === "2/3"
              ? "bg-gradient-to-t from-canvas via-canvas/20 to-black/25"
              : "bg-gradient-to-t from-canvas/90 via-transparent to-black/25"
          )}
        />

        {/* Top Row Badges */}
        {(topLeftBadge || showRating) && (
          <div className="absolute top-3 inset-x-3 z-10 flex items-center justify-between gap-2 pointer-events-none">
            <div className="min-w-0">{topLeftBadge}</div>

            {showRating ? (
              <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-xs font-semibold text-champagne tabular-nums-lining shrink-0">
                <Star
                  className="w-3 h-3 fill-champagne text-champagne"
                  aria-hidden="true"
                />
                <span>{rating.toFixed(1)}</span>
                {ratingSubLabel ? (
                  <span className="text-[10px] text-secondary font-normal">
                    {ratingSubLabel}
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
        )}

        {/* Bottom Left Media Overlay Badge */}
        {(bottomLeftBadge || showDistance) && (
          <div className="absolute bottom-3 left-3 right-3 z-10 flex items-center gap-2 pointer-events-none">
            {bottomLeftBadge}
            {showDistance ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-[11px] font-medium text-emerald-400 tabular-nums-lining">
                <Navigation className="w-3 h-3" aria-hidden="true" />
                <span>{distanceKm.toFixed(1)} km</span>
              </span>
            ) : null}
          </div>
        )}
      </div>

      {/* Card Body */}
      <div className="p-4 flex-1 flex flex-col justify-between gap-3">
        <div className="space-y-1.5 min-w-0">
          {eyebrow ? (
            <div className="font-mono text-[11px] font-medium uppercase tracking-wider text-champagne truncate">
              {eyebrow}
            </div>
          ) : null}

          <h3 className="font-display text-base font-bold tracking-tight text-primary group-hover:text-brand-400 transition-colors line-clamp-1">
            {title}
          </h3>

          {subtitle ? (
            <p className="text-xs text-secondary line-clamp-1 leading-relaxed">
              {subtitle}
            </p>
          ) : null}

          {locationLabel ? (
            <div className="flex items-center gap-1.5 text-xs text-muted pt-0.5 min-w-0">
              <MapPin className="w-3.5 h-3.5 text-secondary shrink-0" aria-hidden="true" />
              <span className="truncate">{locationLabel}</span>
            </div>
          ) : null}

          {tags && tags.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {tags.slice(0, 2).map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 rounded-md bg-surface-2 border border-subtle text-[11px] text-secondary truncate max-w-[160px]"
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {/* Footer Strip */}
        <div className="pt-3 border-t border-subtle flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-primary tabular-nums-lining truncate">
            {priceLabel || ""}
          </span>

          <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-400 group-hover:text-brand-300 shrink-0 transition-colors">
            <span>{ctaLabel}</span>
            <ArrowRight
              className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform"
              aria-hidden="true"
            />
          </span>
        </div>
      </div>
    </Link>
  );
}

