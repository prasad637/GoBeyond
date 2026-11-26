"use client";

import React from "react";
import { MediaCategoryFallback, SafeMediaImage } from "@/components/ui/SafeMediaImage";
import { cn } from "@/lib/cn";

export interface ImageGalleryProps {
  images: string[];
  altPrefix: string;
  activeIndex: number;
  onSelectIndex: (idx: number) => void;
  fallbackCategory?: MediaCategoryFallback;
  className?: string;
}

export function ImageGallery({
  images,
  altPrefix,
  activeIndex,
  onSelectIndex,
  fallbackCategory = "default",
  className,
}: ImageGalleryProps) {
  const validImages = images.filter(
    (img): img is string => typeof img === "string" && img.trim().length > 0
  );

  if (validImages.length <= 1) return null;

  return (
    <div
      role="group"
      aria-label={`${altPrefix} photo gallery`}
      className={cn("flex items-center gap-2 overflow-x-auto no-scrollbar py-1", className)}
    >
      {validImages.map((src, idx) => {
        const isActive = idx === activeIndex;
        return (
          <button
            key={`${src}-${idx}`}
            type="button"
            onClick={() => onSelectIndex(idx)}
            aria-label={`View photo ${idx + 1} of ${validImages.length}`}
            aria-pressed={isActive}
            className={cn(
              "relative w-16 h-11 sm:w-20 sm:h-14 rounded-lg overflow-hidden border shrink-0 transition-all",
              isActive
                ? "border-brand-500 ring-2 ring-brand-500/35 scale-[1.03]"
                : "border-strong/70 opacity-75 hover:opacity-100"
            )}
          >
            <SafeMediaImage
              src={src}
              alt={`${altPrefix} view ${idx + 1}`}
              fallbackCategory={fallbackCategory}
              sizes="80px"
              showFallbackWatermark={false}
            />
          </button>
        );
      })}
    </div>
  );
}

