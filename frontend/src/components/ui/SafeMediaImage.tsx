"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { cn } from "@/lib/cn";

export type MediaCategoryFallback =
  | "movies"
  | "dining"
  | "events"
  | "sports"
  | "activities"
  | "default";

const ALLOWED_REMOTE_HOSTS = new Set([
  "images.unsplash.com",
  "assets-in.bmscdn.com",
  "in.bmscdn.com",
  "media-assets.swiggy.com",
  "res.cloudinary.com",
]);

const FALLBACK_IMAGES: Record<MediaCategoryFallback, string> = {
  movies: "/images/categories/movies.jpg",
  dining: "/images/categories/dining.jpg",
  events: "/images/categories/events.jpg",
  sports: "/images/categories/sports.jpg",
  activities: "/images/categories/activities.jpg",
  default: "/images/hero-hyderabad.jpg",
};

const KNOWN_UNAVAILABLE_SUBSTRINGS = [
  "images.unsplash.com/photo-1529900245534-47fbf867b140",
];

function isSafeConfiguredRemote(src: string): boolean {
  if (src.startsWith("/")) return true;
  try {
    const parsed = new URL(src);
    return parsed.protocol === "https:" && ALLOWED_REMOTE_HOSTS.has(parsed.hostname);
  } catch {
    return false;
  }
}

export interface SafeMediaImageProps {
  src?: string | null;
  alt: string;
  fallbackCategory?: MediaCategoryFallback;
  sizes?: string;
  priority?: boolean;
  eager?: boolean;
  className?: string;
  showFallbackWatermark?: boolean;
}

export function SafeMediaImage({
  src,
  alt,
  fallbackCategory = "default",
  sizes = "(max-width: 640px) 80vw, (max-width: 1024px) 45vw, 320px",
  priority = false,
  eager = false,
  className,
  showFallbackWatermark = false,
}: SafeMediaImageProps) {
  const [primaryFailed, setPrimaryFailed] = useState(false);
  const [fallbackFailed, setFallbackFailed] = useState(false);

  useEffect(() => {
    setPrimaryFailed(false);
    setFallbackFailed(false);
  }, [src]);

  const trimmedSrc = typeof src === "string" && src.trim().length > 0 ? src.trim() : null;
  const cleanSrc =
    trimmedSrc &&
    KNOWN_UNAVAILABLE_SUBSTRINGS.some((dead) => trimmedSrc.includes(dead))
      ? null
      : trimmedSrc;
  const usingFallback = !cleanSrc || primaryFailed;
  const activeSrc = usingFallback ? FALLBACK_IMAGES[fallbackCategory] : cleanSrc;

  if (usingFallback && fallbackFailed) {
    return (
      <div
        aria-label={alt}
        className={cn(
          "absolute inset-0 flex items-center justify-center bg-surface-2 text-muted font-display font-bold tracking-widest text-xs uppercase select-none",
          className
        )}
      >
        GO BEYOND
      </div>
    );
  }

  const useUnoptimized = !usingFallback && !isSafeConfiguredRemote(activeSrc);
  const loadingMode = priority ? undefined : eager ? "eager" : "lazy";

  return (
    <>
      <Image
        src={activeSrc}
        alt={alt}
        fill
        sizes={sizes}
        priority={priority}
        loading={loadingMode}
        unoptimized={useUnoptimized}
        onError={() => {
          if (!usingFallback) {
            setPrimaryFailed(true);
          } else {
            setFallbackFailed(true);
          }
        }}
        className={cn(
          "object-cover transition-transform duration-500 ease-out",
          usingFallback && "brightness-75 contrast-105",
          className
        )}
      />
      {usingFallback && showFallbackWatermark && (
        <span
          aria-hidden="true"
          className="absolute bottom-2.5 right-2.5 z-10 px-2 py-0.5 rounded-md bg-canvas/75 border border-white/10 font-mono text-[10px] tracking-wider uppercase text-secondary pointer-events-none"
        >
          {fallbackCategory === "default" ? "GO BEYOND" : fallbackCategory}
        </span>
      )}
    </>
  );
}

