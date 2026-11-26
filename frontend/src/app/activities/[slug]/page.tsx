"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Calendar,
  Clock,
  Compass,
  MapPin,
  Users,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { computeBookingTotals } from "@/lib/pricing";
import { completeRazorpayCheckoutForBooking } from "@/lib/razorpay";
import { DetailPageHero } from "@/components/booking/DetailPageHero";
import { DetailPageState } from "@/components/booking/DetailPageState";
import { CheckoutSummaryCard } from "@/components/booking/CheckoutSummaryCard";
import { BookingSuccessState } from "@/components/booking/BookingSuccessState";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

interface ActivitySlotItem {
  id: number;
  activity_id: number;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
  booked_count: number;
  available_spots: number;
  price: number;
  is_available: boolean;
}

interface ActivityDetailData {
  id: number;
  venue_id?: number | null;
  venue_name?: string | null;
  title: string;
  slug: string;
  category: string;
  description?: string | null;
  base_price: number;
  duration_minutes: number;
  image_url?: string | null;
  min_age: number;
  is_active: boolean;
  location_name?: string | null;
  slots: ActivitySlotItem[];
}

function formatSlotDateLabel(dateStr: string): string {
  const parsed = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return dateStr;
  return parsed.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export default function ActivityDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const router = useRouter();
  const { user, openAuthModal } = useAuth();

  const [activity, setActivity] = useState<ActivityDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // Selected slot & date grouping
  const [selectedSlotDate, setSelectedSlotDate] = useState<string>("");
  const [selectedSlot, setSelectedSlot] = useState<ActivitySlotItem | null>(null);
  const [ticketCount, setTicketCount] = useState(1);

  const [couponCode, setCouponCode] = useState("");
  const [discountAmount, setDiscountAmount] = useState(0);
  const [couponMessage, setCouponMessage] = useState<string | null>(null);
  const [couponLoading, setCouponLoading] = useState(false);

  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const submitInFlightRef = useRef(false);
  const [confirmedBooking, setConfirmedBooking] = useState<{
    reference: string;
    qr_token: string;
    amount: number;
    slotLabel: string;
  } | null>(null);

  const fetchActivity = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setLoadError(null);
    setNotFound(false);

    try {
      const data = await apiRequest<ActivityDetailData>(`/activities/${slug}`);
      setActivity(data);

      const dates = Array.from(
        new Set((data.slots || []).map((s) => s.slot_date).filter(Boolean))
      ).sort();
      setSelectedSlotDate(dates[0] || "");
    } catch (err: any) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setLoadError(err?.message || "Failed to load activity details.");
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchActivity();
  }, [fetchActivity]);

  const sortedDates = useMemo(() => {
    if (!activity?.slots) return [];
    return Array.from(
      new Set(activity.slots.map((s) => s.slot_date).filter(Boolean))
    ).sort();
  }, [activity]);

  const sortedVisibleSlots = useMemo(() => {
    if (!activity?.slots) return [];
    return [...activity.slots]
      .filter((s) => !selectedSlotDate || s.slot_date === selectedSlotDate)
      .sort((a, b) => {
        if (a.slot_date !== b.slot_date) {
          return a.slot_date.localeCompare(b.slot_date);
        }
        return a.start_time.localeCompare(b.start_time);
      });
  }, [activity, selectedSlotDate]);

  const handleSelectSlot = (slot: ActivitySlotItem) => {
    if (!slot.is_available || slot.available_spots <= 0) return;
    setSelectedSlot(slot);
    setTicketCount((prev) => Math.max(1, Math.min(prev, slot.available_spots)));
    setBookingError(null);
  };

  const effectiveBookingType =
    activity?.category?.toUpperCase() === "SPORTS" ? "SPORTS" : "ACTIVITY";

  const unitPrice = Number(selectedSlot?.price ?? activity?.base_price ?? 0);
  const subtotalPrice = selectedSlot ? unitPrice * ticketCount : 0;
  const { finalPayable } = computeBookingTotals(subtotalPrice, discountAmount);

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    setCouponLoading(true);
    try {
      const res = await apiRequest<{
        valid: boolean;
        discount_amount: number;
        message: string;
      }>("/bookings/apply-coupon", {
        method: "POST",
        body: JSON.stringify({
          code: couponCode.trim(),
          order_amount: subtotalPrice,
          booking_type: effectiveBookingType,
        }),
      });
      if (res.valid) {
        setDiscountAmount(res.discount_amount);
        setCouponMessage(res.message);
      } else {
        setDiscountAmount(0);
        setCouponMessage(res.message);
      }
    } catch (err: any) {
      setDiscountAmount(0);
      setCouponMessage(err?.message || "Failed to apply promo code.");
    } finally {
      setCouponLoading(false);
    }
  };

  const handleCheckoutAndPay = async () => {
    if (!activity || !selectedSlot) return;
    if (!user) {
      openAuthModal("login");
      return;
    }
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;

    setBookingLoading(true);
    setBookingError(null);

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `act_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

      const bookingRes = await apiRequest<{
        id: number;
        booking_reference: string;
        status: string;
        final_payable: number;
        qr_code_token?: string | null;
      }>("/bookings/", {
        method: "POST",
        body: JSON.stringify({
          booking_type: effectiveBookingType,
          items: [
            {
              item_type: "SLOT",
              item_id: selectedSlot.id,
              name: `${activity.title} (${selectedSlot.start_time?.slice(0, 5)})`,
              quantity: ticketCount,
              unit_price: unitPrice,
              details: {
                activity_id: activity.id,
                activity_title: activity.title,
                slot_time: selectedSlot.start_time,
                slot_date: selectedSlot.slot_date,
                venue_name: activity.venue_name,
              },
            },
          ],
          coupon_code: discountAmount > 0 ? couponCode.trim() : null,
          idempotency_key: idempotencyKey,
        }),
      });

      const checkoutResult = await completeRazorpayCheckoutForBooking({
        booking: bookingRes,
        description: `${activity.title} (${selectedSlot.start_time?.slice(0, 5)})`,
        idempotencyKey,
        prefill: {
          name: user.full_name,
          email: user.email,
          contact: user.phone,
        },
      });

      if (checkoutResult.status === "confirmed") {
        setConfirmedBooking({
          reference: checkoutResult.reference,
          qr_token: checkoutResult.qr_token,
          amount: checkoutResult.amount,
          slotLabel: `${selectedSlot.start_time?.slice(0, 5)} - ${selectedSlot.end_time?.slice(0, 5)}`,
        });
      } else {
        setBookingError(checkoutResult.message);
        await fetchActivity();
      }
    } catch (err: any) {
      setBookingError(err?.message || "Failed to complete slot booking.");
    } finally {
      submitInFlightRef.current = false;
      setBookingLoading(false);
    }
  };

  if (loading) {
    return (
      <DetailPageState
        mode="loading"
        backHref="/activities"
        backLabel="Back to Activities"
        entityLabel="activity"
      />
    );
  }

  if (notFound || !activity) {
    return (
      <DetailPageState
        mode={loadError ? "error" : "not-found"}
        backHref="/activities"
        backLabel="Back to Activities"
        entityLabel="activity"
        errorMessage={loadError}
        onRetry={fetchActivity}
      />
    );
  }

  const isSports = activity.category?.toUpperCase() === "SPORTS";
  const maxPlayers = selectedSlot?.available_spots ?? 1;

  return (
    <div className="min-h-screen bg-canvas text-primary pb-24 md:pb-20">
      <DetailPageHero
        backHref={isSports && activity.venue_id ? `/sports/${activity.venue_id}` : "/activities"}
        backLabel={
          isSports && activity.venue_id
            ? "Back to Venue"
            : "All Activities"
        }
        verticalLabel={isSports ? "Sports" : "Activities"}
        title={activity.title}
        subtitle={
          activity.venue_id && activity.venue_name ? (
            <Link
              href={`/sports/${activity.venue_id}`}
              className="inline-flex items-center gap-1.5 text-brand-400 hover:text-brand-300 font-semibold transition-colors"
            >
              <span>{activity.venue_name}</span>
              <span className="text-muted">• View Venue Details</span>
            </Link>
          ) : (
            activity.venue_name || activity.location_name || undefined
          )
        }
        heroImages={[activity.image_url]}
        fallbackCategory={isSports ? "sports" : "activities"}
        badges={
          <>
            <Badge variant="brand" size="md">
              {activity.category.replace(/_/g, " ")}
            </Badge>
            <Badge variant="default" size="md">
              Min Age {activity.min_age}+
            </Badge>
          </>
        }
        metadata={[
          {
            id: "location",
            icon: <MapPin className="w-4 h-4 text-brand-400" aria-hidden="true" />,
            label: activity.location_name || activity.venue_name || "Hyderabad",
          },
          {
            id: "duration",
            icon: <Clock className="w-4 h-4 text-champagne" aria-hidden="true" />,
            label: `${activity.duration_minutes} mins session`,
          },
          {
            id: "age",
            icon: <Users className="w-4 h-4 text-emerald-400" aria-hidden="true" />,
            label: `Age ${activity.min_age}+`,
          },
        ]}
        rightCallout={
          <div className="px-4 py-3 rounded-2xl bg-surface/90 border border-strong backdrop-blur-md text-left md:text-right">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted block">
              Slot Rate
            </span>
            <span className="font-display text-2xl font-extrabold text-primary tabular-nums-lining">
              ₹{Math.round(activity.base_price || 0).toLocaleString("en-IN")}
            </span>
            <span className="text-xs text-secondary block">per spot / hour</span>
          </div>
        }
      />

      {/* MAIN CONTENT */}
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 mt-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10">
          {/* Left Column: Overview & Slot Selector */}
          <div className="lg:col-span-2 space-y-8">
            <section className="p-5 sm:p-6 bg-surface border border-subtle rounded-2xl shadow-surface space-y-3">
              <h2 className="font-display font-bold text-lg text-primary flex items-center gap-2">
                <Compass className="w-5 h-5 text-brand-400 shrink-0" aria-hidden="true" />
                <span>Experience Overview</span>
              </h2>
              {activity.description ? (
                <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                  {activity.description}
                </p>
              ) : (
                <p className="text-xs sm:text-sm text-secondary">
                  Book your preferred time slot for instant QR check-in at the venue.
                </p>
              )}
            </section>

            {/* Time Slot Selector */}
            <section id="time-slots" className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-subtle">
                <h3 className="font-display font-bold text-lg sm:text-xl text-primary flex items-center gap-2.5">
                  <Calendar className="w-5 h-5 text-brand-500 shrink-0" aria-hidden="true" />
                  <span>Select Time Slot</span>
                </h3>
                <span className="text-xs text-secondary">
                  {sortedDates.length === 1 && sortedDates[0]
                    ? formatSlotDateLabel(sortedDates[0])
                    : "Available Schedule"}
                </span>
              </div>

              {/* Date Tabs when multiple dates exist */}
              {sortedDates.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                  {sortedDates.map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => {
                        setSelectedSlotDate(d);
                        setSelectedSlot(null);
                      }}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
                        selectedSlotDate === d
                          ? "bg-brand-500 border-brand-500 text-white shadow-brand-sm"
                          : "bg-surface border-subtle text-secondary hover:text-primary"
                      )}
                    >
                      {formatSlotDateLabel(d)}
                    </button>
                  ))}
                </div>
              ) : null}

              {sortedVisibleSlots.length === 0 ? (
                <div className="p-6 rounded-2xl bg-surface border border-subtle text-xs sm:text-sm text-secondary">
                  No open booking slots found for this date.
                </div>
              ) : (
                <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-3 gap-3">
                  {sortedVisibleSlots.map((slot) => {
                    const isSelected = selectedSlot?.id === slot.id;
                    const disabled = !slot.is_available || slot.available_spots <= 0;
                    const priceNumber = Number(slot.price);

                    return (
                      <button
                        key={slot.id}
                        type="button"
                        disabled={disabled}
                        aria-pressed={isSelected}
                        onClick={() => handleSelectSlot(slot)}
                        className={cn(
                          "p-4 rounded-2xl border text-left transition-all flex flex-col justify-between gap-2.5",
                          disabled
                            ? "bg-canvas/60 border-subtle opacity-45 cursor-not-allowed"
                            : isSelected
                            ? "bg-brand-500/15 border-brand-500 text-primary shadow-brand-sm"
                            : "bg-surface border-subtle hover:border-strong hover:bg-surface-2/70 text-primary"
                        )}
                      >
                        <div className="font-mono font-bold text-sm tabular-nums-lining">
                          {slot.start_time?.slice(0, 5)} - {slot.end_time?.slice(0, 5)}
                        </div>

                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="font-mono font-bold text-primary tabular-nums-lining">
                            ₹{priceNumber}
                          </span>
                          <span
                            className={cn(
                              "font-mono text-[11px] font-semibold",
                              disabled
                                ? "text-red-400"
                                : slot.available_spots <= 2
                                ? "text-amber-400"
                                : "text-emerald-400"
                            )}
                          >
                            {disabled ? "Sold Out" : `${slot.available_spots} left`}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Sticky Booking Summary & Checkout Card */}
          <aside id="activity-checkout" className="space-y-5">
            <div className="sticky top-24 p-6 bg-surface border border-subtle rounded-2xl shadow-elevated space-y-5">
              <div className="border-b border-subtle pb-4">
                <h3 className="font-display font-extrabold text-lg sm:text-xl text-primary">
                  Booking Details
                </h3>
                <p className="text-xs text-secondary mt-1">
                  Verified slot reservation with instant gate QR pass
                </p>
              </div>

              {confirmedBooking ? (
                <BookingSuccessState
                  headingTag="h4"
                  title="Booking Confirmed!"
                  subtitle="Your spot is locked in. Show your digital QR pass at check-in."
                  rows={[
                    {
                      label: "Booking Code",
                      value: confirmedBooking.reference,
                      accent: "brand",
                    },
                    { label: "Time Slot", value: confirmedBooking.slotLabel },
                    { label: "Spots Reserved", value: `${ticketCount}` },
                    {
                      label: "Total Paid",
                      value: `₹${confirmedBooking.amount.toFixed(2)}`,
                      accent: "success",
                    },
                  ]}
                  primaryCtaLabel="View Confirmation Pass"
                  onPrimaryClick={() =>
                    router.push(
                      `/bookings/${confirmedBooking.reference}/confirmation`
                    )
                  }
                  onSecondaryClick={() => router.push("/bookings")}
                />
              ) : (
                <div className="space-y-4">
                  {/* Player / Spot Quantity Capped to Available Spots */}
                  {selectedSlot ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-[11px] uppercase tracking-wider text-secondary font-medium">
                          Players / Persons
                        </span>
                        <span className="text-[11px] text-emerald-400 font-medium">
                          Max {maxPlayers} available
                        </span>
                      </div>

                      <div className="grid grid-cols-4 gap-2">
                        {[1, 2, 4, 6].map((num) => {
                          const overCapacity = num > maxPlayers;
                          const isActive = ticketCount === num;
                          return (
                            <button
                              key={num}
                              type="button"
                              disabled={overCapacity}
                              title={
                                overCapacity
                                  ? `Only ${maxPlayers} spots left in this slot`
                                  : undefined
                              }
                              onClick={() => setTicketCount(num)}
                              className={cn(
                                "py-2 rounded-xl text-xs font-mono font-bold border transition-colors",
                                overCapacity
                                  ? "bg-canvas/60 border-subtle text-muted opacity-40 cursor-not-allowed"
                                  : isActive
                                  ? "bg-brand-500 text-white border-brand-500 shadow-brand-sm"
                                  : "bg-surface-2 border-subtle text-secondary hover:text-primary hover:border-strong"
                              )}
                            >
                              {num}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  <CheckoutSummaryCard
                    subtotal={subtotalPrice}
                    discountAmount={discountAmount}
                    itemsLabel={
                      selectedSlot
                        ? `Slot (${selectedSlot.start_time?.slice(0, 5)} × ${ticketCount}):`
                        : "Selected Slot:"
                    }
                    totalLabel="Total Payable:"
                    hasSelection={Boolean(selectedSlot)}
                    emptySelectionMessage="Please select an available time slot from the schedule."
                    couponCode={couponCode}
                    onCouponCodeChange={setCouponCode}
                    onApplyCoupon={handleApplyCoupon}
                    onClearCoupon={() => {
                      setCouponCode("");
                      setDiscountAmount(0);
                      setCouponMessage(null);
                    }}
                    couponMessage={couponMessage}
                    couponLoading={couponLoading}
                    bookingError={bookingError}
                    isSubmitting={bookingLoading}
                    onSubmit={handleCheckoutAndPay}
                  />
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>

      {/* Mobile Sticky Bottom Slot Checkout Notice */}
      {selectedSlot && !confirmedBooking ? (
        <div className="md:hidden fixed bottom-16 inset-x-0 z-30 bg-surface/95 backdrop-blur-md border-t border-subtle px-4 py-2.5 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-xs font-bold text-primary tabular-nums-lining">
              ₹{finalPayable.toFixed(2)} total
            </div>
            <div className="text-[11px] text-secondary truncate">
              {selectedSlot.start_time?.slice(0, 5)} • {ticketCount}{" "}
              {ticketCount === 1 ? "spot" : "spots"} + GST
            </div>
          </div>
          <a
            href="#activity-checkout"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm shrink-0"
          >
            Continue to Pay
          </a>
        </div>
      ) : null}
    </div>
  );
}
