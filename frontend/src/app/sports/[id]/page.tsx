"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  MapPin,
  ShieldCheck,
  Star,
  Trophy,
  Users,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { ActivityFeedItem, SportsVenueFeedItem } from "@/types/discovery";
import { DetailPageHero } from "@/components/booking/DetailPageHero";
import { DetailPageState } from "@/components/booking/DetailPageState";
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

export default function SportsVenueDetailPage() {
  const params = useParams();
  const venueId = params.id as string;

  const [venue, setVenue] = useState<SportsVenueFeedItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchVenue = useCallback(async () => {
    if (!venueId) return;
    if (!/^\d+$/.test(venueId)) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);
    setNotFound(false);

    try {
      const data = await apiRequest<SportsVenueFeedItem>(
        `/sports/venues/${venueId}`
      );
      setVenue(data);
    } catch (err: any) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setLoadError(err?.message || "Failed to load sports venue details.");
      }
    } finally {
      setLoading(false);
    }
  }, [venueId]);

  useEffect(() => {
    fetchVenue();
  }, [fetchVenue]);

  const sportList = useMemo(() => normalizeList(venue?.sport_types), [venue]);
  const amenityList = useMemo(() => normalizeList(venue?.amenities), [venue]);
  const courts: ActivityFeedItem[] = useMemo(
    () => venue?.activities || [],
    [venue]
  );

  const minCourtRate = useMemo(() => {
    const prices = courts
      .map((c) => c.base_price)
      .filter((p): p is number => typeof p === "number" && !Number.isNaN(p));
    return prices.length > 0 ? Math.min(...prices) : null;
  }, [courts]);

  if (loading) {
    return (
      <DetailPageState
        mode="loading"
        backHref="/sports"
        backLabel="Back to Sports Venues"
        entityLabel="sports venue"
      />
    );
  }

  if (notFound || !venue) {
    return (
      <DetailPageState
        mode={loadError ? "error" : "not-found"}
        backHref="/sports"
        backLabel="Back to Sports Venues"
        entityLabel="sports venue"
        errorMessage={loadError}
        onRetry={fetchVenue}
      />
    );
  }

  const galleryImages = [
    ...(venue.images || []),
    ...courts.map((c) => c.image_url).filter((u): u is string => Boolean(u)),
  ];

  const primaryCourt = courts[0];

  return (
    <div className="min-h-screen bg-canvas text-primary pb-20">
      <DetailPageHero
        backHref="/sports"
        backLabel="All Venues"
        verticalLabel="Sports"
        title={venue.name}
        subtitle={sportList.length > 0 ? sportList.join(" • ") : undefined}
        heroImages={galleryImages}
        fallbackCategory="sports"
        badges={
          <>
            <Badge variant="success" size="md">
              Sports Venue
            </Badge>
            {venue.location_name ? (
              <Badge variant="default" size="md">
                {venue.location_name}
              </Badge>
            ) : null}
            {typeof venue.rating === "number" && venue.rating > 0 ? (
              <Badge
                variant="gold"
                size="md"
                icon={<Star className="w-3.5 h-3.5 fill-champagne text-champagne" />}
              >
                {venue.rating.toFixed(1)}
              </Badge>
            ) : null}
          </>
        }
        metadata={[
          ...(venue.address
            ? [
              {
                id: "address",
                icon: <MapPin className="w-4 h-4 text-brand-400" aria-hidden="true" />,
                label: venue.address,
              },
            ]
            : []),
          {
            id: "courts",
            icon: <Trophy className="w-4 h-4 text-champagne" aria-hidden="true" />,
            label: `${courts.length} ${courts.length === 1 ? "Court" : "Courts"} Bookable`,
          },
        ]}
        rightCallout={
          minCourtRate !== null ? (
            <div className="px-4 py-3 rounded-2xl bg-surface/90 border border-strong backdrop-blur-md text-left md:text-right">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted block">
                Hourly Slots From
              </span>
              <span className="font-display text-2xl font-extrabold text-primary tabular-nums-lining">
                ₹{Math.round(minCourtRate).toLocaleString("en-IN")}
              </span>
              <span className="text-xs text-secondary block">per session</span>
            </div>
          ) : null
        }
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 mt-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10">
          {/* Left Column: Sports, Facilities, and Bookable Courts */}
          <div className="lg:col-span-2 space-y-8">
            {/* Supported Sports & Amenities */}
            {(sportList.length > 0 || amenityList.length > 0) && (
              <section className="p-6 bg-surface border border-subtle rounded-2xl shadow-surface space-y-6">
                {sportList.length > 0 ? (
                  <div className="space-y-2.5">
                    <h2 className="font-display font-bold text-lg text-primary">
                      Sports Supported
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {sportList.map((sport) => (
                        <Badge key={sport} variant="success" size="md">
                          {sport}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : null}

                {amenityList.length > 0 ? (
                  <div className="space-y-3 pt-4 border-t border-subtle">
                    <h2 className="font-display font-bold text-lg text-primary">
                      Facilities & Amenities
                    </h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {amenityList.map((amenity) => (
                        <div
                          key={amenity}
                          className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-surface-2 border border-subtle text-xs sm:text-sm text-secondary"
                        >
                          <CheckCircle2
                            className="w-4 h-4 text-emerald-400 shrink-0"
                            aria-hidden="true"
                          />
                          <span>{amenity}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>
            )}

            {/* Bookable Courts & Turfs */}
            <section id="venue-courts" className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-subtle">
                <h2 className="font-display text-xl sm:text-2xl font-bold text-primary flex items-center gap-2.5">
                  <Trophy className="w-5 h-5 text-brand-500 shrink-0" aria-hidden="true" />
                  <span>Bookable Courts & Turfs</span>
                </h2>
                <span className="text-xs text-secondary">Live Slot Booking</span>
              </div>

              {courts.length === 0 ? (
                <div className="p-6 rounded-2xl bg-surface border border-subtle text-sm text-secondary">
                  No courts or turfs are currently listed as active for online booking at this venue.
                </div>
              ) : (
                <div className="space-y-4">
                  {courts.map((court) => (
                    <article
                      key={court.id}
                      className="p-4 sm:p-5 bg-surface border border-subtle hover:border-strong rounded-2xl shadow-surface flex flex-col sm:flex-row gap-4 sm:items-center justify-between transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row gap-4 min-w-0 flex-1">
                        <div className="relative w-full sm:w-36 aspect-[16/10] rounded-xl overflow-hidden bg-surface-2 border border-subtle shrink-0">
                          <SafeMediaImage
                            src={court.image_url || venue.images?.[0]}
                            alt={court.title}
                            fallbackCategory="sports"
                            sizes="(max-width: 640px) 100vw, 144px"
                          />
                        </div>

                        <div className="space-y-1.5 min-w-0">
                          <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-champagne">
                            {court.category}
                          </span>
                          <h3 className="font-display font-bold text-base sm:text-lg text-primary">
                            {court.title}
                          </h3>
                          {court.description ? (
                            <p className="text-xs text-secondary line-clamp-2 leading-relaxed">
                              {court.description}
                            </p>
                          ) : null}
                          <div className="flex flex-wrap items-center gap-3 text-xs text-muted pt-1">
                            <span className="inline-flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5 text-brand-400" aria-hidden="true" />
                              <span>{court.duration_minutes} mins</span>
                            </span>
                            {court.min_age ? (
                              <span className="inline-flex items-center gap-1">
                                <Users className="w-3.5 h-3.5 text-champagne" aria-hidden="true" />
                                <span>Age {court.min_age}+</span>
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>

                      <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 pt-3 sm:pt-0 border-t sm:border-t-0 border-subtle shrink-0">
                        <div className="text-left sm:text-right">
                          <span className="text-[11px] text-muted block">Per Slot</span>
                          <span className="font-mono text-lg font-bold text-primary tabular-nums-lining">
                            ₹{Math.round(court.base_price || 0).toLocaleString("en-IN")}
                          </span>
                        </div>

                        <Link
                          href={`/activities/${court.slug}?vertical=sports`}
                          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm transition-colors"
                        >
                          <span>Book Slot</span>
                          <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Sticky Venue Booking Card */}
          <aside className="space-y-5">
            <div className="sticky top-24 p-6 bg-surface border border-subtle rounded-2xl shadow-elevated space-y-5">
              <div className="border-b border-subtle pb-4">
                <h3 className="font-display font-extrabold text-lg text-primary">
                  Arena Quick Booking
                </h3>
                <p className="text-xs text-secondary mt-1">
                  Select a court below to pick an hourly time slot
                </p>
              </div>

              <dl className="text-xs space-y-2.5">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">Locality</dt>
                  <dd className="font-semibold text-primary">
                    {venue.location_name || "Hyderabad"}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">Venue Rating</dt>
                  <dd className="font-semibold text-champagne">
                    {(venue.rating || 4.5).toFixed(1)} / 5.0
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">Active Courts</dt>
                  <dd className="font-semibold text-primary">{courts.length}</dd>
                </div>
              </dl>

              {primaryCourt ? (
                <Link
                  href={`/activities/${primaryCourt.slug}?vertical=sports`}
                  className="w-full min-h-[44px] py-2.5 px-5 rounded-xl bg-brand-500 hover:bg-brand-600 text-sm font-semibold text-white text-center shadow-brand-sm flex items-center justify-center gap-2 transition-colors"
                >
                  <span>Book {primaryCourt.title.split("(")[0].trim()}</span>
                  <ArrowRight className="w-4 h-4 shrink-0" aria-hidden="true" />
                </Link>
              ) : (
                <Link
                  href="/sports"
                  className="w-full h-11 px-5 rounded-xl bg-surface-2 hover:bg-surface-3 border border-subtle text-sm font-semibold text-primary flex items-center justify-center gap-2 transition-colors"
                >
                  <span>Explore Other Venues</span>
                </Link>
              )}

              <div className="flex items-start gap-2 text-[11px] text-muted pt-1">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
                <span>
                  Verified partner turf with instant Razorpay confirmation & QR check-in.
                </span>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

