"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { formatRupees } from "@/lib/pricing";
import { QRCodeSVG } from "qrcode.react";
import {
  Ticket,
  Calendar,
  Clock,
  MapPin,
  X,
  CheckCircle2,
  AlertCircle,
  Tag,
  Ban,
  ArrowRight
} from "lucide-react";

export default function MyBookingsPage() {
  const { user, openAuthModal } = useAuth();
  const [bookings, setBookings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPass, setSelectedPass] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"ALL" | "CONFIRMED" | "CANCELLED">("ALL");

  // Cancellation modal state
  const [cancelModalBooking, setCancelModalBooking] = useState<any>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const fetchBookings = async () => {
    try {
      const data = await apiRequest<any[]>("/bookings/my-bookings");
      setBookings(data);
    } catch (err) {
      console.error("Failed to load user bookings", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchBookings();
    } else {
      setLoading(false);
    }
  }, [user]);

  const handleCancelBooking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelModalBooking) return;
    setCancelLoading(true);
    setCancelError(null);

    try {
      await apiRequest(`/bookings/${cancelModalBooking.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: cancelReason }),
      });
      setCancelModalBooking(null);
      setCancelReason("");
      await fetchBookings();
    } catch (err: any) {
      setCancelError(err.message || "Failed to cancel booking.");
    } finally {
      setCancelLoading(false);
    }
  };

  if (!user && !loading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6 text-white">
        <Ticket className="w-16 h-16 text-brand-500 mb-4 animate-bounce" />
        <h2 className="text-2xl font-bold">Please sign in to view your bookings</h2>
        <p className="text-gray-400 text-xs mt-1 mb-6">Access your digital QR passes, movie tickets, and dining reservations.</p>
        <button
          onClick={() => openAuthModal("login")}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs transition"
        >
          Sign In Now
        </button>
      </div>
    );
  }

  const filtered = bookings.filter((b) => {
    if (activeTab === "CONFIRMED") return b.status === "CONFIRMED";
    if (activeTab === "CANCELLED") return b.status === "CANCELLED" || b.status === "REFUNDED" || b.status === "REFUND_PENDING";
    return true;
  });

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-gray-800 gap-4">
        <div>
          <h1 className="text-3xl font-extrabold flex items-center space-x-3">
            <Ticket className="w-7 h-7 text-brand-500" />
            <span>My Bookings & Passes</span>
          </h1>
          <p className="text-gray-400 text-xs mt-1">
            Access your admission passes, live QR gate codes, and manage cancellations
          </p>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex bg-gray-900 border border-gray-800 rounded-xl p-1 text-xs">
          {(["ALL", "CONFIRMED", "CANCELLED"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 rounded-lg font-bold transition ${
                activeTab === tab
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tab.charAt(0) + tab.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Bookings List */}
      <div className="space-y-4 mt-8">
        {filtered.length === 0 ? (
          <div className="p-12 text-center bg-gray-900/60 border border-gray-800 rounded-3xl space-y-3">
            <Ticket className="w-12 h-12 text-gray-600 mx-auto" />
            <h3 className="text-base font-bold text-gray-300">No bookings found</h3>
            <p className="text-xs text-gray-500 max-w-sm mx-auto">
              You don’t have any {activeTab.toLowerCase()} bookings yet. Explore movies, dining, and live concerts!
            </p>
          </div>
        ) : (
          filtered.map((b) => {
            const isConfirmed = b.status === "CONFIRMED";
            const isCancelled = ["CANCELLED", "REFUNDED", "REFUND_PENDING"].includes(b.status);
            const isFailed = ["FAILED", "EXPIRED"].includes(b.status);

            let statusColor = "bg-gray-800 text-gray-300";
            if (isConfirmed) statusColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
            else if (b.status === "REFUND_PENDING") statusColor = "bg-amber-500/20 text-amber-300 border-amber-500/30";
            else if (b.status === "REFUNDED") statusColor = "bg-sky-500/20 text-sky-300 border-sky-500/30";
            else if (isCancelled || isFailed) statusColor = "bg-red-500/20 text-red-300 border-red-500/30";
            else if (b.status === "PAYMENT_PENDING") statusColor = "bg-amber-500/20 text-amber-300 border-amber-500/30";

            return (
              <div
                key={b.id}
                className="p-5 bg-gray-900 border border-gray-800 rounded-2xl hover:border-gray-700 transition flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-0.5 rounded-md bg-gray-800 border border-gray-700 text-[10px] font-bold text-white uppercase tracking-wider">
                      {b.booking_type}
                    </span>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${statusColor}`}>
                      {b.status}
                    </span>
                    <span className="text-xs font-mono text-gray-500">Ref: {b.booking_reference}</span>
                  </div>

                  {/* Items */}
                  <div>
                    {b.items?.map((item: any) => (
                      <div key={item.id} className="font-bold text-sm text-white">
                        {item.name} {item.quantity > 1 && `(x${item.quantity})`}
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-400">
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-gray-500" />
                      <span>Booked: {new Date(b.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                    </span>
                    <span>•</span>
                    <span className="text-white font-bold tabular-nums-lining">
                      {formatRupees(Number(b.final_payable ?? 0), { decimals: 2 })}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2.5 self-end md:self-center">
                  <Link
                    href={`/bookings/${b.booking_reference}/confirmation`}
                    className="px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 font-semibold rounded-xl text-xs transition text-gray-300 hover:text-white"
                  >
                    Details
                  </Link>
                  {isConfirmed && (
                    <button
                      onClick={() => setSelectedPass(b)}
                      className="px-4 py-2 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs transition flex items-center space-x-1.5 shadow-md shadow-brand-500/20"
                    >
                      <Ticket className="w-4 h-4" />
                      <span>View QR Pass</span>
                    </button>
                  )}

                  {isConfirmed && (
                    <button
                      onClick={() => setCancelModalBooking(b)}
                      className="px-3 py-2 bg-gray-800 hover:bg-red-500/20 hover:text-red-400 border border-gray-700 font-semibold rounded-xl text-xs transition flex items-center space-x-1"
                    >
                      <Ban className="w-3.5 h-3.5" />
                      <span>Cancel</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* QR PASS DIGITAL TICKET MODAL */}
      {selectedPass && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-sm bg-gray-900 border border-gray-800 rounded-3xl shadow-2xl overflow-hidden text-white flex flex-col">
            
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 bg-gray-950">
              <span className="text-xs font-bold tracking-widest text-brand-400 uppercase">
                Official Admission Pass
              </span>
              <button
                onClick={() => setSelectedPass(null)}
                className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Ticket Card Body */}
            <div className="p-6 text-center space-y-4">
              <div className="p-4 bg-white rounded-2xl inline-block mx-auto shadow-xl">
                <QRCodeSVG
                  value={selectedPass.qr_code_token || selectedPass.booking_reference}
                  size={180}
                  level="H"
                />
              </div>

              <div className="space-y-1">
                <div className="text-[10px] text-gray-500 font-mono tracking-widest uppercase">Gate Scanner Token</div>
                <div className="text-sm font-mono font-bold text-brand-400 truncate">
                  {selectedPass.qr_code_token || selectedPass.booking_reference}
                </div>
              </div>

              {/* Items Breakdown */}
              <div className="p-3 bg-gray-950 border border-gray-800 rounded-xl text-left text-xs space-y-1.5">
                <div className="flex justify-between text-gray-400">
                  <span>Guest / Ticket:</span>
                  <span className="font-bold text-white truncate max-w-[150px]">{user?.full_name}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Experience:</span>
                  <span className="font-bold text-white">{selectedPass.items?.[0]?.name}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Status:</span>
                  <span className="font-bold text-emerald-400">{selectedPass.status}</span>
                </div>
              </div>

              <p className="text-[11px] text-gray-500">
                Please present this QR code at the cinema usher or event entrance scanner for immediate admission.
              </p>

              <Link
                href={`/bookings/${selectedPass.booking_reference}/confirmation`}
                className="w-full py-2.5 bg-gray-800 hover:bg-gray-700 font-bold rounded-xl text-xs transition text-center block text-white border border-gray-700"
              >
                View Full Receipt & Details
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* CANCELLATION MODAL */}
      {cancelModalBooking && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-md bg-gray-900 border border-gray-800 rounded-3xl shadow-2xl p-6 text-white space-y-4">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h3 className="font-bold text-base text-white">Cancel Booking</h3>
              <button
                onClick={() => setCancelModalBooking(null)}
                className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {cancelError && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs">
                {cancelError}
              </div>
            )}

            <p className="text-xs text-gray-300">
              Are you sure you want to cancel booking <span className="font-mono font-bold text-white">{cancelModalBooking.booking_reference}</span>?
              {cancelModalBooking.final_payable > 0 && " Your refund will be processed back to your original payment method in 3-5 business days."}
            </p>

            <form onSubmit={handleCancelBooking} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Reason for Cancellation
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Change of plans, timing conflict..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-red-500 transition resize-none"
                />
              </div>

              <div className="flex space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setCancelModalBooking(null)}
                  className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 font-bold rounded-xl text-xs transition"
                >
                  Keep Booking
                </button>
                <button
                  type="submit"
                  disabled={cancelLoading}
                  className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 font-bold rounded-xl text-xs transition disabled:opacity-50"
                >
                  {cancelLoading ? "Cancelling..." : "Confirm Cancellation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
