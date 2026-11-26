"use client";

import React from "react";
import { EventFeedItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";

export interface EventCardProps {
  event: EventFeedItem;
  className?: string;
}

function formatEventDateTime(isoStr?: string | null): string | null {
  if (!isoStr) return null;
  const parsed = new Date(isoStr);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: "Asia/Kolkata",
  });
}

function formatCategoryLabel(category?: string | null): string | null {
  if (!category) return null;
  return category
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function EventCard({ event, className }: EventCardProps) {
  const formattedSchedule = formatEventDateTime(event.start_datetime);
  const categoryLabel = formatCategoryLabel(event.category);

  let priceLabel: string | null = null;
  if (typeof event.lowest_price === "number") {
    priceLabel =
      event.lowest_price > 0
        ? `From ₹${Math.round(event.lowest_price).toLocaleString("en-IN")}`
        : "Free Entry";
  }

  return (
    <MediaCard
      href={`/events/${event.slug}`}
      title={event.title}
      imageSrc={event.banner_url || null}
      fallbackCategory="events"
      aspectRatio="16/10"
      topLeftBadge={
        categoryLabel ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-primary">
            {categoryLabel}
          </span>
        ) : undefined
      }
      eyebrow={formattedSchedule ?? undefined}
      subtitle={event.venue_name || event.artist_names || null}
      locationLabel={event.location_name || event.venue_address}
      distanceKm={event.distance_km}
      priceLabel={priceLabel}
      ctaLabel="View Event"
      className={className}
    />
  );
}

