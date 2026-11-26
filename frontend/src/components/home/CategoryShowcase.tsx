"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CalendarDays,
  Compass,
  Film,
  Trophy,
  UtensilsCrossed,
} from "lucide-react";
import { HomeFeedResponse } from "@/types/discovery";
import { SectionHeading } from "@/components/discovery/SectionHeading";
import { SafeMediaImage, MediaCategoryFallback } from "@/components/ui/SafeMediaImage";
import { cn } from "@/lib/cn";

export interface CategoryShowcaseProps {
  feed?: HomeFeedResponse | null;
}

interface CategoryTileConfig {
  key: MediaCategoryFallback;
  title: string;
  subtitle: string;
  href: string;
  imageSrc: string;
  icon: React.ComponentType<{ className?: string }>;
  getCount: (feed?: HomeFeedResponse | null) => number | null;
}

const CATEGORIES: CategoryTileConfig[] = [
  {
    key: "movies",
    title: "Movies",
    subtitle: "Cinema & Premieres",
    href: "/movies",
    imageSrc: "/images/categories/movies.jpg",
    icon: Film,
    getCount: (feed) => (feed ? feed.movies.length : null),
  },
  {
    key: "dining",
    title: "Dining",
    subtitle: "Tables & Cafes",
    href: "/dining",
    imageSrc: "/images/categories/dining.jpg",
    icon: UtensilsCrossed,
    getCount: (feed) => (feed ? feed.restaurants.length : null),
  },
  {
    key: "events",
    title: "Events",
    subtitle: "Live & Comedy",
    href: "/events",
    imageSrc: "/images/categories/events.jpg",
    icon: CalendarDays,
    getCount: (feed) => (feed ? feed.events.length : null),
  },
  {
    key: "sports",
    title: "Sports",
    subtitle: "Turfs & Courts",
    href: "/sports",
    imageSrc: "/images/categories/sports.jpg",
    icon: Trophy,
    getCount: (feed) => (feed ? feed.sports_venues.length : null),
  },
  {
    key: "activities",
    title: "Activities",
    subtitle: "Tracks & Gaming",
    href: "/activities",
    imageSrc: "/images/categories/activities.jpg",
    icon: Compass,
    getCount: (feed) =>
      feed
        ? feed.activities.filter((act) => act.category?.toUpperCase() !== "SPORTS").length
        : null,
  },
];

export function CategoryShowcase({ feed }: CategoryShowcaseProps) {
  return (
    <section id="explore-categories" aria-labelledby="categories-heading">
      <SectionHeading
        headingId="categories-heading"
        eyebrow="Curated Verticals"
        title="Explore by Category"
        subtitle="Direct entry into five entertainment and lifestyle verticals across the city."
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5 sm:gap-4">
        {CATEGORIES.map((cat, idx) => {
          const Icon = cat.icon;
          const liveCount = cat.getCount(feed);

          return (
            <Link
              key={cat.key}
              href={cat.href}
              className={cn(
                "group relative rounded-xl bg-surface border border-subtle hover:border-brand-500/50 overflow-hidden shadow-surface hover:-translate-y-0.5 transition-all duration-200 flex flex-col",
                idx === CATEGORIES.length - 1 && "col-span-2 sm:col-span-1"
              )}
            >
              {/* Moody Dark Category Media */}
              <div
                className={cn(
                  "relative w-full overflow-hidden bg-surface-2",
                  idx === CATEGORIES.length - 1
                    ? "aspect-[21/9] sm:aspect-[16/10]"
                    : "aspect-[16/10]"
                )}
              >
                <SafeMediaImage
                  src={cat.imageSrc}
                  alt={cat.title}
                  fallbackCategory={cat.key}
                  eager
                  sizes="(max-width: 640px) 48vw, (max-width: 1024px) 32vw, 250px"
                  showFallbackWatermark={false}
                  className="group-hover:scale-105"
                />

                <div
                  aria-hidden="true"
                  className="absolute inset-0 bg-gradient-to-t from-canvas via-canvas/30 to-black/20"
                />

                <div className="absolute top-2.5 left-2.5 right-2.5 z-10 flex items-center justify-between gap-2">
                  <span className="w-8 h-8 rounded-lg bg-canvas/85 backdrop-blur-md border border-white/10 flex items-center justify-center text-brand-400 group-hover:text-brand-300 transition-colors">
                    <Icon className="w-4 h-4" aria-hidden="true" />
                  </span>

                  {typeof liveCount === "number" && liveCount > 0 ? (
                    <span className="px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-champagne tabular-nums-lining">
                      {liveCount} live
                    </span>
                  ) : null}
                </div>
              </div>

              {/* Clean Footer Typography */}
              <div className="p-3.5 sm:p-4 flex items-center justify-between gap-2 bg-surface">
                <div className="min-w-0">
                  <h3 className="font-display text-sm sm:text-base font-bold text-primary group-hover:text-brand-400 transition-colors truncate">
                    {cat.title}
                  </h3>
                  <p className="text-[11px] sm:text-xs text-secondary truncate mt-0.5">
                    {cat.subtitle}
                  </p>
                </div>

                <ArrowRight
                  className="w-4 h-4 text-muted group-hover:text-brand-400 group-hover:translate-x-0.5 transition-all shrink-0"
                  aria-hidden="true"
                />
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
