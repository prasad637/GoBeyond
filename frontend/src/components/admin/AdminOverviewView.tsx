"use client";

import React from "react";
import {
  AlertTriangle,
  Building2,
  IndianRupee,
  Landmark,
  Layers,
  Percent,
  RefreshCcw,
  Ticket,
  Users,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DashboardKpiCard,
  DistributionBreakdownCard,
  TrendBarChart,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import { AdminStats, AdminTabId } from "./adminTypes";

export function AdminOverviewView({
  stats,
  onNavigate,
}: {
  stats: AdminStats | null;
  onNavigate: (tab: AdminTabId) => void;
}) {
  if (!stats) {
    return (
      <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
        Executive telemetry is currently unavailable.
      </div>
    );
  }

  const dailySeries = (stats.daily_trends || []).map((d) => ({
    label: d.date,
    fullLabel: d.date,
    revenue: Number(d.gross_revenue || 0),
    bookings: Number(d.bookings || 0),
  }));

  const monthlySeries = (stats.monthly_trends || []).map((m) => ({
    label: m.month.split(" ")[0],
    fullLabel: m.month,
    revenue: Number(m.gross_revenue || 0),
    bookings: Number(m.bookings || 0),
  }));

  const verticalBreakdown = [
    {
      label: "Movies & Cinema",
      count: stats.vertical_bookings?.MOVIE || 0,
      tone: "gold" as const,
    },
    {
      label: "Dining & Tables",
      count: stats.vertical_bookings?.DINING || 0,
      tone: "success" as const,
    },
    {
      label: "Live Events",
      count: stats.vertical_bookings?.EVENT || 0,
      tone: "console" as const,
    },
    {
      label: "Sports & Turfs",
      count: stats.vertical_bookings?.SPORTS || 0,
      tone: "info" as const,
    },
    {
      label: "Activities & Rec",
      count: stats.vertical_bookings?.ACTIVITY || 0,
      tone: "brand" as const,
    },
  ];

  const totalCatalogListings =
    (stats.total_movies || 0) +
    (stats.total_restaurants || 0) +
    (stats.total_events || 0) +
    (stats.total_sports_activities || 0);

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-console-300">
            Platform Control &amp; Telemetry
          </span>
          {/* E2E expects h1:has-text("System Executive Overview") */}
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-primary tracking-tight mt-0.5">
            System Executive Overview
          </h1>
          <p className="text-xs sm:text-sm text-secondary mt-0.5">
            Real-time financial ledger, partner KYC pipeline, and cross-vertical marketplace volume.
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onNavigate("partners")}
          >
            Review Partners ({stats.pending_partner_verifications})
          </Button>
          <Button
            variant="console"
            size="sm"
            onClick={() => onNavigate("financials")}
          >
            Reconcile Ledger
          </Button>
        </div>
      </div>

      {stats.requires_financial_reconciliation && (
        <div className="rounded-2xl bg-red-500/10 border border-red-500/35 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-red-200">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">
                Financial Reconciliation Required ({stats.over_refunded_bookings_count} booking alerts)
              </p>
              <p className="text-red-300/90 mt-0.5">
                Detected cumulative over-refund imbalance of{" "}
                <strong className="font-mono">
                  {formatRupees(stats.total_over_refunded_amount, {
                    decimals: 2,
                  })}
                </strong>
                . Run full financial audit inside Financials &amp; Payments.
              </p>
            </div>
          </div>
          <Button
            variant="danger"
            size="xs"
            onClick={() => onNavigate("financials")}
          >
            Run Audit
          </Button>
        </div>
      )}

      {/* Primary Financial KPI Row — exact labels verified by E2E */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <DashboardKpiCard
          label="Captured Revenue"
          value={formatRupees(stats.total_captured_payments, { decimals: 2 })}
          subtext={`Gross confirmed value ${formatRupees(
            stats.gross_confirmed_booking_value,
            { decimals: 2 }
          )}`}
          icon={<Landmark className="w-4 h-4" />}
          accent="console"
          onClick={() => onNavigate("financials")}
        />
        <DashboardKpiCard
          label="Platform Commission"
          value={formatRupees(stats.actual_platform_revenue, { decimals: 2 })}
          subtext={`Net collected ${formatRupees(stats.net_collected_amount, {
            decimals: 2,
          })}`}
          icon={<Percent className="w-4 h-4" />}
          accent="brand"
          onClick={() => onNavigate("financials")}
        />
        <DashboardKpiCard
          label="Partner Payouts Payable"
          value={formatRupees(stats.partner_settlements_payable, {
            decimals: 2,
          })}
          subtext={`${stats.approved_partners} approved establishments`}
          icon={<Wallet className="w-4 h-4" />}
          accent="success"
          onClick={() => onNavigate("partners")}
        />
        <DashboardKpiCard
          label="Refunded Volume"
          value={formatRupees(stats.total_refunded_amount, { decimals: 2 })}
          subtext={`Net retained settlement pool ${formatRupees(
            stats.net_collected_amount,
            { decimals: 2 }
          )}`}
          icon={<RefreshCcw className="w-4 h-4" />}
          accent="warning"
          onClick={() => onNavigate("financials")}
        />
      </div>

      {/* Operational Marketplace KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <DashboardKpiCard
          label="Platform Users"
          value={stats.total_users.toLocaleString("en-IN")}
          subtext={`${stats.total_customers.toLocaleString("en-IN")} registered consumers`}
          icon={<Users className="w-4 h-4" />}
          accent="info"
          onClick={() => onNavigate("users")}
        />
        <DashboardKpiCard
          label="Partner Ecosystem"
          value={stats.total_partners.toLocaleString("en-IN")}
          subtext={`${stats.approved_partners} active · ${stats.pending_partner_verifications} pending KYC · ${stats.suspended_partners} suspended`}
          icon={<Building2 className="w-4 h-4" />}
          accent="gold"
          onClick={() => onNavigate("partners")}
        />
        <DashboardKpiCard
          label="Total Bookings"
          value={stats.total_bookings.toLocaleString("en-IN")}
          subtext={`${stats.confirmed_bookings.toLocaleString("en-IN")} confirmed passes issued`}
          icon={<Ticket className="w-4 h-4" />}
          accent="console"
          onClick={() => onNavigate("bookings")}
        />
        <DashboardKpiCard
          label="Active Catalog Listings"
          value={totalCatalogListings.toLocaleString("en-IN")}
          subtext={`${stats.total_movies} Movies · ${stats.total_restaurants} Dining · ${stats.total_events} Events · ${stats.total_sports_activities} Sports/Act`}
          icon={<Layers className="w-4 h-4" />}
          accent="brand"
        />
      </div>

      {/* Interactive Trend Chart + Vertical Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TrendBarChart
            title="Platform Gross Revenue & Order Volume"
            subtitle="Switch between 7-Day Daily Telemetry and 6-Month Rolling History"
            series={dailySeries}
            secondarySeries={monthlySeries}
            primaryPeriodLabel="7 Days"
            secondaryPeriodLabel="6 Months"
            defaultMetric="revenue"
          />
        </div>

        <DistributionBreakdownCard
          title="Bookings Across All 5 Verticals"
          subtitle="Live order distribution by marketplace category"
          items={verticalBreakdown}
          footer={
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted flex items-center gap-1.5">
                <IndianRupee className="w-3.5 h-3.5" />
                <span>Total Gross Orders</span>
              </span>
              <strong className="font-mono text-primary">
                {stats.total_bookings.toLocaleString("en-IN")}
              </strong>
            </div>
          }
        />
      </div>
    </div>
  );
}

