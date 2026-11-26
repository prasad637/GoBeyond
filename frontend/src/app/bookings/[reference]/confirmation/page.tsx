"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { formatRupees } from "@/lib/pricing";
import { QRCodeSVG } from "qrcode.react";
import {
  CheckCircle2,
  Calendar,
  Clock,
  MapPin,
  Ticket,
  ArrowRight,
  Download,
  AlertCircle,
  Share2,
  ShieldCheck,
  ChevronLeft
} from "lucide-react";

export default function BookingConfirmationPage() {
  const params = useParams();
  const router = useRouter();
  const reference = params.reference as string;
  const { user, isLoading: authLoading } = useAuth();

  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setError("Authentication required. Please sign in to view your booking confirmation.");
      setLoading(false);
      return;
    }
    const fetchBooking = async () => {
      try {
        const data = await apiRequest<any>(`/bookings/${reference}`);
        setBooking(data);
      } catch (err: any) {
        setError(err.message || "Failed to locate booking confirmation.");
      } finally {
        setLoading(false);
      }
    };
    if (reference) fetchBooking();
  }, [reference, user, authLoading]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-gray-400">
        <span className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mb-3"></span>
        <p className="text-xs uppercase tracking-widest text-gray-400">Retrieving Secure Booking Pass...</p>
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-center p-6 text-white">
        <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
        <h2 className="text-2xl font-bold">Booking Not Found</h2>
        <p className="text-gray-400 text-sm mt-1 mb-6 max-w-md">
          {error || "We could not find a confirmed booking with this reference."}
        </p>
        <Link
          href="/bookings"
          className="px-6 py-2.5 bg-gray-800 hover:bg-gray-700 font-bold rounded-xl text-xs transition"
        >
          Go to My Bookings
        </Link>
      </div>
    );
  }

  const isConfirmed = booking.status === "CONFIRMED";
  const qrData = booking.qr_code_token || `GB-PASS-${booking.booking_reference}`;

  return (
    <div className="min-h-screen bg-gray-950 text-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        
        {/* Navigation Breadcrumb */}
        <Link
          href="/bookings"
          className="inline-flex items-center space-x-1.5 text-xs text-gray-400 hover:text-white transition"
        >
          <ChevronLeft className="w-4 h-4" />
          <span>Back to All Bookings</span>
        </Link>

        {/* Status Banner */}
        <div
          className={`border rounded-3xl p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-6 shadow-2xl ${
            isConfirmed
              ? "bg-gradient-to-r from-emerald-950/80 via-gray-900 to-gray-900 border-emerald-500/30"
              : "bg-gradient-to-r from-amber-950/60 via-gray-900 to-gray-900 border-amber-500/30"
          }`}
        >
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              {isConfirmed ? (
                <CheckCircle2 className="w-7 h-7 text-emerald-400 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-7 h-7 text-amber-400 flex-shrink-0" />
              )}
              <span
                className={`text-xs font-bold uppercase tracking-wider ${
                  isConfirmed ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {isConfirmed ? "Booking Confirmed & Verified" : `Status: ${booking.status}`}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
              {isConfirmed
                ? "You are all set to GO BEYOND!"
                : booking.status === "REFUND_PENDING"
                ? "Refund In Progress"
                : booking.status === "REFUNDED"
                ? "Booking Refunded"
                : booking.status === "CANCELLED"
                ? "Booking Cancelled"
                : "Booking Not Confirmed"}
            </h1>
            <p className="text-xs sm:text-sm text-gray-300">
              {isConfirmed
                ? "Your admission pass has been generated. Present the live QR gate pass below at the venue entrance."
                : booking.status === "REFUND_PENDING"
                ? "Your refund has been initiated to the original payment method. This pass is not valid for admission."
                : "This booking is not currently active for gate admission."}
            </p>
          </div>

          <div className="text-right sm:border-l sm:border-gray-800 sm:pl-6 flex-shrink-0">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Booking Reference</span>
            <div className="text-lg sm:text-xl font-mono font-extrabold text-brand-400">{booking.booking_reference}</div>
            <span
              className={`inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                isConfirmed
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                  : "bg-amber-500/20 text-amber-300 border-amber-500/30"
              }`}
            >
              {booking.booking_type}
            </span>
          </div>
        </div>

        {/* Digital Pass Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-3xl overflow-hidden shadow-2xl">
          
          {/* Ticket Header */}
          <div className="bg-gradient-to-r from-brand-900/60 via-purple-900/40 to-gray-900 px-6 py-4 border-b border-gray-800 flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <Ticket className="w-5 h-5 text-brand-400" />
              <span className="text-xs font-bold uppercase tracking-widest text-white">
                {isConfirmed ? "Official Gate Pass" : "Booking Receipt Summary"}
              </span>
            </div>
            <div className={`flex items-center space-x-1.5 text-xs ${isConfirmed ? "text-emerald-400" : "text-amber-400"}`}>
              <ShieldCheck className="w-4 h-4" />
              <span className="text-[11px] font-medium">
                {isConfirmed ? "Tamper-Proof Signed Token" : `Status: ${booking.status}`}
              </span>
            </div>
          </div>

          <div className="p-6 sm:p-8 grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
            
            {/* QR Code Container (Only valid for CONFIRMED bookings) */}
            {isConfirmed ? (
              <div className="md:col-span-5 flex flex-col items-center justify-center p-6 bg-white rounded-2xl shadow-inner">
                <QRCodeSVG
                  value={qrData}
                  size={180}
                  level="H"
                  includeMargin={false}
                />
                <span className="mt-3 text-[10px] font-mono text-gray-600 tracking-wider text-center break-all">
                  {qrData}
                </span>
                <span className="text-[9px] font-bold text-gray-500 mt-1 uppercase tracking-widest">
                  Scan for Entry
                </span>
              </div>
            ) : (
              <div className="md:col-span-5 flex flex-col items-center justify-center p-6 bg-gray-950 border border-gray-800 rounded-2xl text-center space-y-2">
                <AlertCircle className="w-10 h-10 text-amber-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Pass Inactive ({booking.status})
                </span>
                <span className="text-[11px] text-gray-400">
                  QR admission pass is issued and active strictly while booking status is CONFIRMED.
                </span>
              </div>
            )}

            {/* Ticket Details */}
            <div className="md:col-span-7 space-y-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Experience Items</span>
                <div className="mt-1 space-y-2">
                  {booking.items?.map((item: any) => (
                    <div key={item.id} className="p-3 bg-gray-950/60 rounded-xl border border-gray-800 flex justify-between items-center">
                      <div>
                        <div className="font-bold text-sm text-white">{item.name}</div>
                        {item.details?.cinema_name && (
                          <div className="text-xs text-gray-400">{item.details.cinema_name} • {item.details.screen_name}</div>
                        )}
                        {item.details?.restaurant_name && (
                          <div className="text-xs text-gray-400">{item.details.restaurant_name} • Date: {item.details.reservation_date} at {item.details.reservation_time}</div>
                        )}
                        {item.details?.venue_name && (
                          <div className="text-xs text-gray-400">{item.details.venue_name}</div>
                        )}
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-bold text-white">Qty: {item.quantity}</div>
                        {Number(item.subtotal) > 0 && (
                          <div className="text-xs text-brand-400 font-bold tabular-nums-lining">
                            {formatRupees(Number(item.subtotal), { decimals: 2 })}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Price Breakdown */}
              <div className="pt-3 border-t border-gray-800 space-y-1.5 text-xs text-gray-400">
                <div className="flex justify-between">
                  <span>Merchandise Subtotal</span>
                  <span className="text-white tabular-nums-lining">
                    {formatRupees(Number(booking.total_amount ?? 0), { decimals: 2 })}
                  </span>
                </div>
                {Number(booking.discount_amount) > 0 && (
                  <div className="flex justify-between text-emerald-400">
                    <span>Promo Discount</span>
                    <span className="tabular-nums-lining">
                      -{formatRupees(Number(booking.discount_amount ?? 0), { decimals: 2 })}
                    </span>
                  </div>
                )}
                {Number(booking.tax_amount) > 0 && (
                  <div className="flex justify-between">
                    <span>GST (18%)</span>
                    <span className="text-white tabular-nums-lining">
                      {formatRupees(Number(booking.tax_amount ?? 0), { decimals: 2 })}
                    </span>
                  </div>
                )}
                <div className="flex justify-between text-sm font-bold text-white pt-2 border-t border-gray-800">
                  <span>Total Amount Paid</span>
                  <span className="text-brand-400 font-extrabold text-base tabular-nums-lining">
                    {formatRupees(Number(booking.final_payable ?? 0), { decimals: 2 })}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="px-6 py-4 bg-gray-950/80 border-t border-gray-800 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-gray-500">
              Need to cancel? You can manage your reservation from My Bookings.
            </span>
            <div className="flex items-center space-x-3">
              <Link
                href="/bookings"
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white font-bold rounded-xl text-xs transition"
              >
                Go to My Bookings
              </Link>
              <Link
                href="/"
                className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-xl text-xs transition flex items-center space-x-1.5 shadow-md shadow-brand-500/20"
              >
                <span>Discover More</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
