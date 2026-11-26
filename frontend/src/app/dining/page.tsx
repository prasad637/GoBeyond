"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, UtensilsCrossed, Wine } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { RestaurantFeedItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import { ListingPageHeader } from "@/components/discovery/ListingPageHeader";
import { ListingFilterToolbar } from "@/components/discovery/ListingFilterToolbar";
import { DiscoveryGrid } from "@/components/discovery/DiscoveryGrid";
import { RestaurantCard } from "@/components/discovery/RestaurantCard";
import { cn } from "@/lib/cn";

const BUDGET_CHIPS = [
  { label: "Any Budget", value: "" },
  { label: "Under ₹1,200", value: "under_1200" },
  { label: "₹1,200–₹2,200", value: "mid" },
  { label: "₹2,200+", value: "premium" },
];

function extractCuisineTokens(cuisines?: string[] | string | null): string[] {
  if (!cuisines) return [];
  if (Array.isArray(cuisines)) return cuisines.filter(Boolean).map((c) => c.trim());
  return String(cuisines)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function DiningPage() {
  const { selectedLocality, gpsCoordinates } = useLocation();

  const [restaurants, setRestaurants] = useState<RestaurantFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [pureVegOnly, setPureVegOnly] = useState(false);
  const [buffetOnly, setBuffetOnly] = useState(false);
  const [drinksOnly, setDrinksOnly] = useState(false);
  const [selectedCuisine, setSelectedCuisine] = useState("");
  const [budgetTier, setBudgetTier] = useState("");
  const [sortBy, setSortBy] = useState("rating_desc");

  const requestSeq = useRef(0);

  const fetchRestaurants = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedLocality) params.append("locality", selectedLocality.slug);
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }
      if (pureVegOnly) params.append("pure_veg", "true");
      if (sortBy === "distance" && gpsCoordinates) params.append("sort_by", "distance");

      const qs = params.toString();
      const data = await apiRequest<RestaurantFeedItem[]>(`/dining/${qs ? `?${qs}` : ""}`);
      if (seq !== requestSeq.current) return;
      setRestaurants(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load restaurants right now.";
      setError(msg);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [selectedLocality, gpsCoordinates, pureVegOnly, sortBy]);

  useEffect(() => {
    fetchRestaurants();
  }, [fetchRestaurants]);

  const cuisineOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of restaurants) {
      for (const token of extractCuisineTokens(r.cuisines)) {
        counts.set(token, (counts.get(token) || 0) + 1);
      }
    }
    const topCuisines = Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 6)
      .map(([name]) => ({ label: name, value: name }));

    return [{ label: "All Cuisines", value: "" }, ...topCuisines];
  }, [restaurants]);

  const sortOptions = useMemo(() => {
    const base = [
      { label: "Top Rated", value: "rating_desc" },
      { label: "Cost: Low to High", value: "cost_asc" },
      { label: "Cost: High to Low", value: "cost_desc" },
    ];
    if (gpsCoordinates) {
      base.unshift({ label: "Nearest First", value: "distance" });
    }
    return base;
  }, [gpsCoordinates]);

  const filteredRestaurants = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const cuisineLower = selectedCuisine.toLowerCase();

    const filtered = restaurants.filter((r) => {
      if (pureVegOnly && !r.is_pure_veg) return false;
      if (buffetOnly && !r.has_buffet) return false;
      if (drinksOnly && !r.has_alcohol) return false;

      const cuisineList = extractCuisineTokens(r.cuisines);
      if (
        cuisineLower &&
        !cuisineList.some((c) => c.toLowerCase() === cuisineLower)
      ) {
        return false;
      }

      const cost = r.cost_for_two || 0;
      if (budgetTier === "under_1200" && cost >= 1200) return false;
      if (budgetTier === "mid" && (cost < 1200 || cost > 2200)) return false;
      if (budgetTier === "premium" && cost <= 2200) return false;

      if (q) {
        const hay = `${r.name} ${cuisineList.join(" ")} ${r.address || ""} ${r.location_name || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "distance" && gpsCoordinates) {
        return (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity);
      }
      if (sortBy === "cost_asc") return (a.cost_for_two || 0) - (b.cost_for_two || 0);
      if (sortBy === "cost_desc") return (b.cost_for_two || 0) - (a.cost_for_two || 0);
      return (b.rating || 0) - (a.rating || 0);
    });
  }, [
    restaurants,
    pureVegOnly,
    buffetOnly,
    drinksOnly,
    selectedCuisine,
    budgetTier,
    searchQuery,
    sortBy,
    gpsCoordinates,
  ]);

  const activeFilterCount =
    (pureVegOnly ? 1 : 0) +
    (buffetOnly ? 1 : 0) +
    (drinksOnly ? 1 : 0) +
    (selectedCuisine ? 1 : 0) +
    (budgetTier ? 1 : 0) +
    (searchQuery.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setPureVegOnly(false);
    setBuffetOnly(false);
    setDrinksOnly(false);
    setSelectedCuisine("");
    setBudgetTier("");
    setSearchQuery("");
    setSortBy("rating_desc");
  };

  return (
    <div className="min-h-screen bg-canvas text-primary pb-16">
      <ListingPageHeader
        eyebrow="GO BEYOND • DINING"
        icon={<UtensilsCrossed className="w-3.5 h-3.5" aria-hidden="true" />}
        title="Dining & Culinary Experiences"
        subtitle="Reserve tables instantly with zero booking fee at royal Nizami kitchens, rooftop lounges and specialty cafés"
        breadcrumbLabel="Dining"
        resultCount={filteredRestaurants.length}
        resultLabel="restaurants"
        loading={loading}
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <ListingFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search restaurant, cuisine or area..."
          extraInlineSlot={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                aria-pressed={pureVegOnly}
                onClick={() => setPureVegOnly((prev) => !prev)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors inline-flex items-center gap-1.5",
                  pureVegOnly
                    ? "bg-emerald-500/15 border-emerald-500/45 text-emerald-300"
                    : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                )}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400" aria-hidden="true" />
                <span>Pure Veg Only</span>
                {pureVegOnly ? <Check className="w-3.5 h-3.5" aria-hidden="true" /> : null}
              </button>

              <button
                type="button"
                aria-pressed={buffetOnly}
                onClick={() => setBuffetOnly((prev) => !prev)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
                  buffetOnly
                    ? "bg-brand-500/15 border-brand-500/45 text-brand-300"
                    : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                )}
              >
                Buffet
              </button>

              <button
                type="button"
                aria-pressed={drinksOnly}
                onClick={() => setDrinksOnly((prev) => !prev)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors inline-flex items-center gap-1.5",
                  drinksOnly
                    ? "bg-brand-500/15 border-brand-500/45 text-brand-300"
                    : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                )}
              >
                <Wine className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Bar & Drinks</span>
              </button>
            </div>
          }
          secondaryGroups={[
            ...(cuisineOptions.length > 1
              ? [
                  {
                    id: "cuisine",
                    label: "Cuisine",
                    options: cuisineOptions,
                    selectedValue: selectedCuisine,
                    onSelect: setSelectedCuisine,
                  },
                ]
              : []),
            {
              id: "budget",
              label: "Cost for two",
              options: BUDGET_CHIPS,
              selectedValue: budgetTier,
              onSelect: setBudgetTier,
            },
          ]}
          sortOptions={sortOptions}
          selectedSort={sortBy}
          onSortChange={setSortBy}
          activeFilterCount={activeFilterCount}
          onClearAll={handleClearFilters}
          drawerTitle="Filter Restaurants"
        />

        <DiscoveryGrid
          loading={loading}
          error={error}
          onRetry={fetchRestaurants}
          isEmpty={filteredRestaurants.length === 0}
          categoryLabel="restaurants"
          hasActiveFilters={activeFilterCount > 0}
          onClearFilters={handleClearFilters}
          skeletonAspect="16/10"
          skeletonCount={6}
          columnsClassName="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6"
        >
          {filteredRestaurants.map((restaurant) => (
            <RestaurantCard key={restaurant.id} restaurant={restaurant} />
          ))}
        </DiscoveryGrid>
      </div>
    </div>
  );
}
