"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  IndianRupee,
  Landmark,
  Percent,
  RefreshCcw,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DashboardKpiCard,
  DataTable,
  DataTableColumn,
  StatusBadge,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import {
  exportRowsToCsv,
  PartnerFinancials,
  PartnerFinancialTransaction,
} from "./partnerTypes";

export function PartnerFinancialsView({
  financials,
}: {
  financials: PartnerFinancials | null;
}) {
  const toast = useToast();

  if (!financials) {
    return (
      <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
        Financial ledger metrics are loading or unavailable.
      </div>
    );
  }

  const net = Number(financials.net_collected_amount || 0);
  const fee = Number(financials.actual_platform_revenue || 0);
  const payout = Number(financials.partner_settlements_payable || 0);
  const requiresRecon = Boolean(financials.requires_financial_reconciliation);
  const isConserved = !requiresRecon && Math.abs(fee + payout - net) < 0.05;

  const handleExportCsv = () => {
    exportRowsToCsv(
      `gobeyond-partner-settlements-${new Date().toISOString().slice(0, 10)}.csv`,
      [
        "Booking Reference",
        "Date",
        "Status",
        "Captured (INR)",
        "Refunded (INR)",
        "Net Collected (INR)",
        "Commission Fee (INR)",
        "Partner Payout (INR)",
      ],
      (financials.transactions || []).map((t) => [
        t.booking_reference,
        t.created_at,
        t.status,
        t.captured_amount.toFixed(2),
        t.refund_amount.toFixed(2),
        t.net_collected.toFixed(2),
        t.platform_fee.toFixed(2),
        t.partner_payout.toFixed(2),
      ])
    );
    toast.success("Settlement ledger exported");
  };

  const columns: DataTableColumn<PartnerFinancialTransaction>[] = [
    {
      key: "ref",
      header: "Booking Reference",
      render: (t) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {t.booking_reference}
          </span>
          <span className="block text-[11px] text-muted mt-0.5">
            {t.created_at}
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (t) => <StatusBadge status={t.status} />,
    },
    {
      key: "captured",
      header: "Captured",
      align: "right",
      render: (t) => (
        <span className="font-mono text-primary tabular-nums-lining">
          {formatRupees(t.captured_amount, { decimals: 2 })}
        </span>
      ),
    },
    {
      key: "refund",
      header: "Refunded",
      align: "right",
      render: (t) => (
        <span className="font-mono text-amber-300 tabular-nums-lining">
          {formatRupees(t.refund_amount, { decimals: 2 })}
        </span>
      ),
    },
    {
      key: "fee",
      header: "Commission",
      align: "right",
      render: (t) => (
        <span className="font-mono text-console-300 tabular-nums-lining">
          -{formatRupees(t.platform_fee, { decimals: 2 })}
        </span>
      ),
    },
    {
      key: "payout",
      header: "Net Payout",
      align: "right",
      render: (t) => (
        <span className="font-display font-bold text-emerald-300 tabular-nums-lining">
          {formatRupees(t.partner_payout, { decimals: 2 })}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Financials &amp; Payout Settlements
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Decimal ROUND_HALF_UP ledger attribution for{" "}
            <strong className="text-secondary">{financials.business_name}</strong>{" "}
            ({(financials.commission_rate * 100).toFixed(2)}% platform rate).
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Download className="w-4 h-4" />}
          onClick={handleExportCsv}
          disabled={!financials.transactions?.length}
        >
          Export Settlement CSV
        </Button>
      </div>

      {/* Over-refund reconciliation warning when flagged */}
      {requiresRecon && (
        <div className="rounded-2xl bg-amber-500/10 border border-amber-500/35 p-4 flex items-start gap-3 text-xs sm:text-sm text-amber-200">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-bold">Reconciliation Review Notice</p>
            <p className="text-xs text-amber-300/90 mt-0.5">
              Cumulative refunds exceed captured balances by{" "}
              <strong className="font-mono">
                {formatRupees(financials.total_over_refunded_amount || 0, {
                  decimals: 2,
                })}
              </strong>
              . Payout settlement holds apply until Super Admin audit completion.
            </p>
          </div>
        </div>
      )}

      {/* 5 Decimal KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <DashboardKpiCard
          label="Gross Order Value"
          value={formatRupees(financials.gross_confirmed_booking_value, {
            decimals: 2,
          })}
          icon={<IndianRupee className="w-4 h-4" />}
          accent="console"
        />
        <DashboardKpiCard
          label="Captured Payments"
          value={formatRupees(financials.total_captured_payments, {
            decimals: 2,
          })}
          icon={<Landmark className="w-4 h-4" />}
          accent="info"
        />
        <DashboardKpiCard
          label="Refunded Amount"
          value={formatRupees(financials.total_refunded_amount, { decimals: 2 })}
          icon={<RefreshCcw className="w-4 h-4" />}
          accent="warning"
        />
        <DashboardKpiCard
          label="Platform Commission"
          value={formatRupees(fee, { decimals: 2 })}
          subtext={`Contract ${(financials.commission_rate * 100).toFixed(2)}%`}
          icon={<Percent className="w-4 h-4" />}
          accent="brand"
        />
        <DashboardKpiCard
          label="Settlement Payable"
          value={formatRupees(payout, { decimals: 2 })}
          icon={<Wallet className="w-4 h-4" />}
          accent="success"
        />
      </div>

      {/* Accounting Conservation Verification Banner (E2E checks text=CONSERVED) */}
      <div className="rounded-2xl bg-surface border border-subtle p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          {isConserved ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          )}
          <div className="text-xs">
            <div className="font-bold text-primary">
              Accounting Conservation Verification
            </div>
            <p className="text-secondary mt-0.5 tabular-nums-lining">
              Net Collected ({formatRupees(net, { decimals: 2 })}) = Commission (
              {formatRupees(fee, { decimals: 2 })}) + Partner Payout (
              {formatRupees(payout, { decimals: 2 })})
            </p>
          </div>
        </div>
        <span
          className={`px-3 py-1 rounded-full border font-mono text-xs font-bold shrink-0 ${
            isConserved
              ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-300"
              : "bg-amber-500/15 border-amber-500/35 text-amber-300"
          }`}
        >
          {isConserved ? "CONSERVED" : "RECONCILIATION_REQUIRED"}
        </span>
      </div>

      {/* Settlement Ledger Table (E2E checks text=Transaction Settlement Ledger) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-base sm:text-lg font-bold text-primary">
            Transaction Settlement Ledger
          </h2>
          <span className="text-xs text-muted font-mono tabular-nums-lining">
            {(financials.transactions || []).length} entries
          </span>
        </div>

        <DataTable
          columns={columns}
          data={financials.transactions || []}
          keyExtractor={(t) => t.booking_id}
          emptyTitle="No settled transactions yet"
          emptyDescription="Completed payments and commission deductions appear here in real time."
          renderMobileRow={(t) => (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-console-300">
                  {t.booking_reference}
                </span>
                <StatusBadge status={t.status} />
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs tabular-nums-lining">
                <div>
                  <span className="text-muted block">Captured</span>
                  <span className="text-primary">
                    {formatRupees(t.captured_amount, { decimals: 2 })}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Fee</span>
                  <span className="text-console-300">
                    -{formatRupees(t.platform_fee, { decimals: 2 })}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-muted block">Payout</span>
                  <strong className="text-emerald-300">
                    {formatRupees(t.partner_payout, { decimals: 2 })}
                  </strong>
                </div>
              </div>
            </div>
          )}
        />
      </div>
    </div>
  );
}

