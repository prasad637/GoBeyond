"use client";

import React from "react";
import { ActivityFeedItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";

export interface ExperienceCardProps {
  activity: ActivityFeedItem;
  className?: string;
}

function formatActivityCategory(cat?: string | null): string | null {
  if (!cat) return null;
  return cat
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function ExperienceCard({ activity, className }: ExperienceCardProps) {
  const categoryLabel = formatActivityCategory(activity.category);
  const metaParts = [
    activity.duration_minutes ? `${activity.duration_minutes} mins` : null,
    activity.min_age ? `Age ${activity.min_age}+` : null,
  ].filter(Boolean);

  const locationParts = [activity.venue_name, activity.location_name]
    .filter(Boolean)
    .join(" • ");

  return (
    <MediaCard
      href={`/activities/${activity.slug}`}
      title={activity.title}
      imageSrc={activity.image_url || null}
      fallbackCategory={
        activity.category?.toUpperCase() === "SPORTS" ? "sports" : "activities"
      }
      aspectRatio="16/10"
      topLeftBadge={
        categoryLabel ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-primary">
            {categoryLabel}
          </span>
        ) : undefined
      }
      eyebrow={metaParts.length > 0 ? metaParts.join(" • ") : undefined}
      subtitle={activity.description || null}
      locationLabel={locationParts || null}
      distanceKm={activity.distance_km}
      priceLabel={
        typeof activity.base_price === "number"
          ? `₹${Math.round(activity.base_price).toLocaleString("en-IN")} / slot`
          : null
      }
      ctaLabel="Book Slot"
      className={className}
    />
  );
}

