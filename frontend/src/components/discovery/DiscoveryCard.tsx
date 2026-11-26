"use client";

import React from "react";
import { SearchResultItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";
import { MediaCategoryFallback } from "@/components/ui/SafeMediaImage";

interface DiscoveryCardProps {
  item: SearchResultItem;
  className?: string;
}

function mapFallback(category: string): MediaCategoryFallback {
  switch (category?.toUpperCase()) {
    case "MOVIES":
      return "movies";
    case "DINING":
      return "dining";
    case "EVENTS":
      return "events";
    case "SPORTS":
      return "sports";
    case "ACTIVITIES":
      return "activities";
    default:
      return "default";
  }
}

export function DiscoveryCard({ item, className }: DiscoveryCardProps) {
  return (
    <MediaCard
      href={item.action_url}
      title={item.title}
      imageSrc={item.image_url}
      fallbackCategory={mapFallback(item.category)}
      aspectRatio={item.category?.toUpperCase() === "MOVIES" ? "2/3" : "16/10"}
      topLeftBadge={
        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-primary">
          {item.category_label || item.category}
        </span>
      }
      rating={item.rating}
      distanceKm={item.distance_km}
      subtitle={item.description}
      locationLabel={item.location_name}
      priceLabel={item.price_label}
      ctaLabel={item.action_label || "View Details"}
      className={className}
    />
  );
}
