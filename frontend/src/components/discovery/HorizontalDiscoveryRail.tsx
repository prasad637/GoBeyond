"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface HorizontalDiscoveryRailProps {
  children: React.ReactNode;
  ariaLabel: string;
  itemDensity?: "poster" | "landscape";
  className?: string;
}

export function HorizontalDiscoveryRail({
  children,
  ariaLabel,
  itemDensity = "landscape",
  className,
}: HorizontalDiscoveryRailProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollButtons = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 8);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 8);
  }, []);

  useEffect(() => {
    updateScrollButtons();
    window.addEventListener("resize", updateScrollButtons);
    return () => window.removeEventListener("resize", updateScrollButtons);
  }, [updateScrollButtons, children]);

  const scrollByAmount = (direction: -1 | 1) => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = Math.max(260, Math.round(el.clientWidth * 0.78));
    el.scrollBy({ left: direction * distance, behavior: "smooth" });
  };

  return (
    <div className={cn("relative group/rail", className)}>
      {/* Desktop Left Navigation Arrow */}
      {canScrollLeft && (
        <button
          type="button"
          onClick={() => scrollByAmount(-1)}
          aria-label={`Scroll ${ariaLabel} left`}
          className="hidden lg:flex items-center justify-center w-10 h-10 rounded-full bg-surface-2/95 hover:bg-surface-3 border border-strong text-primary shadow-elevated backdrop-blur-md absolute -left-3 top-[38%] -translate-y-1/2 z-20 transition-all"
        >
          <ChevronLeft className="w-5 h-5" aria-hidden="true" />
        </button>
      )}

      {/* Horizontal Snap Rail */}
      <div
        ref={scrollRef}
        onScroll={updateScrollButtons}
        role="region"
        aria-label={ariaLabel}
        className={cn(
          "flex overflow-x-auto snap-x snap-mandatory scroll-smooth no-scrollbar pb-2",
          itemDensity === "poster" ? "gap-4 sm:gap-5" : "gap-4 sm:gap-5"
        )}
      >
        {children}
      </div>

      {/* Desktop Right Navigation Arrow */}
      {canScrollRight && (
        <button
          type="button"
          onClick={() => scrollByAmount(1)}
          aria-label={`Scroll ${ariaLabel} right`}
          className="hidden lg:flex items-center justify-center w-10 h-10 rounded-full bg-surface-2/95 hover:bg-surface-3 border border-strong text-primary shadow-elevated backdrop-blur-md absolute -right-3 top-[38%] -translate-y-1/2 z-20 transition-all"
        >
          <ChevronRight className="w-5 h-5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export interface RailItemWrapperProps {
  children: React.ReactNode;
  variant?: "poster" | "landscape";
  className?: string;
}

export function RailItemWrapper({
  children,
  variant = "landscape",
  className,
}: RailItemWrapperProps) {
  return (
    <div
      className={cn(
        "snap-start shrink-0",
        variant === "poster"
          ? "w-[62%] min-w-[205px] max-w-[260px] sm:w-[225px] md:w-[235px] lg:w-[242px]"
          : "w-[84%] min-w-[270px] max-w-[380px] sm:w-[320px] md:w-[335px] lg:w-[360px]",
        className
      )}
    >
      {children}
    </div>
  );
}

