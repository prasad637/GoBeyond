"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Clock,
  MapPin,
  Phone,
  Search,
  Sparkles,
  Star,
  Users,
  UtensilsCrossed,
  Wine,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { DetailPageHero } from "@/components/booking/DetailPageHero";
import { DetailPageState } from "@/components/booking/DetailPageState";
import { BookingSuccessState } from "@/components/booking/BookingSuccessState";
import { SafeMediaImage } from "@/components/ui/SafeMediaImage";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

interface MenuItemData {
  id: number;
  category: string;
  item_name: string;
  description?: string | null;
  price: number;
  is_veg: boolean;
  is_bestseller: boolean;
  image_url?: string | null;
  is_available: boolean;
}

interface DiningTableData {
  id: number;
  table_number: string;
  capacity: number;
  zone: string;
  is_active: boolean;
}

interface RestaurantDetailData {
  id: number;
  name: string;
  slug: string;
  cuisines: string[] | string;
  cost_for_two: number;
  address: string;
  phone: string;
  timings: string;
  images: string[];
  rating: number;
  review_count: number;
  has_buffet: boolean;
  has_alcohol: boolean;
  is_pure_veg: boolean;
  is_active: boolean;
  location_name?: string | null;
  menus: MenuItemData[];
  tables: DiningTableData[];
}

const TIME_SLOTS = [
  "12:30:00",
  "13:30:00",
  "19:00:00",
  "19:30:00",
  "20:30:00",
  "21:30:00",
];

const GUEST_OPTIONS = [1, 2, 4, 6, 8];

