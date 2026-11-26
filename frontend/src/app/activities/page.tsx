"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Compass } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { ActivityFeedItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import { ListingPageHeader } from "@/components/discovery/ListingPageHeader";
import { ListingFilterToolbar } from "@/components/discovery/ListingFilterToolbar";
import { DiscoveryGrid } from "@/components/discovery/DiscoveryGrid";
import { ExperienceCard } from "@/components/discovery/ExperienceCard";

const CATEGORY_CHIPS = [
  { label: "All", value: "" },
  { label: "Adventure", value: "ADVENTURE" },
  { label: "Gaming Zone", value: "GAMING_ZONE" },
  { label: "Amusement", value: "AMUSEMENT" },
];

const PRICE_CHIPS = [
  { label: "Any Price", value: "" },
  { label: "Under ₹500", value: "under_500" },
  { label: "₹500–₹1,000", value: "mid" },
  { label: "₹1,000+", value: "premium" },
];

export default function ActivitiesPage() {
  const { gpsCoordinates } = useLocation();

  const [activities, setActivities] = useState<ActivityFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState("");
  const [priceTier, setPriceTier] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("title");

  const requestSeq = useRef(0);

  const fetchActivities = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.append("category", selectedCategory);
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }
      if (sortBy === "distance" && gpsCoordinates) params.append("sort_by", "distance");

      const qs = params.toString();
      const data = await apiRequest<ActivityFeedItem[]>(
        `/activities/${qs ? `?${qs}` : ""}`
      );
      if (seq !== requestSeq.current) return;
      setActivities(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load activities right now.";
      setError(msg);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [selectedCategory, gpsCoordinates, sortBy]);

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  const sortOptions = useMemo(() => {
    const base = [
      { label: "A–Z", value: "title" },
      { label: "Price: Low to High", value: "price_asc" },
      { label: "Price: High to Low", value: "price_desc" },
      { label: "Duration: Shortest", value: "duration_asc" },
    ];
    if (gpsCoordinates) {
      base.unshift({ label: "Nearest First", value: "distance" });
    }
    return base;
  }, [gpsCoordinates]);

  const filteredActivities = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    const filtered = activities.filter((act) => {
      if (act.category?.toUpperCase() === "SPORTS") return false;
      const price = act.base_price ?? 0;
      if (priceTier === "under_500" && price >= 500) return false;
      if (priceTier === "mid" && (price < 500 || price > 1000)) return false;
      if (priceTier === "premium" && price <= 1000) return false;

      if (q) {
        const hay = `${act.title} ${act.description || ""} ${act.venue_name || ""} ${act.location_name || ""} ${act.category || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "distance" && gpsCoordinates) {
        return (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity);
      }
      if (sortBy === "price_asc") return (a.base_price ?? 0) - (b.base_price ?? 0);
      if (sortBy === "price_desc") return (b.base_price ?? 0) - (a.base_price ?? 0);
      if (sortBy === "duration_asc") {
        return (a.duration_minutes ?? 999) - (b.duration_minutes ?? 999);
      }
      return (a.title || "").localeCompare(b.title || "");
    });
  }, [activities, priceTier, searchQuery, sortBy, gpsCoordinates]);

  const activeFilterCount =
    (selectedCategory ? 1 : 0) +
    (priceTier ? 1 : 0) +
    (searchQuery.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setSelectedCategory("");
    setPriceTier("");
    setSearchQuery("");
    setSortBy("title");
  };

  return (
    <div className="min-h-screen bg-canvas text-primary pb-16">
      <ListingPageHeader
        eyebrow="GO BEYOND • ACTIVITIES"
        icon={<Compass className="w-3.5 h-3.5" aria-hidden="true" />}
        title="Activities & Recreation"
        subtitle="High-speed go-karting tracks, escape rooms, VR gaming arenas and interactive city thrills"
        breadcrumbLabel="Activities"
        resultCount={filteredActivities.length}
        resultLabel="activities"
        loading={loading}
        cityWideScope
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <ListingFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search activity or venue..."
          primaryLabel="Category"
          primaryChips={CATEGORY_CHIPS}
          selectedPrimaryValue={selectedCategory}
          onPrimarySelect={setSelectedCategory}
          secondaryGroups={[
            {
              id: "price",
              label: "Slot Price",
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
          drawerTitle="Filter Activities"
        />

        <DiscoveryGrid
          loading={loading}
          error={error}
          onRetry={fetchActivities}
          isEmpty={filteredActivities.length === 0}
          categoryLabel="activities"
          hasActiveFilters={activeFilterCount > 0}
          onClearFilters={handleClearFilters}
          cityWideScope
          skeletonAspect="16/10"
          skeletonCount={6}
          columnsClassName="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6"
        >
          {filteredActivities.map((activity) => (
            <ExperienceCard key={activity.id} activity={activity} />
          ))}
        </DiscoveryGrid>
      </div>
    </div>
  );
}
