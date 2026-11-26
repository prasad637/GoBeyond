"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Sparkles } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { EventFeedItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import { ListingPageHeader } from "@/components/discovery/ListingPageHeader";
import { ListingFilterToolbar } from "@/components/discovery/ListingFilterToolbar";
import { DiscoveryGrid } from "@/components/discovery/DiscoveryGrid";
import { EventCard } from "@/components/discovery/EventCard";
import { cn } from "@/lib/cn";

const BASE_CATEGORIES = [
  { label: "All", value: "" },
  { label: "Concert", value: "CONCERT" },
  { label: "Comedy", value: "COMEDY" },
  { label: "Cultural", value: "CULTURAL" },
];

const PRICE_CHIPS = [
  { label: "Any Price", value: "" },
  { label: "Under ₹500", value: "under_500" },
  { label: "₹500–₹1,500", value: "mid" },
  { label: "₹1,500+", value: "premium" },
];

export default function EventsPage() {
  const { gpsCoordinates } = useLocation();

  const [events, setEvents] = useState<EventFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [priceTier, setPriceTier] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("date");

  const requestSeq = useRef(0);

  const fetchEvents = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.append("category", selectedCategory);
      if (featuredOnly) params.append("featured_only", "true");
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }
      if (sortBy === "distance" && gpsCoordinates) params.append("sort_by", "distance");

      const qs = params.toString();
      const data = await apiRequest<EventFeedItem[]>(`/events/${qs ? `?${qs}` : ""}`);
      if (seq !== requestSeq.current) return;
      setEvents(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load events right now.";
      setError(msg);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [selectedCategory, featuredOnly, gpsCoordinates, sortBy]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const sortOptions = useMemo(() => {
    const base = [
      { label: "Soonest First", value: "date" },
      { label: "Price: Low to High", value: "price_asc" },
      { label: "Price: High to Low", value: "price_desc" },
    ];
    if (gpsCoordinates) {
      base.unshift({ label: "Nearest First", value: "distance" });
    }
    return base;
  }, [gpsCoordinates]);

  const filteredEvents = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    const filtered = events.filter((ev) => {
      const price = ev.lowest_price ?? 0;
      if (priceTier === "under_500" && price >= 500) return false;
      if (priceTier === "mid" && (price < 500 || price > 1500)) return false;
      if (priceTier === "premium" && price <= 1500) return false;

      if (q) {
        const hay = `${ev.title} ${ev.artist_names || ""} ${ev.venue_name || ""} ${ev.location_name || ""} ${ev.category || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "distance" && gpsCoordinates) {
        return (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity);
      }
      if (sortBy === "price_asc") return (a.lowest_price ?? 0) - (b.lowest_price ?? 0);
      if (sortBy === "price_desc") return (b.lowest_price ?? 0) - (a.lowest_price ?? 0);
      return (a.start_datetime || "").localeCompare(b.start_datetime || "");
    });
  }, [events, priceTier, searchQuery, sortBy, gpsCoordinates]);

  const activeFilterCount =
    (selectedCategory ? 1 : 0) +
    (featuredOnly ? 1 : 0) +
    (priceTier ? 1 : 0) +
    (searchQuery.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setSelectedCategory("");
    setFeaturedOnly(false);
    setPriceTier("");
    setSearchQuery("");
    setSortBy("date");
  };

  return (
    <div className="min-h-screen bg-canvas text-primary pb-16">
      <ListingPageHeader
        eyebrow="GO BEYOND • LIVE STAGE"
        icon={<CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />}
        title="Live Events & Concerts"
        subtitle="Stadium arena tours, standup comedy specials, cultural nights and electronic music festivals"
        breadcrumbLabel="Events"
        resultCount={filteredEvents.length}
        resultLabel="events"
        loading={loading}
        cityWideScope
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <ListingFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search event, artist or venue..."
          primaryLabel="Category"
          primaryChips={BASE_CATEGORIES}
          selectedPrimaryValue={selectedCategory}
          onPrimarySelect={setSelectedCategory}
          extraInlineSlot={
            <button
              type="button"
              aria-pressed={featuredOnly}
              onClick={() => setFeaturedOnly((prev) => !prev)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors inline-flex items-center gap-1.5",
                featuredOnly
                  ? "bg-champagne/15 border-champagne/40 text-champagne"
                  : "bg-surface-2 border-subtle text-secondary hover:text-primary"
              )}
            >
              <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Featured</span>
            </button>
          }
          secondaryGroups={[
            {
              id: "price",
              label: "Entry Price",
              options: PRICE_CHIPS,
              selectedValue: priceTier,
              onSelect: setPriceTier,
            },
          ]}
          sortOptions={sortOptions}
          selectedSort={sortBy}
          onSortChange={setSortBy}
          activeFilterCount={activeFilterCount}
          onClearAll={handleClearFilters}
          drawerTitle="Filter Events"
        />

        <DiscoveryGrid
          loading={loading}
          error={error}
          onRetry={fetchEvents}
          isEmpty={filteredEvents.length === 0}
          categoryLabel="events"
          hasActiveFilters={activeFilterCount > 0}
          onClearFilters={handleClearFilters}
          cityWideScope
          skeletonAspect="16/10"
          skeletonCount={6}
          columnsClassName="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6"
        >
          {filteredEvents.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </DiscoveryGrid>
      </div>
    </div>
  );
}