export default function RestaurantDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const router = useRouter();
  const { user, openAuthModal } = useAuth();

  const [restaurant, setRestaurant] = useState<RestaurantDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // Menu browsing filters
  const [menuSearch, setMenuSearch] = useState("");
  const [menuFilter, setMenuFilter] = useState<"all" | "veg" | "bestseller">("all");

  // Reservation form state
  const todayStr = new Date().toISOString().split("T")[0];
  const [resDate, setResDate] = useState(todayStr);
  const [resTime, setResTime] = useState("19:30:00");
  const [guestCount, setGuestCount] = useState(2);
  const [selectedZone, setSelectedZone] = useState("");
  const [specialRequests, setSpecialRequests] = useState("");
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const submitInFlightRef = useRef(false);
  const [confirmedReservation, setConfirmedReservation] = useState<{
    booking_reference: string;
    table_number: string;
    reservation_date: string;
    reservation_time: string;
    guest_count: number;
  } | null>(null);

  const fetchRestaurant = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setLoadError(null);
    setNotFound(false);

    try {
      const data = await apiRequest<RestaurantDetailData>(`/dining/${slug}`);
      setRestaurant(data);
      const firstZone = data.tables?.[0]?.zone || "";
      setSelectedZone(firstZone);
    } catch (err: any) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setLoadError(err?.message || "Failed to load restaurant details.");
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchRestaurant();
  }, [fetchRestaurant]);

  const activeZones = useMemo(() => {
    if (!restaurant?.tables) return [];
    const map = new Map<string, number>();
    for (const t of restaurant.tables) {
      if (!t.is_active) continue;
      map.set(t.zone, (map.get(t.zone) || 0) + 1);
    }
    return Array.from(map.entries()).map(([zone, count]) => ({ zone, count }));
  }, [restaurant]);

  const groupedMenus = useMemo(() => {
    if (!restaurant?.menus) return {};
    const q = menuSearch.trim().toLowerCase();
    const groups: Record<string, MenuItemData[]> = {};

    for (const item of restaurant.menus) {
      if (menuFilter === "veg" && !item.is_veg) continue;
      if (menuFilter === "bestseller" && !item.is_bestseller) continue;
      if (q) {
        const hay = `${item.item_name} ${item.description || ""} ${item.category}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      if (!groups[item.category]) groups[item.category] = [];
      groups[item.category].push(item);
    }
    return groups;
  }, [restaurant, menuSearch, menuFilter]);

  const handleReserveTable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!restaurant) return;
    if (!user) {
      openAuthModal("login");
      return;
    }
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;

    setBookingLoading(true);
    setBookingError(null);

    try {
      const res = await apiRequest<{
        booking_reference: string;
        table_number: string;
        reservation_date: string;
        reservation_time: string;
        guest_count: number;
      }>("/dining/reserve", {
        method: "POST",
        body: JSON.stringify({
          restaurant_id: restaurant.id,
          reservation_date: resDate,
          reservation_time: resTime,
          guest_count: guestCount,
          zone_preference: selectedZone || undefined,
          special_requests: specialRequests || undefined,
        }),
      });
      setConfirmedReservation(res);
    } catch (err: any) {
      setBookingError(err?.message || "Failed to reserve table.");
    } finally {
      submitInFlightRef.current = false;
      setBookingLoading(false);
    }
  };

  if (loading) {
    return (
      <DetailPageState
        mode="loading"
        backHref="/dining"
        backLabel="Back to Dining"
        entityLabel="restaurant"
      />
    );
  }

  if (notFound || !restaurant) {
    return (
      <DetailPageState
        mode={loadError ? "error" : "not-found"}
        backHref="/dining"
        backLabel="Back to Dining"
        entityLabel="restaurant"
        errorMessage={loadError}
        onRetry={fetchRestaurant}
      />
    );
  }

  const cuisineDisplay = Array.isArray(restaurant.cuisines)
    ? restaurant.cuisines.join(" • ")
    : restaurant.cuisines;

  return (
    <div className="min-h-screen bg-canvas text-primary pb-24 md:pb-20">
      <DetailPageHero
        backHref="/dining"
        backLabel="All Restaurants"
        verticalLabel="Dining"
        title={restaurant.name}
        subtitle={cuisineDisplay}
        heroImages={restaurant.images || []}
        fallbackCategory="dining"
        badges={
          <>
            <Badge variant={restaurant.is_pure_veg ? "veg" : "default"} dot size="md">
              {restaurant.is_pure_veg ? "Pure Vegetarian" : "Multi-Cuisine"}
            </Badge>
            {restaurant.has_buffet ? (
              <Badge variant="gold" size="md">
                Buffet Available
              </Badge>
            ) : null}
            {restaurant.has_alcohol ? (
              <Badge
                variant="info"
                size="md"
                icon={<Wine className="w-3.5 h-3.5" />}
              >
                Bar & Cocktails
              </Badge>
            ) : null}
            {restaurant.rating > 0 ? (
              <Badge
                variant="gold"
                size="md"
                icon={<Star className="w-3.5 h-3.5 fill-champagne text-champagne" />}
              >
                {restaurant.rating.toFixed(1)}
                {restaurant.review_count > 0
                  ? ` (${restaurant.review_count.toLocaleString("en-IN")} reviews)`
                  : ""}
              </Badge>
            ) : null}
          </>
        }
        metadata={[
          {
            id: "address",
            icon: <MapPin className="w-4 h-4 text-brand-400" aria-hidden="true" />,
            label: restaurant.address,
          },
          {
            id: "timings",
            icon: <Clock className="w-4 h-4 text-champagne" aria-hidden="true" />,
            label: restaurant.timings,
          },
          ...(restaurant.phone
            ? [
                {
                  id: "phone",
                  icon: <Phone className="w-4 h-4 text-emerald-400" aria-hidden="true" />,
                  label: restaurant.phone,
                  value: (
                    <a
                      href={`tel:${restaurant.phone.replace(/\s+/g, "")}`}
                      className="hover:text-primary transition-colors"
                    >
                      {restaurant.phone}
                    </a>
                  ),
                },
              ]
            : []),
        ]}
        rightCallout={
          <div className="px-4 py-3 rounded-2xl bg-surface/90 border border-strong backdrop-blur-md text-left md:text-right">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted block">
              Approx. Cost
            </span>
            <span className="font-display text-2xl font-extrabold text-primary tabular-nums-lining">
              ₹{restaurant.cost_for_two.toLocaleString("en-IN")}
            </span>
            <span className="text-xs text-secondary block">for two guests</span>
          </div>
        }
      />

      {/* MAIN CONTENT GRID */}
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 mt-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10">
          {/* Left Column: Seating Zones + Digital Menu */}
          <div className="lg:col-span-2 space-y-8">
            {activeZones.length > 0 ? (
              <section className="p-5 sm:p-6 bg-surface border border-subtle rounded-2xl shadow-surface space-y-3">
                <h2 className="font-display text-base sm:text-lg font-bold text-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-champagne" aria-hidden="true" />
                  <span>Available Dining Zones</span>
                </h2>
                <div className="flex flex-wrap gap-2">
                  {activeZones.map(({ zone, count }) => (
                    <div
                      key={zone}
                      className="px-3 py-1.5 rounded-xl bg-surface-2 border border-subtle text-xs text-primary flex items-center gap-2"
                    >
                      <span className="font-semibold">{zone}</span>
                      <span className="font-mono text-[11px] text-secondary">
                        {count} {count === 1 ? "table" : "tables"}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {/* Digital Menu */}
            <section className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-subtle">
                <div>
                  <h2 className="font-display text-xl sm:text-2xl font-bold flex items-center gap-2.5 text-primary">
                    <UtensilsCrossed
                      className="w-5 h-5 text-brand-500 shrink-0"
                      aria-hidden="true"
                    />
                    <span>Chef&apos;s Digital Menu</span>
                  </h2>
                  <p className="text-xs text-secondary mt-0.5">
                    {restaurant.menus?.length || 0} curated dishes available
                  </p>
                </div>

                {restaurant.menus?.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-1 p-1 rounded-xl bg-surface border border-subtle">
                      {[
                        { label: "All", value: "all" as const },
                        { label: "Veg Only", value: "veg" as const },
                        { label: "Bestsellers", value: "bestseller" as const },
                      ].map((tab) => (
                        <button
                          key={tab.value}
                          type="button"
                          onClick={() => setMenuFilter(tab.value)}
                          className={cn(
                            "px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors",
                            menuFilter === tab.value
                              ? "bg-brand-500 text-white"
                              : "text-secondary hover:text-primary"
                          )}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    <div className="relative">
                      <Search
                        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted"
                        aria-hidden="true"
                      />
                      <input
                        type="text"
                        placeholder="Filter menu..."
                        aria-label="Filter menu items"
                        value={menuSearch}
                        onChange={(e) => setMenuSearch(e.target.value)}
                        className="h-9 pl-8 pr-3 w-40 sm:w-48 bg-surface border border-subtle rounded-xl text-base md:text-xs text-primary placeholder:text-muted focus:outline-none focus:border-brand-500"
                      />
                    </div>
                  </div>
                ) : null}
              </div>

              {Object.keys(groupedMenus).length === 0 ? (
                <div className="p-6 rounded-2xl bg-surface border border-subtle text-xs sm:text-sm text-secondary">
                  {restaurant.menus?.length === 0
                    ? "Menu items are currently being updated by the restaurant."
                    : "No dishes match your current menu filter."}
                </div>
              ) : (
                <div className="space-y-8">
                  {Object.entries(groupedMenus).map(([category, items]) => (
                    <div key={category} className="space-y-3.5">
                      <h3 className="font-mono text-xs font-bold text-champagne uppercase tracking-widest">
                        {category}
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {items.map((menuItem) => (
                          <div
                            key={menuItem.id}
                            className={cn(
                              "p-4 bg-surface border border-subtle rounded-2xl flex items-start justify-between gap-3.5 shadow-surface",
                              !menuItem.is_available && "opacity-60"
                            )}
                          >
                            <div className="space-y-1.5 flex-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span
                                  aria-label={menuItem.is_veg ? "Vegetarian" : "Non-vegetarian"}
                                  className={cn(
                                    "w-3.5 h-3.5 rounded-sm border flex items-center justify-center p-0.5 shrink-0",
                                    menuItem.is_veg
                                      ? "border-emerald-500"
                                      : "border-red-500"
                                  )}
                                >
                                  <span
                                    className={cn(
                                      "w-1.5 h-1.5 rounded-full",
                                      menuItem.is_veg ? "bg-emerald-500" : "bg-red-500"
                                    )}
                                  />
                                </span>

                                <span className="font-semibold text-sm text-primary">
                                  {menuItem.item_name}
                                </span>

                                {menuItem.is_bestseller ? (
                                  <Badge variant="gold" size="sm">
                                    Bestseller
                                  </Badge>
                                ) : null}
                              </div>

                              {menuItem.description ? (
                                <p className="text-xs text-secondary line-clamp-2 leading-relaxed">
                                  {menuItem.description}
                                </p>
                              ) : null}

                              <div className="flex items-center gap-2 pt-1">
                                <span className="font-mono text-sm font-bold text-primary tabular-nums-lining">
                                  ₹{Number(menuItem.price).toFixed(0)}
                                </span>
                                {!menuItem.is_available ? (
                                  <span className="text-[10px] font-medium text-muted">
                                    Currently unavailable
                                  </span>
                                ) : null}
                              </div>
                            </div>

                            {menuItem.image_url ? (
                              <div className="relative w-16 h-16 rounded-xl overflow-hidden bg-surface-2 border border-subtle shrink-0">
                                <SafeMediaImage
                                  src={menuItem.image_url}
                                  alt={menuItem.item_name}
                                  fallbackCategory="dining"
                                  sizes="64px"
                                  showFallbackWatermark={false}
                                />
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Sticky Table Reservation Card */}
          <aside id="reserve-table" className="space-y-5">
            <div className="sticky top-24 p-6 bg-surface border border-subtle rounded-2xl shadow-elevated space-y-5">
              <div className="border-b border-subtle pb-4">
                <h3 className="font-display font-extrabold text-lg sm:text-xl text-primary">
                  Reserve a Dining Table
                </h3>
                <p className="text-xs text-secondary mt-1">
                  Instant booking confirmation with zero reservation fee
                </p>
              </div>

              {confirmedReservation ? (
                <BookingSuccessState
                  headingTag="h4"
                  title="Table Reserved!"
                  subtitle={`Your table is booked at ${restaurant.name}.`}
                  rows={[
                    {
                      label: "Booking Code",
                      value: confirmedReservation.booking_reference,
                      accent: "brand",
                    },
                    {
                      label: "Assigned Table",
                      value: `Table ${confirmedReservation.table_number}`,
                    },
                    {
                      label: "Date & Time",
                      value: `${confirmedReservation.reservation_date} at ${confirmedReservation.reservation_time?.slice(0, 5)}`,
                    },
                    {
                      label: "Party Size",
                      value: `${confirmedReservation.guest_count} guests`,
                    },
                  ]}
                  primaryCtaLabel="View Confirmation Pass"
                  onPrimaryClick={() =>
                    router.push(
                      `/bookings/${confirmedReservation.booking_reference}/confirmation`
                    )
                  }
                  onSecondaryClick={() => router.push("/bookings")}
                />
              ) : (
                <form onSubmit={handleReserveTable} className="space-y-4">
                  {bookingError ? (
                    <div
                      role="alert"
                      className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2"
                    >
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                      <span>{bookingError}</span>
                    </div>
                  ) : null}

                  {/* Date Selection */}
                  <div>
                    <label
                      htmlFor="dining-res-date"
                      className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary mb-1.5"
                    >
                      Date
                    </label>
                    <input
                      id="dining-res-date"
                      type="date"
                      required
                      min={todayStr}
                      value={resDate}
                      onChange={(e) => setResDate(e.target.value)}
                      className="w-full h-10 px-3 bg-surface-2 border border-subtle rounded-xl text-base md:text-xs text-primary focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
                    />
                  </div>

                  {/* Guest Count */}
                  <div>
                    <span className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary mb-1.5">
                      Number of Guests
                    </span>
                    <div className="grid grid-cols-5 gap-1.5">
                      {GUEST_OPTIONS.map((count) => {
                        const isActive = guestCount === count;
                        return (
                          <button
                            key={count}
                            type="button"
                            onClick={() => setGuestCount(count)}
                            className={cn(
                              "py-2 rounded-xl text-xs font-bold border transition-colors",
                              isActive
                                ? "bg-brand-500 text-white border-brand-500 shadow-brand-sm"
                                : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:border-strong"
                            )}
                          >
                            {count}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Seating Zone Preference (only if multiple zones exist in API tables) */}
                  {activeZones.length > 1 ? (
                    <div>
                      <span className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary mb-1.5">
                        Seating Zone
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {activeZones.map(({ zone }) => (
                          <button
                            key={zone}
                            type="button"
                            onClick={() => setSelectedZone(zone)}
                            className={cn(
                              "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
                              selectedZone === zone
                                ? "bg-brand-500/15 border-brand-500/45 text-brand-300"
                                : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                            )}
                          >
                            {zone}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {/* Time Slots */}
                  <div>
                    <span className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary mb-1.5">
                      Select Time
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {TIME_SLOTS.map((slot) => {
                        const isSelected = resTime === slot;
                        return (
                          <button
                            key={slot}
                            type="button"
                            onClick={() => setResTime(slot)}
                            className={cn(
                              "py-2 rounded-xl font-mono text-xs font-bold border transition-colors tabular-nums-lining",
                              isSelected
                                ? "bg-brand-500 text-white border-brand-500 shadow-brand-sm"
                                : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:border-strong"
                            )}
                          >
                            {slot.slice(0, 5)}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Special Requests */}
                  <div>
                    <label
                      htmlFor="dining-special-requests"
                      className="block font-mono text-[11px] font-medium uppercase tracking-wider text-secondary mb-1.5"
                    >
                      Special Requests (Optional)
                    </label>
                    <textarea
                      id="dining-special-requests"
                      rows={2}
                      placeholder="e.g. Anniversary table, high chair, quiet corner"
                      value={specialRequests}
                      onChange={(e) => setSpecialRequests(e.target.value)}
                      className="w-full px-3 py-2 bg-surface-2 border border-subtle rounded-xl text-base md:text-xs text-primary placeholder:text-muted focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 resize-none"
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    fullWidth
                    isLoading={bookingLoading}
                    rightIcon={<ArrowRight className="w-4 h-4" aria-hidden="true" />}
                  >
                    Confirm Reservation
                  </Button>
                </form>
              )}
            </div>
          </aside>
        </div>
      </div>

      {/* Mobile Quick-Jump Sticky Bar above MobileBottomNav */}
      {!confirmedReservation ? (
        <div className="md:hidden fixed bottom-16 inset-x-0 z-30 bg-surface/95 backdrop-blur-md border-t border-subtle px-4 py-2.5 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-bold text-primary truncate">
              ₹{restaurant.cost_for_two.toLocaleString("en-IN")} for two
            </div>
            <div className="text-[11px] text-secondary flex items-center gap-1">
              <Users className="w-3 h-3 text-brand-400" aria-hidden="true" />
              <span>Zero reservation fee</span>
            </div>
          </div>
          <a
            href="#reserve-table"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm shrink-0"
          >
            <span>Reserve Table</span>
            <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
          </a>
        </div>
      ) : null}
    </div>
  );
}
