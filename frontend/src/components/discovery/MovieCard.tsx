"use client";

import React from "react";
import { MovieFeedItem } from "@/types/discovery";
import { MediaCard } from "@/components/discovery/MediaCard";

export interface MovieCardProps {
  movie: MovieFeedItem;
  className?: string;
}

function formatReleaseDate(dateStr?: string | null): string | null {
  if (!dateStr) return null;
  const parsed = new Date(`${dateStr}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function MovieCard({ movie, className }: MovieCardProps) {
  const formattedRelease = formatReleaseDate(movie.release_date);
  const topBadge = [movie.language, movie.censor_rating].filter(Boolean).join(" • ");
  const metaSubtitle = [movie.genre, movie.duration_minutes ? `${movie.duration_minutes}m` : null]
    .filter(Boolean)
    .join(" • ");

  return (
    <MediaCard
      href={`/movies/${movie.slug}`}
      title={movie.title}
      imageSrc={movie.poster_url || movie.backdrop_url}
      fallbackCategory="movies"
      aspectRatio="2/3"
      topLeftBadge={
        topBadge ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-primary truncate max-w-[140px]">
            {topBadge}
          </span>
        ) : undefined
      }
      rating={movie.rating}
      subtitle={metaSubtitle || null}
      eyebrow={formattedRelease ? `Release · ${formattedRelease}` : undefined}
      priceLabel={movie.language ? `${movie.language} Cinema` : undefined}
      ctaLabel="View Details"
      className={className}
    />
  );
}

