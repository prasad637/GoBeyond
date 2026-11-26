"use client";

import React from "react";
import { SportsVenueFeedItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";

export interface VenueCardProps {
  venue: SportsVenueFeedItem;
  className?: string;
}

function normalizeSportTypes(sportTypes?: string[] | string | null): string[] {
  if (!sportTypes) return [];
  if (Array.isArray(sportTypes)) return sportTypes.filter(Boolean);
  return String(sportTypes)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function VenueCard({ venue, className }: VenueCardProps) {
  const sportList = normalizeSportTypes(venue.sport_types);
  const activities = venue.activities || [];
  const primaryActivity = activities.find((act) => Boolean(act?.slug));

  const validPrices = activities
    .map((a) => a.base_price)
    .filter((p): p is number => typeof p === "number" && !Number.isNaN(p) && p >= 0);

  let priceLabel: string | null = null;
  if (validPrices.length > 0) {
    const minPrice = Math.min(...validPrices);
    priceLabel = `From ₹${Math.round(minPrice).toLocaleString("en-IN")} / slot`;
  } else if (activities.length > 0) {
    priceLabel = `${activities.length} bookable ${activities.length === 1 ? "experience" : "experiences"}`;
  }

  return (
    <MediaCard
      href={`/sports/${venue.id}`}
      title={venue.name}
      imageSrc={venue.images?.[0] || primaryActivity?.image_url || null}
      fallbackCategory="sports"
      aspectRatio="16/10"
      rating={venue.rating}
      distanceKm={venue.distance_km}
      subtitle={primaryActivity?.title || sportList.join(" • ") || null}
      locationLabel={venue.location_name || venue.address}
      tags={sportList.slice(0, 2)}
      priceLabel={priceLabel}
      ctaLabel="Explore Venue"
      className={className}
    />
  );
}

