"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Clock,
  ExternalLink,
  Film,
  MapPin,
  Navigation,
  ShieldCheck,
  Star,
  Ticket,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useLocation } from "@/context/LocationContext";
import { apiRequest } from "@/lib/api";
import { computeBookingTotals } from "@/lib/pricing";
import { completeRazorpayCheckoutForBooking } from "@/lib/razorpay";
import { DetailPageHero } from "@/components/booking/DetailPageHero";
import { DetailPageState } from "@/components/booking/DetailPageState";
import {
  SeatMapGrid,
  ShowSeatItem,
} from "@/components/booking/SeatMapGrid";
import { CheckoutSummaryCard } from "@/components/booking/CheckoutSummaryCard";
import { BookingSuccessState } from "@/components/booking/BookingSuccessState";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/cn";

interface MovieShowItem {
  id: number;
  movie_id: number;
  screen_id: number;
  cinema_id: number;
  cinema_name: string;
  screen_name: string;
  screen_type: string;
  show_date: string;
  start_time: string;
  end_time: string;
  price_multiplier: number;
  status: string;
  address: string;
  location_name?: string | null;
  locality_id?: number | null;
  distance_km?: number | null;
}

interface MovieDetailData {
  id: number;
  title: string;
  slug: string;
  description?: string | null;
  duration_minutes: number;
  language: string;
  genre: string;
  censor_rating: string;
  release_date: string;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_url?: string | null;
  rating: number;
  vote_count: number;
  is_active: boolean;
  shows: MovieShowItem[];
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export default function MovieDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const router = useRouter();
  const { user, openAuthModal } = useAuth();
  const { gpsCoordinates, selectedCity } = useLocation();

  const [movie, setMovie] = useState<MovieDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // Show filters
  const [selectedShowDate, setSelectedShowDate] = useState<string>("");
  const [selectedFormat, setSelectedFormat] = useState<string>("");

