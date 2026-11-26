"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  Bell,
  CheckCircle2,
  Mail,
  Smartphone,
  Sliders,
  RefreshCw,
  Check,
  AlertTriangle,
  CreditCard,
  Ticket,
  DollarSign,
  Info,
  Calendar,
  Sparkles,
  ChevronRight
} from "lucide-react";

export default function NotificationsCenterPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<"inbox" | "preferences">("inbox");
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Preferences State
  const [preferences, setPreferences] = useState({
    email_enabled: true,
    sms_enabled: true,
    push_enabled: true,
    in_app_enabled: true,
    booking_alerts: true,
    payment_alerts: true,
    marketing_enabled: false
  });
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefsSuccess, setPrefsSuccess] = useState<string | null>(null);

  // Load In-App Notifications
  const loadNotifications = async () => {
    try {
      setLoading(true);
      const isReadQuery = filter === "unread" ? "&is_read=false" : "";
      const res = await apiRequest<any>(`/notifications/?page=${page}&page_size=20${isReadQuery}`);
      setNotifications(res.items || []);
      setUnreadCount(res.unread_count || 0);
      setTotalPages(Math.ceil((res.total || 1) / 20));
    } catch (err) {
      console.error("Failed to load notifications", err);
    } finally {
      setLoading(false);
    }
  };

  // Load Preferences
  const loadPreferences = async () => {
    try {
      const res = await apiRequest<any>("/notifications/preferences");
      if (res) {
        setPreferences(res);
      }
    } catch (err) {
      console.error("Failed to load notification preferences", err);
    }
  };

  useEffect(() => {
    if (user) {
      loadNotifications();
      loadPreferences();
    }
  }, [user, page, filter]);

  // Mark single notification as read
  const handleMarkAsRead = async (id: number) => {
    try {
      await apiRequest(`/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error("Failed to mark notification as read", err);
    }
  };

  // Mark all notifications as read
  const handleMarkAllRead = async () => {
    try {
      await apiRequest("/notifications/mark-all-read", { method: "POST" });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to mark all as read", err);
    }
  };

  // Save Preferences
  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingPrefs(true);
      setPrefsSuccess(null);
      const res = await apiRequest<any>("/notifications/preferences", {
        method: "PUT",
        body: JSON.stringify(preferences)
      });
      setPreferences(res);
      setPrefsSuccess("Notification preferences updated successfully!");
      setTimeout(() => setPrefsSuccess(null), 3500);
    } catch (err: any) {
      alert(err.message || "Failed to update notification preferences");
    } finally {
      setSavingPrefs(false);
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "BOOKING_CONFIRMED":
      case "BOOKING_CONFIRMATION":
        return <Ticket className="w-5 h-5 text-emerald-400" />;
      case "PAYMENT_SUCCESS":
      case "PAYMENT_UPDATE":
        return <CreditCard className="w-5 h-5 text-cyan-400" />;
      case "REFUND_PROCESSED":
      case "REFUND_INITIATED":
        return <DollarSign className="w-5 h-5 text-amber-400" />;
      case "BOOKING_CANCELLED":
      case "PAYMENT_FAILED":
        return <AlertTriangle className="w-5 h-5 text-rose-400" />;
      case "BOOKING_REMINDER_24H":
      case "BOOKING_REMINDER_2H":
        return <Calendar className="w-5 h-5 text-purple-400" />;
      default:
        return <Info className="w-5 h-5 text-blue-400" />;
    }
  };

  if (!user) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6 text-white">
        <Bell className="w-16 h-16 text-brand-500 mb-4" />
        <h2 className="text-2xl font-bold">Please sign in to view your notifications</h2>
        <div className="flex space-x-3 mt-4">
          <Link
            href="/login"
            className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs transition"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-6 py-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 font-bold rounded-xl text-xs transition"
          >
            Create Account
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              <span className="p-2.5 bg-brand-500/10 text-brand-400 rounded-2xl border border-brand-500/20">
                <Bell className="w-6 h-6" />
              </span>
              <div>
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Notification Centre</h1>
                <p className="text-xs text-gray-400 mt-0.5">
                  Stay updated on your booking status, payment confirmations, and reminders
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center space-x-3">
            {unreadCount > 0 && activeTab === "inbox" && (
              <button
                onClick={handleMarkAllRead}
                className="px-4 py-2 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-xs font-bold text-gray-300 hover:text-white rounded-xl transition flex items-center space-x-1.5"
              >
                <Check className="w-4 h-4 text-emerald-400" />
                <span>Mark All as Read</span>
              </button>
            )}
            <button
              onClick={() => {
                loadNotifications();
                loadPreferences();
              }}
              className="p-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-400 hover:text-white rounded-xl transition"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-gray-800 text-xs font-bold space-x-8">
          <button
            onClick={() => setActiveTab("inbox")}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition ${
              activeTab === "inbox"
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Bell className="w-4 h-4" />
            <span>Activity Inbox</span>
            {unreadCount > 0 && (
              <span className="px-2 py-0.5 bg-brand-500 text-white rounded-full text-[10px]">
                {unreadCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("preferences")}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition ${
              activeTab === "preferences"
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>Delivery Preferences</span>
          </button>
        </div>

        {/* INBOX TAB */}
        {activeTab === "inbox" && (
          <div className="space-y-6">
            
            {/* Filter Pills */}
            <div className="flex items-center space-x-2 text-xs">
              <button
                onClick={() => {
                  setFilter("all");
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg font-bold transition ${
                  filter === "all"
                    ? "bg-brand-600 text-white"
                    : "bg-gray-900 text-gray-400 hover:text-white"
                }`}
              >
                All Notifications
              </button>
              <button
                onClick={() => {
                  setFilter("unread");
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg font-bold transition flex items-center space-x-1.5 ${
                  filter === "unread"
                    ? "bg-brand-600 text-white"
                    : "bg-gray-900 text-gray-400 hover:text-white"
                }`}
              >
                <span>Unread Only</span>
                {unreadCount > 0 && (
                  <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
                )}
              </button>
            </div>

            {/* Notification List */}
            {loading ? (
              <div className="p-12 text-center text-gray-500 text-xs">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-brand-500" />
                Loading your notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-12 text-center bg-gray-900/40 border border-gray-800 rounded-3xl space-y-3">
                <CheckCircle2 className="w-12 h-12 text-emerald-400/60 mx-auto" />
                <h3 className="font-bold text-sm text-white">All Caught Up!</h3>
                <p className="text-xs text-gray-400 max-w-sm mx-auto">
                  {filter === "unread"
                    ? "You have zero unread notifications."
                    : "You do not have any notifications at the moment."}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => !n.is_read && handleMarkAsRead(n.id)}
                    className={`p-4 rounded-2xl border transition flex items-start space-x-4 cursor-pointer ${
                      n.is_read
                        ? "bg-gray-900/40 border-gray-800/80 hover:bg-gray-900/70"
                        : "bg-gray-900 border-brand-500/40 hover:border-brand-500/80 shadow-md shadow-brand-500/5"
                    }`}
                  >
                    <div className="p-2.5 rounded-xl bg-gray-950 border border-gray-800 flex-shrink-0">
                      {getNotificationIcon(n.type)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center space-x-2">
                          <h4 className={`text-xs font-bold truncate ${n.is_read ? "text-gray-200" : "text-white"}`}>
                            {n.title}
                          </h4>
                          {!n.is_read && (
                            <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0" />
                          )}
                        </div>
                        <span className="text-[10px] text-gray-500 flex-shrink-0">
                          {n.created_at}
                        </span>
                      </div>

                      <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                        {n.message}
                      </p>

                      {/* Deep Link to booking if available */}
                      {n.data && n.data.booking_reference && (
                        <div className="mt-2.5">
                          <Link
                            href={`/bookings`}
                            className="inline-flex items-center space-x-1 text-[11px] text-brand-400 hover:text-brand-300 font-bold transition"
                          >
                            <span>View Booking #{n.data.booking_reference}</span>
                            <ChevronRight className="w-3 h-3" />
                          </Link>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-gray-800 text-xs">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-4 py-2 bg-gray-900 border border-gray-800 rounded-xl disabled:opacity-40 transition"
                >
                  Previous
                </button>
                <span className="text-gray-400">
                  Page {page} of {totalPages}
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="px-4 py-2 bg-gray-900 border border-gray-800 rounded-xl disabled:opacity-40 transition"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}

        {/* PREFERENCES TAB */}
        {activeTab === "preferences" && (
          <form onSubmit={handleSavePreferences} className="space-y-6">
            
            {prefsSuccess && (
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl text-xs flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                <span>{prefsSuccess}</span>
              </div>
            )}

            <div className="p-6 bg-gray-900 border border-gray-800 rounded-3xl space-y-6">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <Sliders className="w-4 h-4 text-brand-400" />
                  <span>Notification Channels</span>
                </h3>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Choose which mediums you prefer for transactional updates and reminders
                </p>
              </div>

              <div className="divide-y divide-gray-800/80 text-xs space-y-4 pt-1">
                
                {/* Email */}
                <div className="flex items-center justify-between pt-4">
                  <div className="flex items-start space-x-3">
                    <Mail className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <span className="font-bold text-white">Email Notifications</span>
                      <p className="text-[11px] text-gray-400">Receive booking vouchers, invoices, and confirmation emails.</p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.email_enabled}
                    onChange={(e) => setPreferences({ ...preferences, email_enabled: e.target.checked })}
                    className="w-4 h-4 rounded text-brand-600 bg-gray-950 border-gray-700 focus:ring-brand-500 cursor-pointer"
                  />
                </div>

                {/* SMS */}
                <div className="flex items-center justify-between pt-4">
                  <div className="flex items-start space-x-3">
                    <Smartphone className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <span className="font-bold text-white">SMS Updates</span>
                      <p className="text-[11px] text-gray-400">Receive instant SMS alerts for critical ticket passes and gate entry.</p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.sms_enabled}
                    onChange={(e) => setPreferences({ ...preferences, sms_enabled: e.target.checked })}
                    className="w-4 h-4 rounded text-brand-600 bg-gray-950 border-gray-700 focus:ring-brand-500 cursor-pointer"
                  />
                </div>

                {/* In-App */}
                <div className="flex items-center justify-between pt-4">
                  <div className="flex items-start space-x-3">
                    <Bell className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <span className="font-bold text-white">In-App Notifications</span>
                      <p className="text-[11px] text-gray-400">Show notification alerts in your account header bell and profile.</p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.in_app_enabled}
                    onChange={(e) => setPreferences({ ...preferences, in_app_enabled: e.target.checked })}
                    className="w-4 h-4 rounded text-brand-600 bg-gray-950 border-gray-700 focus:ring-brand-500 cursor-pointer"
                  />
                </div>

                {/* Booking & Reminders */}
                <div className="flex items-center justify-between pt-4">
                  <div className="flex items-start space-x-3">
                    <Calendar className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <span className="font-bold text-white">24h & 2h Booking Reminders</span>
                      <p className="text-[11px] text-gray-400">Automated reminder alerts before your showtime, match, or table reservation.</p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.booking_alerts}
                    onChange={(e) => setPreferences({ ...preferences, booking_alerts: e.target.checked })}
                    className="w-4 h-4 rounded text-brand-600 bg-gray-950 border-gray-700 focus:ring-brand-500 cursor-pointer"
                  />
                </div>

                {/* Marketing & Promotional */}
                <div className="flex items-center justify-between pt-4">
                  <div className="flex items-start space-x-3">
                    <Sparkles className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <span className="font-bold text-white">Promotions & Curated Discovery Offers</span>
                      <p className="text-[11px] text-gray-400">Exclusive discounts, weekend guides, and partner special events.</p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.marketing_enabled}
                    onChange={(e) => setPreferences({ ...preferences, marketing_enabled: e.target.checked })}
                    className="w-4 h-4 rounded text-brand-600 bg-gray-950 border-gray-700 focus:ring-brand-500 cursor-pointer"
                  />
                </div>

              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={savingPrefs}
                  className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 disabled:opacity-50 transition"
                >
                  {savingPrefs ? "Saving..." : "Save Preferences"}
                </button>
              </div>
            </div>

          </form>
        )}

      </div>
    </div>
  );
}

