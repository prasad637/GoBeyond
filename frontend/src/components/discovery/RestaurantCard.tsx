"use client";

import React from "react";
import { RestaurantFeedItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";

export interface RestaurantCardProps {
  restaurant: RestaurantFeedItem;
  className?: string;
}

function formatCuisines(cuisines?: string[] | string | null): {
  text: string | null;
  tags: string[];
} {
  if (!cuisines) return { text: null, tags: [] };
  if (Array.isArray(cuisines)) {
    const clean = cuisines.filter(Boolean);
    return {
      text: clean.length > 0 ? clean.join(", ") : null,
      tags: clean,
    };
  }
  const split = String(cuisines)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return {
    text: split.length > 0 ? split.join(", ") : null,
    tags: split,
  };
}

export function RestaurantCard({ restaurant, className }: RestaurantCardProps) {
  const { text: cuisinesText } = formatCuisines(restaurant.cuisines);

  const badgeText = restaurant.is_pure_veg
    ? "Pure Veg"
    : restaurant.has_buffet
    ? "Buffet"
    : null;

  return (
    <MediaCard
      href={`/dining/${restaurant.slug}`}
      title={restaurant.name}
      imageSrc={restaurant.images?.[0] || null}
      fallbackCategory="dining"
      aspectRatio="16/10"
      topLeftBadge={
        badgeText ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-[11px] font-medium text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
            <span>{badgeText}</span>
          </span>
        ) : undefined
      }
      rating={restaurant.rating}
      ratingSubLabel={
        restaurant.review_count && restaurant.review_count > 0
          ? `(${restaurant.review_count.toLocaleString("en-IN")})`
          : null
      }
      distanceKm={restaurant.distance_km}
      subtitle={cuisinesText}
      locationLabel={restaurant.location_name || restaurant.address}
      priceLabel={
        typeof restaurant.cost_for_two === "number" && restaurant.cost_for_two > 0
          ? `₹${restaurant.cost_for_two.toLocaleString("en-IN")} for two`
          : null
      }
      ctaLabel="Reserve Table"
      className={className}
    />
  );
}