  // Seat Selection Modal State
  const [selectedShow, setSelectedShow] = useState<MovieShowItem | null>(null);
  const [seats, setSeats] = useState<ShowSeatItem[]>([]);
  const [seatsLoading, setSeatsLoading] = useState(false);
  const [selectedSeatIds, setSelectedSeatIds] = useState<number[]>([]);
  const [seatLimitWarning, setSeatLimitWarning] = useState<string | null>(null);
  const [isSeatModalOpen, setIsSeatModalOpen] = useState(false);
  const [lockingLoading, setLockingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const submitInFlightRef = useRef(false);

  // Checkout State
  const [couponCode, setCouponCode] = useState("");
  const [discountAmount, setDiscountAmount] = useState(0);
  const [couponMessage, setCouponMessage] = useState<string | null>(null);
  const [couponLoading, setCouponLoading] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState<{
    reference: string;
    qr_token: string;
    amount: number;
    seats: string;
  } | null>(null);

  const fetchMovie = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setLoadError(null);
    setNotFound(false);

    try {
      const qs = gpsCoordinates
        ? `?lat=${gpsCoordinates.lat}&lon=${gpsCoordinates.lon}`
        : "";
      const data = await apiRequest<MovieDetailData>(`/movies/${slug}${qs}`);
      setMovie(data);

      const dates = Array.from(
        new Set((data.shows || []).map((s) => s.show_date).filter(Boolean))
      ).sort();
      setSelectedShowDate(dates[0] || "");
      setSelectedFormat("");
    } catch (err: any) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setLoadError(err?.message || "Failed to load movie details.");
      }
    } finally {
      setLoading(false);
    }
  }, [slug, gpsCoordinates]);

  useEffect(() => {
    fetchMovie();
  }, [fetchMovie]);

  const availableDates = useMemo(() => {
    if (!movie?.shows) return [];
    return Array.from(
      new Set(movie.shows.map((s) => s.show_date).filter(Boolean))
    ).sort();
  }, [movie]);

  const availableFormats = useMemo(() => {
    if (!movie?.shows) return [];
    return Array.from(
      new Set(movie.shows.map((s) => s.screen_type).filter(Boolean))
    );
  }, [movie]);

  const cinemaGroups = useMemo(() => {
    if (!movie?.shows) return [];
    const filtered = movie.shows.filter((s) => {
      if (selectedShowDate && s.show_date !== selectedShowDate) return false;
      if (selectedFormat && s.screen_type !== selectedFormat) return false;
      return true;
    });

    const groups = new Map<
      number,
      {
        cinema_id: number;
        cinema_name: string;
        address: string;
        location_name?: string | null;
        distance_km?: number | null;
        shows: MovieShowItem[];
      }
    >();

    for (const show of filtered) {
      const existing = groups.get(show.cinema_id);
      if (existing) {
        existing.shows.push(show);
      } else {
        groups.set(show.cinema_id, {
          cinema_id: show.cinema_id,
          cinema_name: show.cinema_name,
          address: show.address,
          location_name: show.location_name,
          distance_km: show.distance_km,
          shows: [show],
        });
      }
    }

    const result = Array.from(groups.values());
    for (const g of result) {
      g.shows.sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return result;
  }, [movie, selectedShowDate, selectedFormat]);

  const handleOpenShowSeats = async (show: MovieShowItem) => {
    if (show.status === "HOUSEFULL") return;
    if (!user) {
      openAuthModal("login");
      return;
    }

    setSelectedShow(show);
    setSelectedSeatIds([]);
    setSeatLimitWarning(null);
    setBookingError(null);
    setCouponCode("");
    setDiscountAmount(0);
    setCouponMessage(null);
    setConfirmedBooking(null);
    setSeats([]);
    setSeatsLoading(true);
    setIsSeatModalOpen(true);

    try {
      const seatsData = await apiRequest<ShowSeatItem[]>(
        `/movies/shows/${show.id}/seats`
      );
      setSeats(Array.isArray(seatsData) ? seatsData : []);
    } catch (err: any) {
      setBookingError(err?.message || "Failed to load seats for this show.");
    } finally {
      setSeatsLoading(false);
    }
  };

  const toggleSeatSelection = (seat: ShowSeatItem) => {
    if (seat.is_booked || seat.is_locked) return;
    setSeatLimitWarning(null);

    if (selectedSeatIds.includes(seat.id)) {
      setSelectedSeatIds((prev) => prev.filter((id) => id !== seat.id));
    } else {
      if (selectedSeatIds.length >= 6) {
        setSeatLimitWarning("Maximum 6 seats can be selected per booking.");
        return;
      }
      setSelectedSeatIds((prev) => [...prev, seat.id]);
    }
  };

  const selectedSeatsList = useMemo(
    () => seats.filter((s) => selectedSeatIds.includes(s.id)),
    [seats, selectedSeatIds]
  );

  // Note: /movies/shows/{show_id}/seats already applies show.price_multiplier to seat.base_price
  const subtotalPrice = useMemo(
    () => selectedSeatsList.reduce((sum, s) => sum + Number(s.base_price || 0), 0),
    [selectedSeatsList]
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
          booking_type: "MOVIE",
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
      setCouponMessage(err?.message || "Failed to validate promo code.");
    } finally {
      setCouponLoading(false);
    }
  };

  const handleLockSeatsAndPay = async () => {
    if (!movie || !selectedShow || selectedSeatIds.length === 0) return;
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;
    setLockingLoading(true);
    setBookingError(null);

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `mov_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

      // 1. Pessimistic lock on backend Redis + DB
      const lockRes = await apiRequest<{ lock_token: string }>(
        `/movies/shows/${selectedShow.id}/lock-seats`,
        {
          method: "POST",
          body: JSON.stringify({
            show_id: selectedShow.id,
            seat_ids: selectedSeatIds,
          }),
        }
      );

      // 2. Create server-authoritative booking record
      const bookingItems = selectedSeatsList.map((s) => ({
        item_type: "SEAT",
        item_id: s.id,
        name: `${s.row_code}${s.seat_number} (${s.tier})`,
        quantity: 1,
        unit_price: s.base_price,
        details: {
          show_id: selectedShow.id,
          movie_title: movie.title,
          cinema_name: selectedShow.cinema_name,
          screen_name: selectedShow.screen_name,
          row_code: s.row_code,
          seat_number: s.seat_number,
          tier: s.tier,
        },
      }));

      const bookingRes = await apiRequest<{
        id: number;
        booking_reference: string;
        status: string;
        final_payable: number;
        qr_code_token?: string | null;
      }>("/bookings/", {
        method: "POST",
        body: JSON.stringify({
          booking_type: "MOVIE",
          items: bookingItems,
          coupon_code: discountAmount > 0 ? couponCode.trim() : null,
          lock_token: lockRes.lock_token,
          idempotency_key: idempotencyKey,
        }),
      });

      // 3. Complete payment via official Razorpay Checkout.js & server signature verification
      const checkoutResult = await completeRazorpayCheckoutForBooking({
        booking: bookingRes,
        description: `${movie.title} • ${selectedShow.cinema_name}`,
        idempotencyKey,
        prefill: user
          ? {
              name: user.full_name,
              email: user.email,
              contact: user.phone,
            }
          : undefined,
      });

      if (checkoutResult.status === "confirmed") {
        setConfirmedBooking({
          reference: checkoutResult.reference,
          qr_token: checkoutResult.qr_token,
          amount: checkoutResult.amount,
          seats: selectedSeatsList.map((s) => `${s.row_code}${s.seat_number}`).join(", "),
        });
      } else {
        setBookingError(checkoutResult.message);
        const refreshedSeats = await apiRequest<ShowSeatItem[]>(
          `/movies/shows/${selectedShow.id}/seats`
        ).catch(() => null);
        if (Array.isArray(refreshedSeats)) {
          setSeats(refreshedSeats);
        }
      }
    } catch (err: any) {
      setBookingError(err?.message || "Failed to complete booking.");
    } finally {
      submitInFlightRef.current = false;
      setLockingLoading(false);
    }
  };

  if (loading) {
    return (
      <DetailPageState
        mode="loading"
        backHref="/movies"
        backLabel="Back to Movies"
        entityLabel="movie"
      />
    );
  }

  if (notFound || !movie) {
    return (
      <DetailPageState
        mode={loadError ? "error" : "not-found"}
        backHref="/movies"
        backLabel="Back to Movies"
        entityLabel="movie"
        errorMessage={loadError}
        onRetry={fetchMovie}
      />
    );
  }

  return (
    <div className="min-h-screen bg-canvas text-primary pb-20">
      <DetailPageHero
        backHref="/movies"
        backLabel="All Movies"
        verticalLabel="Movies"
        title={movie.title}
        subtitle={movie.genre}
        heroImages={[movie.backdrop_url, movie.poster_url]}
        posterSrc={movie.poster_url || movie.backdrop_url}
        fallbackCategory="movies"
        blurBackdrop
        badges={
          <>
            <Badge variant="brand" size="md">
              {movie.censor_rating}
            </Badge>
            <Badge variant="default" size="md">
              {movie.language}
            </Badge>
            {movie.rating > 0 ? (
              <Badge
                variant="gold"
                size="md"
                icon={<Star className="w-3.5 h-3.5 fill-champagne text-champagne" />}
              >
                {movie.rating.toFixed(1)} / 5.0
                {movie.vote_count > 0
                  ? ` (${movie.vote_count.toLocaleString("en-IN")})`
                  : ""}
              </Badge>
            ) : null}
          </>
        }
        metadata={[
          {
            id: "duration",
            icon: <Clock className="w-4 h-4 text-brand-400" aria-hidden="true" />,
            label: `${movie.duration_minutes} mins`,
          },
          {
            id: "release",
            icon: <Calendar className="w-4 h-4 text-champagne" aria-hidden="true" />,
            label: `Release ${formatDateLabel(movie.release_date)}`,
          },
          {
            id: "shows",
            icon: <Ticket className="w-4 h-4 text-emerald-400" aria-hidden="true" />,
            label: `${movie.shows?.length || 0} active ${
              movie.shows?.length === 1 ? "show" : "shows"
            }`,
          },
        ]}
        actionsSlot={
          <>
            <a
              href="#showtimes"
              className="inline-flex items-center gap-2 h-10 px-5 rounded-lg bg-brand-500 hover:bg-brand-600 text-sm font-semibold text-white shadow-brand-sm transition-colors"
            >
              <Film className="w-4 h-4" aria-hidden="true" />
              <span>Book Tickets</span>
            </a>

            {movie.trailer_url ? (
              <a
                href={movie.trailer_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-surface-2 hover:bg-surface-3 border border-strong text-sm font-semibold text-primary transition-colors"
              >
                <ExternalLink className="w-4 h-4 text-champagne" aria-hidden="true" />
                <span>Watch Trailer</span>
              </a>
            ) : null}
          </>
        }
      />

      {/* SHOWS & MOVIE INFO */}
      <div
        id="showtimes"
        className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 mt-10"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10">
          {/* Main Cinema Shows Column */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-subtle">
              <h2 className="font-display text-xl sm:text-2xl font-bold flex items-center gap-2.5 text-primary">
                <Calendar className="w-5 h-5 text-brand-500 shrink-0" aria-hidden="true" />
                <span>Cinema Shows & Timings</span>
              </h2>
              <span className="text-xs font-medium text-secondary">
                {selectedCity} Theatres
              </span>
            </div>

            {/* Date & Format Selectors (shown smoothly when applicable) */}
            {(availableDates.length > 1 || availableFormats.length > 1) && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                {availableDates.length > 1 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {availableDates.map((d) => {
                      const active = selectedShowDate === d;
                      return (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setSelectedShowDate(d)}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
                            active
                              ? "bg-brand-500 border-brand-500 text-white shadow-brand-sm"
                              : "bg-surface border-subtle text-secondary hover:text-primary"
                          )}
                        >
                          {formatDateLabel(d)}
                        </button>
                      );
                    })}
                  </div>
                ) : null}

                {availableFormats.length > 1 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setSelectedFormat("")}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors",
                        selectedFormat === ""
                          ? "bg-surface-3 border-strong text-primary"
                          : "bg-surface border-subtle text-secondary hover:text-primary"
                      )}
                    >
                      All Formats
                    </button>
                    {availableFormats.map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => setSelectedFormat(fmt)}
                        className={cn(
                          "px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors",
                          selectedFormat === fmt
                            ? "bg-brand-500/15 border-brand-500/45 text-brand-300 font-semibold"
                            : "bg-surface border-subtle text-secondary hover:text-primary"
                        )}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            )}

            {cinemaGroups.length === 0 ? (
              <div className="p-8 text-center bg-surface border border-subtle rounded-2xl text-sm text-secondary">
                No active showtimes scheduled for the selected date or format.
              </div>
            ) : (
              <div className="space-y-4">
                {cinemaGroups.map((cinema) => (
                  <div
                    key={cinema.cinema_id}
                    className="p-5 sm:p-6 bg-surface border border-subtle hover:border-strong rounded-2xl transition-colors space-y-4 shadow-surface"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="font-display font-bold text-base sm:text-lg text-primary">
                          {cinema.cinema_name}
                        </h3>
                        <p className="text-xs text-secondary flex items-start gap-1.5 mt-1">
                          <MapPin
                            className="w-3.5 h-3.5 text-brand-400 shrink-0 mt-0.5"
                            aria-hidden="true"
                          />
                          <span>{cinema.address}</span>
                        </p>
                      </div>

                      {typeof cinema.distance_km === "number" ? (
                        <Badge
                          variant="success"
                          size="sm"
                          icon={<Navigation className="w-3 h-3" />}
                        >
                          {cinema.distance_km.toFixed(1)} km
                        </Badge>
                      ) : cinema.location_name ? (
                        <Badge variant="default" size="sm">
                          {cinema.location_name}
                        </Badge>
                      ) : null}
                    </div>

                    <div className="pt-2 border-t border-subtle flex flex-wrap items-center gap-2.5">
                      {cinema.shows.map((show) => {
                        const isHousefull = show.status === "HOUSEFULL";
                        return (
                          <button
                            key={show.id}
                            type="button"
                            disabled={isHousefull}
                            onClick={() => handleOpenShowSeats(show)}
                            className={cn(
                              "px-4 py-2.5 rounded-xl border text-left transition-all flex items-center gap-2.5 group",
                              isHousefull
                                ? "bg-canvas/60 border-subtle text-muted opacity-50 cursor-not-allowed"
                                : "bg-surface-2 hover:bg-brand-500 border-subtle hover:border-brand-400 text-primary hover:shadow-brand-sm"
                            )}
                          >
                            <span className="font-mono font-bold text-sm tabular-nums-lining">
                              {show.start_time?.slice(0, 5)}
                            </span>
                            <span className="text-[11px] text-secondary group-hover:text-white/90">
                              {show.screen_name}
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-surface-3 group-hover:bg-black/20 font-mono text-[10px] font-semibold uppercase">
                              {show.screen_type}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* About Movie Sidebar */}
          <aside className="space-y-5">
            <div className="p-6 bg-surface border border-subtle rounded-2xl space-y-4 shadow-surface">
              <h3 className="font-display font-bold text-lg text-primary">
                About the Movie
              </h3>

              {movie.description ? (
                <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                  {movie.description}
                </p>
              ) : null}

              <dl className="pt-3 border-t border-subtle text-xs space-y-2.5">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Language</dt>
                  <dd className="font-semibold text-primary">{movie.language}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Genre</dt>
                  <dd className="font-semibold text-primary text-right">
                    {movie.genre}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Duration</dt>
                  <dd className="font-semibold text-primary">
                    {movie.duration_minutes} mins
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Certification</dt>
                  <dd className="font-semibold text-primary">
                    {movie.censor_rating}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Release Date</dt>
                  <dd className="font-semibold text-primary">
                    {formatDateLabel(movie.release_date)}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-start gap-3 text-xs text-emerald-300 leading-relaxed">
              <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
              <span>
                Instant QR gate pass issued upon checkout. Eligible for cancellation
                up to 2 hours before showtime.
              </span>
            </div>
          </aside>
        </div>
      </div>

      {/* INTERACTIVE SEAT SELECTION & CHECKOUT MODAL */}
      <Modal
        isOpen={isSeatModalOpen}
        onClose={() => {
          if (lockingLoading) return;
          setIsSeatModalOpen(false);
        }}
        closeOnBackdrop={!lockingLoading}
        closeOnEscape={!lockingLoading}
        showCloseButton={!lockingLoading}
        size="xl"
        bodyClassName="p-3.5 sm:p-6"
        title={movie.title}
        description={
          selectedShow
            ? `${selectedShow.cinema_name} • ${selectedShow.screen_name} (${selectedShow.screen_type}) • ${selectedShow.start_time?.slice(0, 5)}`
            : undefined
        }
        footer={
          !confirmedBooking && selectedSeatIds.length > 0 ? (
            <div className="flex flex-col w-full gap-2.5">
              {bookingError ? (
                <div
                  role="alert"
                  className="p-2.5 sm:p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2"
                >
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <span>{bookingError}</span>
                </div>
              ) : null}

              <Button
                variant="primary"
                size="lg"
                fullWidth
                isLoading={lockingLoading}
                disabled={selectedSeatIds.length === 0 || lockingLoading}
                rightIcon={<ArrowRight className="w-4 h-4" aria-hidden="true" />}
                onClick={handleLockSeatsAndPay}
              >
                {finalPayable === 0
                  ? "Confirm Booking (₹0.00)"
                  : `Pay ₹${finalPayable.toFixed(2)} with Razorpay`}
              </Button>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
                <span>Secured by Razorpay Checkout • Instant QR Pass</span>
              </div>
            </div>
          ) : undefined
        }
      >
        {confirmedBooking ? (
          <BookingSuccessState
            headingTag="h3"
            title="Booking Confirmed!"
            subtitle="Your seats are confirmed. Present your digital QR pass at the audi entrance."
            rows={[
              {
                label: "Booking Reference",
                value: confirmedBooking.reference,
                accent: "brand",
              },
              { label: "Selected Seats", value: confirmedBooking.seats },
              {
                label: "Total Paid",
                value: `₹${confirmedBooking.amount.toFixed(2)}`,
                accent: "success",
              },
            ]}
            primaryCtaLabel="View Confirmation & Pass"
            onPrimaryClick={() => {
              setIsSeatModalOpen(false);
              router.push(`/bookings/${confirmedBooking.reference}/confirmation`);
            }}
            onSecondaryClick={() => {
              setIsSeatModalOpen(false);
              router.push("/bookings");
            }}
          />
        ) : (
          <div className="space-y-6">
            <SeatMapGrid
              seats={seats}
              loading={seatsLoading}
              selectedSeatIds={selectedSeatIds}
              onToggleSeat={toggleSeatSelection}
              maxSeats={6}
              limitWarning={seatLimitWarning}
            />

            {selectedSeatIds.length > 0 ? (
              <div className="pt-4 border-t border-subtle">
                <CheckoutSummaryCard
                  subtotal={subtotalPrice}
                  discountAmount={discountAmount}
                  itemsLabel={`Seats (${selectedSeatsList
                    .map((s) => `${s.row_code}${s.seat_number}`)
                    .join(", ")}):`}
                  totalLabel="Final Payable:"
                  hasSelection={selectedSeatIds.length > 0}
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
                  bookingError={null}
                  isSubmitting={lockingLoading}
                  hideSubmitButton
                  onSubmit={handleLockSeatsAndPay}
                />
              </div>
            ) : bookingError ? (
              <div
                role="alert"
                className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs text-center"
              >
                {bookingError}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-surface-2/70 border border-subtle text-center text-xs text-secondary">
                Select one or more available seats above to view price & complete checkout.
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
