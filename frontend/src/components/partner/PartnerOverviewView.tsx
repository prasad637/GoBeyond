"use client";

import React from "react";
import {
  Activity,
  ArrowRight,
  Calendar,
  IndianRupee,
  Layers,
  QrCode,
  Sparkles,
  Ticket,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DashboardKpiCard,
  DistributionBreakdownCard,
  StatusBadge,
  TrendBarChart,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import {
  getVerticalLabels,
  PartnerAnalytics,
  PartnerNotificationRecord,
  PartnerProfile,
  PartnerTabId,
} from "./partnerTypes";

export function PartnerOverviewView({
  partnerProfile,
  analytics,
  notifications,
  onNavigate,
}: {
  partnerProfile: PartnerProfile;
  analytics: PartnerAnalytics | null;
  notifications: PartnerNotificationRecord[];
  onNavigate: (tab: PartnerTabId) => void;
}) {
  const verticalMeta = getVerticalLabels(partnerProfile.partner_type);
  const dailySeries = (analytics?.daily_stats || []).map((d) => ({
    label: d.date,
    fullLabel: d.date,
    revenue: Number(d.revenue || 0),
    bookings: Number(d.bookings || 0),
  }));

  const bookingDistribution = [
    {
      label: "Confirmed",
      count: analytics?.confirmed_bookings || 0,
      tone: "success" as const,
    },
    {
      label: "Pending",
      count: analytics?.pending_bookings || 0,
      tone: "warning" as const,
    },
    {
      label: "Cancelled",
      count: analytics?.cancelled_bookings || 0,
      tone: "danger" as const,
    },
    {
      label: "Refunded",
      count: analytics?.refunded_bookings || 0,
      tone: "info" as const,
    },
  ];

  const recentBookings = analytics?.recent_bookings || [];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Establishment Context Banner */}
      <div className="rounded-2xl bg-gradient-to-br from-surface via-surface to-console-950/35 border border-subtle p-5 sm:p-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-bold uppercase tracking-wider text-console-300">
              {verticalMeta.badge}
            </span>
            <StatusBadge status={partnerProfile.status} />
            <span className="px-2 py-0.5 rounded-md bg-surface-2 border border-subtle text-[11px] font-mono text-secondary">
              Platform Fee: {(partnerProfile.commission_rate * 100).toFixed(2)}%
            </span>
          </div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-primary tracking-tight truncate">
            {partnerProfile.business_name}
          </h1>
          <p className="text-xs sm:text-sm text-secondary">
            {partnerProfile.contact_email} · {partnerProfile.contact_phone}
            {partnerProfile.verified_at
              ? ` · Verified ${partnerProfile.verified_at.slice(0, 10)}`
              : ""}
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2.5 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<Layers className="w-4 h-4" />}
            onClick={() => onNavigate("listings")}
          >
            Manage {verticalMeta.catalogTitle.split(",")[0]}
          </Button>
          <Button
            variant="console"
            size="sm"
            leftIcon={<QrCode className="w-4 h-4" />}
            onClick={() => onNavigate("scanner")}
          >
            Open Gate Scanner
          </Button>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <DashboardKpiCard
          label="Gross Booking Value"
          value={formatRupees(analytics?.gross_revenue || 0, { decimals: 2 })}
          subtext="Total confirmed customer transaction value"
          icon={<IndianRupee className="w-4 h-4" />}
          accent="console"
          onClick={() => onNavigate("financials")}
        />
        <DashboardKpiCard
          label="Net Partner Payout"
          value={formatRupees(analytics?.partner_payout || 0, { decimals: 2 })}
          subtext={`After ${formatRupees(analytics?.platform_fee || 0, { decimals: 2 })} platform commission`}
          icon={<Wallet className="w-4 h-4" />}
          accent="success"
          onClick={() => onNavigate("financials")}
        />
        <DashboardKpiCard
          label="Confirmed Bookings"
          value={(analytics?.confirmed_bookings || 0).toLocaleString("en-IN")}
          subtext={`${analytics?.total_bookings || 0} total orders across lifecycle`}
          icon={<Ticket className="w-4 h-4" />}
          accent="brand"
          onClick={() => onNavigate("bookings")}
        />
        <DashboardKpiCard
          label="Active Listings"
          value={(analytics?.total_listings || 0).toLocaleString("en-IN")}
          subtext={verticalMeta.catalogTitle}
          icon={<Activity className="w-4 h-4" />}
          accent="gold"
          onClick={() => onNavigate("listings")}
        />
      </div>

      {/* Analytics Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TrendBarChart
            title="7-Day Performance Trend"
            subtitle="Daily confirmed bookings & gross collection across your establishment"
            series={dailySeries}
            defaultMetric="revenue"
          />
        </div>

        <DistributionBreakdownCard
          title="Booking Status Distribution"
          subtitle="Lifecycle health across all isolated tenant bookings"
          items={bookingDistribution}
          footer={
            <button
              type="button"
              onClick={() => onNavigate("bookings")}
              className="w-full flex items-center justify-between text-xs font-semibold text-console-300 hover:text-console-200 transition-colors"
            >
              <span>Inspect full booking manifest</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          }
        />
      </div>

      {/* Recent Bookings & Notifications Split */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 rounded-2xl bg-surface border border-subtle overflow-hidden">
          <div className="px-5 py-4 border-b border-subtle flex items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-sm sm:text-base font-bold text-primary">
                Recent Establishment Orders
              </h3>
              <p className="text-xs text-muted mt-0.5">
                Latest 10 customer transactions for {partnerProfile.business_name}
              </p>
            </div>
            <Button
              variant="ghost"
              size="xs"
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              onClick={() => onNavigate("bookings")}
            >
              View All
            </Button>
          </div>

          {recentBookings.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted">
              No recent bookings recorded for this establishment yet.
            </div>
          ) : (
            <div className="divide-y divide-subtle">
              {recentBookings.slice(0, 6).map((b) => (
                <div
                  key={b.id}
                  onClick={() => onNavigate("bookings")}
                  className="px-5 py-3.5 hover:bg-surface-2/60 transition-colors flex items-center justify-between gap-3 cursor-pointer"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-console-300">
                        {b.reference}
                      </span>
                      <StatusBadge status={b.status} />
                    </div>
                    <div className="text-xs text-secondary mt-1 truncate">
                      {b.customer_name} · {b.items_count} item(s) · {b.created_at}
                    </div>
                  </div>
                  <div className="font-display font-bold text-sm text-primary tabular-nums-lining shrink-0">
                    {formatRupees(b.amount, { decimals: 2 })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-2 rounded-2xl bg-surface border border-subtle overflow-hidden flex flex-col justify-between">
          <div>
            <div className="px-5 py-4 border-b border-subtle flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-console-400" />
                <h3 className="font-display text-sm sm:text-base font-bold text-primary">
                  Recent Alerts
                </h3>
              </div>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onNavigate("notifications")}
              >
                Inbox
              </Button>
            </div>

            {notifications.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted">
                No partner alerts yet.
              </div>
            ) : (
              <div className="divide-y divide-subtle">
                {notifications.slice(0, 4).map((n) => (
                  <div key={n.id} className="px-5 py-3.5 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-primary truncate">
                        {n.title}
                      </span>
                      {!n.is_read && (
                        <span className="px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-300 text-[10px] font-bold shrink-0">
                          NEW
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-secondary line-clamp-2">
                      {n.message}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 border-t border-subtle bg-surface-2/40 flex items-center justify-between gap-2">
            <span className="text-[11px] text-muted flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              <span>Daily schedule operations</span>
            </span>
            <Button
              variant="secondary"
              size="xs"
              onClick={() => onNavigate("schedules")}
            >
              Open {verticalMeta.scheduleTitle}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

