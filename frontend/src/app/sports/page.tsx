"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ChevronRight,
  Clock,
  MapPin,
  Navigation,
  Star,
  Trophy,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { SportsVenueFeedItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import { ListingPageHeader } from "@/components/discovery/ListingPageHeader";
import { ListingFilterToolbar } from "@/components/discovery/ListingFilterToolbar";
import { DiscoveryGrid } from "@/components/discovery/DiscoveryGrid";
import { SafeMediaImage } from "@/components/ui/SafeMediaImage";
import { Badge } from "@/components/ui/Badge";

function normalizeList(input?: string[] | string | null): string[] {
  if (!input) return [];
  if (Array.isArray(input)) return input.filter(Boolean).map((s) => s.trim());
  return String(input)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function SportsPage() {
  const { gpsCoordinates } = useLocation();

  const [venues, setVenues] = useState<SportsVenueFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedSport, setSelectedSport] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("rating");

  const requestSeq = useRef(0);

  const fetchVenues = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }
      if (sortBy === "distance" && gpsCoordinates) params.append("sort_by", "distance");

      const qs = params.toString();
      const data = await apiRequest<SportsVenueFeedItem[]>(
        `/sports/venues${qs ? `?${qs}` : ""}`
      );
      if (seq !== requestSeq.current) return;
      setVenues(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load sports venues right now.";
      setError(msg);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [gpsCoordinates, sortBy]);

  useEffect(() => {
    fetchVenues();
  }, [fetchVenues]);

  const sportChips = useMemo(() => {
    const counts = new Map<string, number>();
    for (const venue of venues) {
      for (const sport of normalizeList(venue.sport_types)) {
        counts.set(sport, (counts.get(sport) || 0) + 1);
      }
    }
    const topSports = Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 5)
      .map(([sport]) => ({ label: sport, value: sport }));

    return [{ label: "All Sports", value: "" }, ...topSports];
  }, [venues]);

  const sortOptions = useMemo(() => {
    const base = [
      { label: "Top Rated", value: "rating" },
      { label: "Rate: Low to High", value: "price_asc" },
    ];
    if (gpsCoordinates) {
      base.unshift({ label: "Nearest First", value: "distance" });
    }
    return base;
  }, [gpsCoordinates]);

  const filteredVenues = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const sportLower = selectedSport.toLowerCase();

    const filtered = venues.filter((v) => {
      const sportsList = normalizeList(v.sport_types);
      const amenitiesList = normalizeList(v.amenities);
      const acts = v.activities || [];

      if (
        sportLower &&
        !sportsList.some((s) => s.toLowerCase().includes(sportLower))
      ) {
        return false;
      }

      if (q) {
        const actsText = acts.map((a) => `${a.title} ${a.description || ""}`).join(" ");
        const hay = `${v.name} ${v.address || ""} ${v.location_name || ""} ${sportsList.join(" ")} ${amenitiesList.join(" ")} ${actsText}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }

      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "distance" && gpsCoordinates) {
        return (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity);
      }
      if (sortBy === "price_asc") {
        const minPrice = (venue: SportsVenueFeedItem) => {
          const prices = (venue.activities || [])
            .map((x) => x.base_price)
            .filter((p): p is number => typeof p === "number");
          return prices.length > 0 ? Math.min(...prices) : Infinity;
        };
        return minPrice(a) - minPrice(b);
      }
      return (b.rating || 0) - (a.rating || 0);
    });
  }, [venues, selectedSport, searchQuery, sortBy, gpsCoordinates]);

  const activeFilterCount =
    (selectedSport ? 1 : 0) + (searchQuery.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setSelectedSport("");
    setSearchQuery("");
    setSortBy("rating");
  };

  return (
    <div className="min-h-screen bg-canvas text-primary pb-16">
      <ListingPageHeader
        eyebrow="GO BEYOND • SPORTS & TURFS"
        icon={<Trophy className="w-3.5 h-3.5" aria-hidden="true" />}
        title="Sports Venues & Turfs"
        subtitle="Book BWF-grade badminton courts, FIFA-standard 5-a-side football turfs and floodlit cricket arenas"
        breadcrumbLabel="Sports"
        resultCount={filteredVenues.length}
        resultLabel="venues"
        loading={loading}
        cityWideScope
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <ListingFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search arena, sport or court..."
          primaryLabel="Sport Type"
          primaryChips={sportChips.length > 1 ? sportChips : undefined}
          selectedPrimaryValue={selectedSport}
          onPrimarySelect={setSelectedSport}
          sortOptions={sortOptions}
          selectedSort={sortBy}
          onSortChange={setSortBy}
          activeFilterCount={activeFilterCount}
          onClearAll={handleClearFilters}
          drawerTitle="Filter Sports Venues"
        />

        <DiscoveryGrid
          loading={loading}
          error={error}
          onRetry={fetchVenues}
          isEmpty={filteredVenues.length === 0}
          categoryLabel="sports venues"
          hasActiveFilters={activeFilterCount > 0}
          onClearFilters={handleClearFilters}
          cityWideScope
          skeletonAspect="16/10"
          skeletonCount={4}
          columnsClassName="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {filteredVenues.map((venue) => {
            const sportList = normalizeList(venue.sport_types);
            const amenityList = normalizeList(venue.amenities);
            const courts = venue.activities || [];
            const heroImage = venue.images?.[0] || courts[0]?.image_url || null;

            return (
              <article
                key={venue.id}
                className="bg-surface border border-subtle hover:border-strong rounded-2xl overflow-hidden shadow-surface flex flex-col transition-all duration-200"
              >
                {/* Venue Hero Image Linking to Dedicated Venue Page */}
                <Link
                  href={`/sports/${venue.id}`}
                  className="group relative aspect-[16/10] w-full overflow-hidden bg-surface-2 block"
                >
                  <SafeMediaImage
                    src={heroImage}
                    alt={venue.name}
                    fallbackCategory="sports"
                    eager
                    sizes="(max-width: 1024px) 100vw, 640px"
                    className="group-hover:scale-105"
                  />
                  <div
                    aria-hidden="true"
                    className="absolute inset-0 bg-gradient-to-t from-canvas/90 via-transparent to-black/30"
                  />

                  <div className="absolute top-3 inset-x-3 flex items-center justify-between gap-2">
                    <span className="px-2.5 py-1 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 font-mono text-[10px] font-medium uppercase tracking-wider text-primary">
                      {courts.length} {courts.length === 1 ? "Court" : "Courts"} Available
                    </span>

                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-xs font-semibold text-champagne tabular-nums-lining">
                      <Star className="w-3.5 h-3.5 fill-champagne text-champagne" aria-hidden="true" />
                      <span>{(venue.rating || 4.5).toFixed(1)}</span>
                    </span>
                  </div>

                  <div className="absolute bottom-3 inset-x-3 flex items-center justify-between gap-2">
                    {typeof venue.distance_km === "number" ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-[11px] font-medium text-emerald-400 tabular-nums-lining">
                        <Navigation className="w-3 h-3" aria-hidden="true" />
                        <span>{venue.distance_km.toFixed(1)} km</span>
                      </span>
                    ) : (
                      <span />
                    )}

                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-canvas/85 backdrop-blur-md border border-white/10 text-xs font-semibold text-brand-400 group-hover:text-brand-300">
                      <span>Venue Details</span>
                      <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                    </span>
                  </div>
                </Link>

                {/* Venue Body & Direct Court Slot Booking */}
                <div className="p-5 sm:p-6 flex-1 flex flex-col justify-between gap-5">
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Link
                          href={`/sports/${venue.id}`}
                          className="font-display text-lg sm:text-xl font-bold tracking-tight text-primary hover:text-brand-400 transition-colors block truncate"
                        >
                          {venue.name}
                        </Link>
                        <p className="text-xs text-secondary flex items-center gap-1.5 mt-1">
                          <MapPin className="w-3.5 h-3.5 text-brand-400 shrink-0" aria-hidden="true" />
                          <span className="truncate">{venue.address}</span>
                        </p>
                      </div>
                    </div>

                    {sportList.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {sportList.map((sport) => (
                          <Badge key={sport} variant="success" size="sm">
                            {sport}
                          </Badge>
                        ))}
                      </div>
                    ) : null}

                    {amenityList.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {amenityList.slice(0, 3).map((amenity) => (
                          <span
                            key={amenity}
                            className="px-2 py-0.5 rounded-md bg-surface-2 border border-subtle text-[11px] text-secondary"
                          >
                            {amenity}
                          </span>
                        ))}
                        {amenityList.length > 3 ? (
                          <span className="px-2 py-0.5 rounded-md bg-surface-2 border border-subtle text-[11px] text-muted">
                            +{amenityList.length - 3} more
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  {/* Bookable Courts / Turfs List */}
                  <div className="space-y-2.5 pt-4 border-t border-subtle">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-secondary">
                        Bookable Courts & Turfs
                      </span>
                      <Link
                        href={`/sports/${venue.id}`}
                        className="text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors"
                      >
                        Full Venue Info
                      </Link>
                    </div>

                    {courts.length === 0 ? (
                      <p className="text-xs text-muted py-2">
                        Court schedule details available on the venue page.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {courts.map((act) => (
                          <Link
                            key={act.id}
                            href={`/activities/${act.slug}?vertical=sports`}
                            className="group p-3 rounded-xl bg-surface-2/80 hover:bg-surface-2 border border-subtle hover:border-brand-500/40 flex items-center justify-between gap-3 transition-colors"
                          >
                            <div className="min-w-0">
                              <div className="font-semibold text-xs sm:text-sm text-primary group-hover:text-brand-400 transition-colors truncate">
                                {act.title}
                              </div>
                              <div className="text-[11px] text-secondary flex items-center gap-2 mt-0.5">
                                <span className="inline-flex items-center gap-1">
                                  <Clock className="w-3 h-3 text-muted" aria-hidden="true" />
                                  <span>{act.duration_minutes} mins</span>
                                </span>
                                {typeof act.base_price === "number" ? (
                                  <span className="font-mono text-primary font-semibold tabular-nums-lining">
                                    • From ₹{Math.round(act.base_price)}
                                  </span>
                                ) : null}
                              </div>
                            </div>

                            <span className="px-3 py-1.5 rounded-lg bg-brand-500 group-hover:bg-brand-600 text-white text-xs font-semibold inline-flex items-center gap-1 shrink-0 shadow-brand-sm transition-colors">
                              <span>Book Slot</span>
                              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
                            </span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </DiscoveryGrid>
      </div>
    </div>
  );
}
