"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  CalendarDays,
  Clock,
  MapPin,
  Minus,
  Plus,
  Sparkles,
  Ticket,
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

interface EventTicketTier {
  id: number;
  event_id: number;
  name: string;
  description?: string | null;
  price: number;
  total_quantity: number;
  available_quantity: number;
  max_per_booking: number;
}

interface EventDetailData {
  id: number;
  title: string;
  slug: string;
  category: string;
  description?: string | null;
  artist_names?: string | null;
  venue_name: string;
  venue_address: string;
  start_datetime: string;
  end_datetime: string;
  banner_url?: string | null;
  is_featured: boolean;
  is_active: boolean;
  location_name?: string | null;
  lowest_price?: number | null;
  ticket_types: EventTicketTier[];
}

export default function EventDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const router = useRouter();
  const { user, openAuthModal } = useAuth();

  const [event, setEvent] = useState<EventDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // Selected tickets: ticket_type_id -> quantity
  const [selectedTickets, setSelectedTickets] = useState<Record<number, number>>({});
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
    ticketsCount: number;
  } | null>(null);

  const fetchEvent = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setLoadError(null);
    setNotFound(false);

    try {
      const data = await apiRequest<EventDetailData>(`/events/${slug}`);
      setEvent(data);
    } catch (err: any) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setLoadError(err?.message || "Failed to load event details.");
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchEvent();
  }, [fetchEvent]);

  const updateQuantity = (ticketId: number, delta: number, maxAllowed: number) => {
    setSelectedTickets((prev) => {
      const current = prev[ticketId] || 0;
      const updated = Math.max(0, Math.min(maxAllowed, current + delta));
      return { ...prev, [ticketId]: updated };
    });
  };

  const ticketTypes = useMemo(() => event?.ticket_types || [], [event]);

  const totalTickets = useMemo(
    () => Object.values(selectedTickets).reduce((sum, qty) => sum + qty, 0),
    [selectedTickets]
  );

  const subtotalPrice = useMemo(
    () =>
      ticketTypes.reduce((sum, tt) => {
        const qty = selectedTickets[tt.id] || 0;
        return sum + qty * Number(tt.price || 0);
      }, 0),
    [ticketTypes, selectedTickets]
  );

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
          booking_type: "EVENT",
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
      setCouponMessage(err?.message || "Failed to validate coupon code.");
    } finally {
      setCouponLoading(false);
    }
  };

  const handleCheckoutAndPay = async () => {
    if (!event || totalTickets === 0) return;
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
          : `evt_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

      const items = ticketTypes
        .filter((tt) => (selectedTickets[tt.id] || 0) > 0)
        .map((tt) => ({
          item_type: "TICKET",
          item_id: tt.id,
          name: `${tt.name} Pass`,
          quantity: selectedTickets[tt.id],
          unit_price: tt.price,
          details: {
            event_id: event.id,
            event_title: event.title,
            venue_name: event.venue_name,
            tier_name: tt.name,
          },
        }));

      // 1. Create server-authoritative booking hold
      const bookingRes = await apiRequest<{
        id: number;
        booking_reference: string;
        status: string;
        final_payable: number;
        qr_code_token?: string | null;
      }>("/bookings/", {
        method: "POST",
        body: JSON.stringify({
          booking_type: "EVENT",
          items,
          coupon_code: discountAmount > 0 ? couponCode.trim() : null,
          idempotency_key: idempotencyKey,
        }),
      });

      // 2. Complete payment via official Razorpay Checkout.js & server signature verification
      const checkoutResult = await completeRazorpayCheckoutForBooking({
        booking: bookingRes,
        description: `${event.title} • ${event.venue_name}`,
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
          ticketsCount: totalTickets,
        });
      } else {
        setBookingError(checkoutResult.message);
        await fetchEvent();
      }
    } catch (err: any) {
      setBookingError(err?.message || "Failed to process booking.");
    } finally {
      submitInFlightRef.current = false;
      setBookingLoading(false);
    }
  };

  if (loading) {
    return (
      <DetailPageState
        mode="loading"
        backHref="/events"
        backLabel="Back to Events"
        entityLabel="event"
      />
    );
  }

  if (notFound || !event) {
    return (
      <DetailPageState
        mode={loadError ? "error" : "not-found"}
        backHref="/events"
        backLabel="Back to Events"
        entityLabel="event"
        errorMessage={loadError}
        onRetry={fetchEvent}
      />
    );
  }

  const startDate = new Date(event.start_datetime);
  const formattedDate = Number.isNaN(startDate.getTime())
    ? ""
    : startDate.toLocaleDateString("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      });
  const formattedTime = Number.isNaN(startDate.getTime())
    ? ""
    : startDate.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });

  return (
    <div className="min-h-screen bg-canvas text-primary pb-24 md:pb-20">
      <DetailPageHero
        backHref="/events"
        backLabel="All Events"
        verticalLabel="Events"
        title={event.title}
        subtitle={
          event.artist_names ? (
            <span>
              Featuring <span className="font-semibold text-primary">{event.artist_names}</span>
            </span>
          ) : null
        }
        heroImages={[event.banner_url]}
        fallbackCategory="events"
        badges={
          <>
            <Badge variant="brand" size="md">
              {event.category}
            </Badge>
            {event.is_featured ? (
              <Badge
                variant="gold"
                size="md"
                icon={<Sparkles className="w-3.5 h-3.5" />}
              >
                Featured
              </Badge>
            ) : null}
          </>
        }
        metadata={[
          ...(formattedDate
            ? [
                {
                  id: "date",
                  icon: <CalendarDays className="w-4 h-4 text-brand-400" aria-hidden="true" />,
                  label: formattedDate,
                },
              ]
            : []),
          ...(formattedTime
            ? [
                {
                  id: "time",
                  icon: <Clock className="w-4 h-4 text-champagne" aria-hidden="true" />,
                  label: `${formattedTime} onwards`,
                },
              ]
            : []),
          {
            id: "venue",
            icon: <MapPin className="w-4 h-4 text-emerald-400" aria-hidden="true" />,
            label: `${event.venue_name}${
              event.location_name ? ` • ${event.location_name}` : ""
            }`,
          },
        ]}
        rightCallout={
          typeof event.lowest_price === "number" ? (
            <div className="px-4 py-3 rounded-2xl bg-surface/90 border border-strong backdrop-blur-md text-left md:text-right">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted block">
                Passes From
              </span>
              <span className="font-display text-2xl font-extrabold text-primary tabular-nums-lining">
                {event.lowest_price > 0
                  ? `₹${Math.round(event.lowest_price).toLocaleString("en-IN")}`
                  : "Free Entry"}
              </span>
            </div>
          ) : null
        }
      />

      {/* TICKET SELECTION & CHECKOUT */}
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 mt-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10">
          {/* Left Column: Event Details & Ticket Tiers */}
          <div className="lg:col-span-2 space-y-8">
            <section className="p-5 sm:p-6 bg-surface border border-subtle rounded-2xl shadow-surface space-y-3">
              <h2 className="font-display font-bold text-lg text-primary">
                Event Experience Details
              </h2>
              {event.description ? (
                <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                  {event.description}
                </p>
              ) : null}
              <div className="pt-2 border-t border-subtle text-xs text-secondary flex items-start gap-2">
                <MapPin className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" aria-hidden="true" />
                <span>
                  <span className="font-semibold text-primary">{event.venue_name}</span>
                  {event.venue_address ? ` — ${event.venue_address}` : ""}
                </span>
              </div>
            </section>

            {/* Select Passes */}
            <section id="ticket-passes" className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-subtle">
                <h3 className="font-display font-bold text-lg sm:text-xl text-primary flex items-center gap-2.5">
                  <Ticket className="w-5 h-5 text-brand-500 shrink-0" aria-hidden="true" />
                  <span>Select Ticket Passes</span>
                </h3>
                <span className="text-xs text-secondary">Instant M-Ticket</span>
              </div>

              {ticketTypes.length === 0 ? (
                <div className="p-6 rounded-2xl bg-surface border border-subtle text-xs sm:text-sm text-secondary">
                  Ticket passes are not currently open for online booking.
                </div>
              ) : (
                <div className="space-y-3.5">
                  {ticketTypes.map((tt) => {
                    const qty = selectedTickets[tt.id] || 0;
                    const isSoldOut = tt.available_quantity <= 0;
                    const isLowStock =
                      !isSoldOut && tt.available_quantity <= 15;
                    const maxSelectable = Math.min(
                      tt.max_per_booking || 10,
                      tt.available_quantity
                    );

                    return (
                      <div
                        key={tt.id}
                        className={cn(
                          "p-5 bg-surface border rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors shadow-surface",
                          qty > 0
                            ? "border-brand-500/45 bg-surface-2/40"
                            : "border-subtle hover:border-strong"
                        )}
                      >
                        <div className="space-y-1.5 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-display font-bold text-base sm:text-lg text-primary">
                              {tt.name}
                            </span>

                            {tt.name.toUpperCase().includes("VIP") ? (
                              <Badge variant="gold" size="sm">
                                VIP Access
                              </Badge>
                            ) : null}

                            {isLowStock ? (
                              <Badge variant="warning" size="sm">
                                Only {tt.available_quantity} left
                              </Badge>
                            ) : null}
                          </div>

                          {tt.description ? (
                            <p className="text-xs text-secondary leading-relaxed">
                              {tt.description}
                            </p>
                          ) : null}

                          <div className="font-mono text-base font-bold text-primary pt-0.5 tabular-nums-lining">
                            ₹{Number(tt.price).toFixed(0)}
                          </div>
                        </div>

                        <div className="shrink-0 self-end sm:self-center">
                          {isSoldOut ? (
                            <Badge variant="danger" size="md">
                              Sold Out
                            </Badge>
                          ) : (
                            <div className="inline-flex items-center gap-3 bg-surface-2 border border-subtle rounded-xl p-1">
                              <button
                                type="button"
                                aria-label={`Decrease quantity for ${tt.name}`}
                                onClick={() =>
                                  updateQuantity(tt.id, -1, maxSelectable)
                                }
                                disabled={qty <= 0}
                                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-3 text-primary disabled:opacity-30 transition-colors"
                              >
                                <Minus className="w-3.5 h-3.5" />
                              </button>
                              <span className="w-6 text-center font-mono text-sm font-bold text-primary tabular-nums-lining">
                                {qty}
                              </span>
                              <button
                                type="button"
                                aria-label={`Increase quantity for ${tt.name}`}
                                onClick={() =>
                                  updateQuantity(tt.id, 1, maxSelectable)
                                }
                                disabled={qty >= maxSelectable}
                                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 disabled:opacity-30 transition-colors"
                              >
                                <Plus className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Sticky Order Summary Card */}
          <aside id="event-checkout" className="space-y-5">
            <div className="sticky top-24 p-6 bg-surface border border-subtle rounded-2xl shadow-elevated space-y-5">
              <div className="border-b border-subtle pb-4">
                <h3 className="font-display font-extrabold text-lg sm:text-xl text-primary">
                  Order Summary
                </h3>
                <p className="text-xs text-secondary mt-1">
                  Instant M-Ticket with gate scanner QR pass
                </p>
              </div>

              {confirmedBooking ? (
                <BookingSuccessState
                  headingTag="h4"
                  title="Tickets Confirmed!"
                  subtitle="Your event passes are ready. Show your digital QR code at the venue gate."
                  rows={[
                    {
                      label: "Booking Code",
                      value: confirmedBooking.reference,
                      accent: "brand",
                    },
                    {
                      label: "Passes",
                      value: `${confirmedBooking.ticketsCount} ${
                        confirmedBooking.ticketsCount === 1 ? "ticket" : "tickets"
                      }`,
                    },
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
                <CheckoutSummaryCard
                  subtotal={subtotalPrice}
                  discountAmount={discountAmount}
                  itemsLabel={`Tickets (${totalTickets}):`}
                  totalLabel="Total Payable:"
                  hasSelection={totalTickets > 0}
                  emptySelectionMessage="Add one or more passes on the left to continue to checkout."
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
              )}
            </div>
          </aside>
        </div>
      </div>

      {/* Mobile Sticky Bottom Checkout Summary */}
      {totalTickets > 0 && !confirmedBooking ? (
        <div className="md:hidden fixed bottom-16 inset-x-0 z-30 bg-surface/95 backdrop-blur-md border-t border-subtle px-4 py-2.5 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-xs font-bold text-primary tabular-nums-lining">
              ₹{finalPayable.toFixed(2)} total
            </div>
            <div className="text-[11px] text-secondary">
              {totalTickets} {totalTickets === 1 ? "pass" : "passes"} selected + GST
            </div>
          </div>
          <a
            href="#event-checkout"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm shrink-0"
          >
            Review & Pay
          </a>
        </div>
      ) : null}
    </div>
  );
}
