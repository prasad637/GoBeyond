"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  X,
  SlidersHorizontal,
  Navigation,
  Film,
  UtensilsCrossed,
  CalendarDays,
  Trophy,
  Compass,
  Loader2,
} from "lucide-react";
import { SearchResultItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import {
  SEARCH_CATEGORIES,
  SEARCH_PRICE_RANGES,
  useDiscoverySearch,
} from "@/hooks/useDiscoverySearch";
import { SearchResultsList } from "@/components/discovery/SearchResultsList";
import { cn } from "@/lib/cn";

interface SearchBarProps {
  onSearchSelected?: (item: SearchResultItem) => void;
  className?: string;
}

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }> | null> = {
  ALL: null,
  MOVIES: Film,
  DINING: UtensilsCrossed,
  EVENTS: CalendarDays,
  SPORTS: Trophy,
  ACTIVITIES: Compass,
};

export function SearchBar({ onSearchSelected, className = "" }: SearchBarProps) {
  const { selectedCity, selectedLocality, gpsCoordinates } = useLocation();
  const [showFilters, setShowFilters] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const {
    query,
    setQuery,
    selectedCategory,
    setSelectedCategory,
    selectedPriceIdx,
    setSelectedPriceIdx,
    sortBy,
    setSortBy,
    results,
    totalCount,
    isLoading,
    error,
    hasActiveFilter,
    retry,
    resetFilters,
  } = useDiscoverySearch({
    pageSize: 6,
    debounceMs: 250,
    fetchWhenFilterActive: showFilters,
    onResultsLoaded: () => setIsOpen(true),
  });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const showDropdown =
    isOpen && (Boolean(query.trim()) || results.length > 0 || isLoading || Boolean(error) || showFilters);

  return (
    <div ref={containerRef} className={cn("relative w-full max-w-3xl mx-auto", className)}>
      {/* Search Input Bar */}
      <div className="relative flex items-center bg-surface border border-strong hover:border-brand-500/60 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 rounded-2xl shadow-elevated transition-colors duration-200">
        <div className="pl-4 pr-2 text-secondary">
          {isLoading ? (
            <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen && e.target.value.trim()) setIsOpen(true);
          }}
          onFocus={() => {
            if (results.length > 0 || query.trim() || error) setIsOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setIsOpen(false);
            }
          }}
          placeholder={
            selectedLocality
              ? `Search movies, dining, events in ${selectedLocality.name}...`
              : `Search movies, restaurants, events, turfs in ${selectedCity}...`
          }
          aria-label="Search experiences"
          className="w-full py-3.5 bg-transparent text-primary text-base sm:text-sm placeholder:text-muted focus:outline-none"
        />

        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear search query"
            className="p-2 mr-1 text-secondary hover:text-primary rounded-lg hover:bg-surface-2 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        <button
          type="button"
          onClick={() => {
            setShowFilters((prev) => !prev);
            setIsOpen(true);
          }}
          aria-expanded={showFilters}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 mr-2 text-xs font-semibold rounded-xl border transition-colors shrink-0",
            showFilters || selectedCategory !== "ALL" || selectedPriceIdx !== 0
              ? "bg-brand-500/15 border-brand-500/50 text-brand-300"
              : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:bg-surface-3"
          )}
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Filters</span>
        </button>
      </div>

      {/* Expanded Filter Panel */}
      {showFilters && (
        <div className="mt-2.5 p-4 bg-surface border border-subtle rounded-2xl shadow-elevated text-xs space-y-3.5 animate-slideInTop">
          <div>
            <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider block mb-2">
              Vertical
            </span>
            <div className="flex flex-wrap gap-1.5">
              {SEARCH_CATEGORIES.map((cat) => {
                const Icon = CATEGORY_ICONS[cat.key];
                const isSelected = selectedCategory === cat.key;
                return (
                  <button
                    key={cat.key}
                    type="button"
                    onClick={() => setSelectedCategory(cat.key)}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium border transition-colors",
                      isSelected
                        ? "bg-brand-500 border-brand-500 text-white shadow-brand-sm"
                        : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:bg-surface-3"
                    )}
                  >
                    {Icon ? <Icon className="w-3.5 h-3.5" /> : null}
                    <span>{cat.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider block mb-2">
              Price Range
            </span>
            <div className="flex flex-wrap gap-1.5">
              {SEARCH_PRICE_RANGES.map((pr, idx) => (
                <button
                  key={pr.label}
                  type="button"
                  onClick={() => setSelectedPriceIdx(idx)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg font-medium border transition-colors",
                    selectedPriceIdx === idx
                      ? "bg-brand-500/15 border-brand-500/50 text-brand-300 font-semibold"
                      : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:bg-surface-3"
                  )}
                >
                  {pr.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2.5 border-t border-subtle">
            <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider">
              Sort By
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => setSortBy("relevance")}
                className={cn(
                  "px-2.5 py-1 rounded-lg transition-colors",
                  sortBy === "relevance"
                    ? "bg-surface-3 text-primary font-semibold"
                    : "text-secondary hover:text-primary"
                )}
              >
                Relevance
              </button>
              <button
                type="button"
                onClick={() => setSortBy("rating")}
                className={cn(
                  "px-2.5 py-1 rounded-lg transition-colors",
                  sortBy === "rating"
                    ? "bg-surface-3 text-primary font-semibold"
                    : "text-secondary hover:text-primary"
                )}
              >
                Top Rated
              </button>
              {gpsCoordinates && (
                <button
                  type="button"
                  onClick={() => setSortBy("distance")}
                  className={cn(
                    "px-2.5 py-1 rounded-lg flex items-center gap-1 transition-colors",
                    sortBy === "distance"
                      ? "bg-surface-3 text-primary font-semibold"
                      : "text-secondary hover:text-primary"
                  )}
                >
                  <Navigation className="w-3 h-3 text-emerald-400" />
                  <span>Nearest</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => setSortBy("price_asc")}
                className={cn(
                  "px-2.5 py-1 rounded-lg transition-colors",
                  sortBy === "price_asc"
                    ? "bg-surface-3 text-primary font-semibold"
                    : "text-secondary hover:text-primary"
                )}
              >
                Price: Low to High
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Live Dropdown Results */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-surface border border-strong rounded-2xl shadow-modal overflow-hidden z-50 animate-fadeIn">
          <SearchResultsList
            query={query}
            results={results}
            totalCount={totalCount}
            isLoading={isLoading}
            error={error}
            localityName={selectedLocality?.name ?? selectedCity}
            onSelect={(item) => {
              setIsOpen(false);
              onSearchSelected?.(item);
            }}
            onRetry={retry}
            onResetFilters={hasActiveFilter ? resetFilters : undefined}
          />
        </div>
      )}
    </div>
  );
}
