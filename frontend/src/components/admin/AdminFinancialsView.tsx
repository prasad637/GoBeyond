"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Eye,
  IndianRupee,
  Landmark,
  Percent,
  RefreshCcw,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import {
  DashboardKpiCard,
  DataTable,
  DataTableColumn,
  FilterDropdown,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import { exportRowsToCsv } from "@/components/partner";
import {
  AdminPaymentItem,
  AdminRefundItem,
  ReconciliationReport,
} from "./adminTypes";

export function AdminFinancialsView({
  ledger,
  payments,
  paymentsTotal,
  paymentsPage,
  paymentsPageSize,
  paymentsLoading,
  paymentSearch,
  paymentStatusFilter,
  onPaymentSearchChange,
  onPaymentStatusChange,
  onPaymentPageChange,
  refunds,
  refundsTotal,
  refundsPage,
  refundsPageSize,
  refundsLoading,
  refundStatusFilter,
  onRefundStatusChange,
  onRefundPageChange,
  onReconciled,
}: {
  ledger: Record<string, any> | null;
  payments: AdminPaymentItem[];
  paymentsTotal: number;
  paymentsPage: number;
  paymentsPageSize: number;
  paymentsLoading: boolean;
  paymentSearch: string;
  paymentStatusFilter: string;
  onPaymentSearchChange: (val: string) => void;
  onPaymentStatusChange: (val: string) => void;
  onPaymentPageChange: (p: number) => void;
  refunds: AdminRefundItem[];
  refundsTotal: number;
  refundsPage: number;
  refundsPageSize: number;
  refundsLoading: boolean;
  refundStatusFilter: string;
  onRefundStatusChange: (val: string) => void;
  onRefundPageChange: (p: number) => void;
  onReconciled: () => Promise<void>;
}) {
  const toast = useToast();
  const [subTab, setSubTab] = useState<"PAYMENTS" | "REFUNDS">("PAYMENTS");
  const [runningAudit, setRunningAudit] = useState(false);
  const [auditReport, setAuditReport] = useState<ReconciliationReport | null>(
    null
  );
  const [selectedRefund, setSelectedRefund] = useState<AdminRefundItem | null>(
    null
  );

  const handleRunReconciliation = async () => {
    setRunningAudit(true);
    try {
      const report = await apiRequest<ReconciliationReport>(
        "/payments/reconciliation/run",
        { method: "POST" }
      );
      setAuditReport(report);
      if (report.is_healthy) {
        toast.success(
          "Reconciliation audit healthy",
          `${report.total_payments_audited} payments & ${report.total_refunds_audited} refunds verified.`
        );
      } else {
        toast.warning(
          "Discrepancies detected",
          `${report.discrepancies_count} audit flags surfaced below.`
        );
      }
      await onReconciled();
    } catch (err: any) {
      toast.error("Reconciliation audit failed", err.message || "");
    } finally {
      setRunningAudit(false);
    }
  };

  const paymentColumns: DataTableColumn<AdminPaymentItem>[] = [
    {
      key: "ref",
      header: "Booking Reference",
      render: (p) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {p.booking_reference}
          </span>
          <span className="block text-[11px] text-muted mt-0.5">
            {p.created_at}
          </span>
        </div>
      ),
    },
    {
      key: "gateway",
      header: "Gateway",
      render: (p) => (
        <div>
          {/* E2E checks text=RAZORPAY */}
          <span className="font-mono text-xs font-bold text-primary">
            {p.payment_gateway}
          </span>
          <span className="block font-mono text-[10px] text-muted mt-0.5 truncate max-w-[170px]">
            {p.gateway_payment_id || p.gateway_order_id || "—"}
          </span>
        </div>
      ),
    },
    {
      key: "customer",
      header: "Customer",
      render: (p) => (
        <div>
          <div className="font-medium text-primary">{p.customer_name}</div>
          <div className="text-[11px] text-muted">{p.customer_email}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (p) => <StatusBadge status={p.status} />,
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      render: (p) => (
        <span className="font-display font-bold text-primary tabular-nums-lining">
          {formatRupees(p.amount, { decimals: 2 })}
        </span>
      ),
    },
  ];

  const refundColumns: DataTableColumn<AdminRefundItem>[] = [
    {
      key: "ref",
      header: "Booking / Refund ID",
      render: (r) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {r.booking_reference}
          </span>
          <span className="block font-mono text-[11px] text-muted mt-0.5">
            {r.gateway_refund_id || `Refund #${r.id}`}
          </span>
        </div>
      ),
    },
    {
      key: "customer",
      header: "Customer",
      render: (r) => (
        <span className="font-medium text-primary">{r.customer_name}</span>
      ),
    },
    {
      key: "reason",
      header: "Audit Reason",
      render: (r) => (
        <div className="space-y-1.5 max-w-sm">
          <p className="text-xs text-secondary whitespace-normal break-words leading-relaxed">
            {r.reason || "—"}
          </p>
          {r.reason ? (
            <button
              type="button"
              onClick={() => setSelectedRefund(r)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-console-300 hover:text-console-200 transition-colors"
            >
              <Eye className="w-3 h-3" aria-hidden="true" />
              <span>View Audit Note</span>
            </button>
          ) : null}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      render: (r) => (
        <span className="font-display font-bold text-amber-300 tabular-nums-lining">
          {formatRupees(r.amount, { decimals: 2 })}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Financials, Gateway Ledger &amp; Reconciliation
          </h1>
          <p className="text-xs text-muted mt-0.5">
            System-wide Decimal precision accounting, Razorpay capture audit, and refund settlement verification.
          </p>
        </div>

        <Button
          variant="console"
          size="sm"
          leftIcon={<ShieldCheck className="w-4 h-4" />}
          isLoading={runningAudit}
          onClick={handleRunReconciliation}
        >
          Run Reconciliation Audit
        </Button>
      </div>

      {/* Ledger KPI Strip */}
      {ledger && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <DashboardKpiCard
            label="Gross Booking Value"
            value={formatRupees(ledger.gross_confirmed_booking_value || 0, {
              decimals: 2,
            })}
            icon={<IndianRupee className="w-4 h-4" />}
            accent="console"
          />
          <DashboardKpiCard
            label="Captured Revenue"
            value={formatRupees(ledger.total_captured_payments || 0, {
              decimals: 2,
            })}
            icon={<Landmark className="w-4 h-4" />}
            accent="info"
          />
          <DashboardKpiCard
            label="Refunds Processed"
            value={formatRupees(ledger.total_refunded_amount || 0, {
              decimals: 2,
            })}
            icon={<RefreshCcw className="w-4 h-4" />}
            accent="warning"
          />
          <DashboardKpiCard
            label="Platform Commission"
            value={formatRupees(ledger.actual_platform_revenue || 0, {
              decimals: 2,
            })}
            icon={<Percent className="w-4 h-4" />}
            accent="brand"
          />
          <DashboardKpiCard
            label="Partner Settlements"
            value={formatRupees(ledger.partner_settlements_payable || 0, {
              decimals: 2,
            })}
            icon={<Wallet className="w-4 h-4" />}
            accent="success"
          />
        </div>
      )}

      {/* Reconciliation Audit Results Panel */}
      {auditReport && (
        <div
          className={`rounded-2xl border p-5 space-y-4 ${
            auditReport.is_healthy
              ? "bg-emerald-500/8 border-emerald-500/30"
              : "bg-red-500/8 border-red-500/30"
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              {auditReport.is_healthy ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
              )}
              <div>
                <h3 className="font-display font-bold text-sm sm:text-base text-primary">
                  Reconciliation Report —{" "}
                  {auditReport.is_healthy
                    ? "Zero High/Medium Discrepancies"
                    : `${auditReport.discrepancies_count} Discrepancies Detected`}
                </h3>
                <p className="text-xs text-secondary">
                  Audited {auditReport.total_bookings_audited} bookings ·{" "}
                  {auditReport.total_payments_audited} payments ·{" "}
                  {auditReport.total_refunds_audited} refunds · {auditReport.audited_at}
                </p>
              </div>
            </div>
            <StatusBadge
              status={auditReport.is_healthy ? "CONSERVED" : "FAILED"}
            />
          </div>

          {auditReport.discrepancies.length > 0 && (
            <div className="rounded-xl bg-surface/85 border border-subtle divide-y divide-subtle">
              {auditReport.discrepancies.map((d, idx) => (
                <div
                  key={`${d.code}-${idx}`}
                  className="p-3.5 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-bold text-primary">
                      {d.code}
                      {d.booking_reference ? ` · ${d.booking_reference}` : ""}
                    </span>
                    <StatusBadge
                      status={d.severity === "HIGH" ? "FAILED" : "PENDING"}
                    />
                  </div>
                  <p className="text-secondary">{d.description}</p>
                  <p className="text-muted">Action: {d.suggested_action}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Payments vs Refunds Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="inline-flex rounded-xl bg-surface-2 border border-subtle p-1 text-xs">
          <button
            type="button"
            onClick={() => setSubTab("PAYMENTS")}
            className={`px-4 py-1.5 rounded-lg font-semibold transition-colors ${
              subTab === "PAYMENTS"
                ? "bg-console-600 text-white"
                : "text-secondary hover:text-primary"
            }`}
          >
            Payment Transactions ({paymentsTotal})
          </button>
          <button
            type="button"
            onClick={() => setSubTab("REFUNDS")}
            className={`px-4 py-1.5 rounded-lg font-semibold transition-colors ${
              subTab === "REFUNDS"
                ? "bg-console-600 text-white"
                : "text-secondary hover:text-primary"
            }`}
          >
            Refund Ledger ({refundsTotal})
          </button>
        </div>

        {subTab === "PAYMENTS" && (
          <Button
            variant="secondary"
            size="xs"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            disabled={payments.length === 0}
            onClick={() => {
              exportRowsToCsv(
                `gobeyond-payments-${new Date().toISOString().slice(0, 10)}.csv`,
                ["Booking Ref", "Gateway", "Payment ID", "Order ID", "Customer", "Status", "Amount", "Created"],
                payments.map((p) => [
                  p.booking_reference,
                  p.payment_gateway,
                  p.gateway_payment_id || "",
                  p.gateway_order_id || "",
                  p.customer_email,
                  p.status,
                  p.amount.toFixed(2),
                  p.created_at,
                ])
              );
              toast.success("Payments CSV exported");
            }}
          >
            Export Payments CSV
          </Button>
        )}
      </div>

      {subTab === "PAYMENTS" ? (
        <div className="space-y-4">
          <TableToolbar
            searchValue={paymentSearch}
            onSearchChange={onPaymentSearchChange}
            searchPlaceholder="Search payment ID, order ID, booking ref or email..."
            filters={
              <FilterDropdown
                value={paymentStatusFilter}
                onChange={onPaymentStatusChange}
                placeholder="All Payment States"
                options={[
                  { label: "Captured", value: "CAPTURED" },
                  { label: "Initiated", value: "INITIATED" },
                  { label: "Partially Refunded", value: "PARTIALLY_REFUNDED" },
                  { label: "Refunded", value: "REFUNDED" },
                  { label: "Failed", value: "FAILED" },
                ]}
              />
            }
          />
          <DataTable
            columns={paymentColumns}
            data={payments}
            keyExtractor={(p) => p.id}
            loading={paymentsLoading}
            emptyTitle="No payment transactions match filter"
            pagination={{
              page: paymentsPage,
              pageSize: paymentsPageSize,
              total: paymentsTotal,
              onPageChange: onPaymentPageChange,
            }}
            renderMobileRow={(p) => (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-console-300">
                    {p.booking_reference}
                  </span>
                  <StatusBadge status={p.status} />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-primary">
                    {p.payment_gateway} · {p.customer_name}
                  </span>
                  <strong className="font-display text-primary tabular-nums-lining">
                    {formatRupees(p.amount, { decimals: 2 })}
                  </strong>
                </div>
              </div>
            )}
          />
        </div>
      ) : (
        <div className="space-y-4">
          <TableToolbar
            filters={
              <FilterDropdown
                value={refundStatusFilter}
                onChange={onRefundStatusChange}
                placeholder="All Refund States"
                options={[
                  { label: "Processed", value: "PROCESSED" },
                  { label: "Initiated", value: "INITIATED" },
                  { label: "Failed", value: "FAILED" },
                ]}
              />
            }
          />
          <DataTable
            columns={refundColumns}
            data={refunds}
            keyExtractor={(r) => r.id}
            loading={refundsLoading}
            emptyTitle="No refund records found"
            pagination={{
              page: refundsPage,
              pageSize: refundsPageSize,
              total: refundsTotal,
              onPageChange: onRefundPageChange,
            }}
            renderMobileRow={(r) => (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-console-300">
                    {r.booking_reference}
                  </span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-secondary">{r.customer_name}</span>
                  <strong className="font-display text-amber-300 tabular-nums-lining">
                    {formatRupees(r.amount, { decimals: 2 })}
                  </strong>
                </div>
                <div className="pt-1.5 border-t border-subtle flex items-start justify-between gap-2">
                  <p className="text-[11px] text-secondary whitespace-normal break-words leading-relaxed">
                    {r.reason || "—"}
                  </p>
                  {r.reason ? (
                    <button
                      type="button"
                      onClick={() => setSelectedRefund(r)}
                      className="text-[11px] font-semibold text-console-300 shrink-0"
                    >
                      Inspect
                    </button>
                  ) : null}
                </div>
              </div>
            )}
          />
        </div>
      )}

      {/* Refund Audit Reason Detail Modal */}
      <Modal
        isOpen={Boolean(selectedRefund)}
        onClose={() => setSelectedRefund(null)}
        size="md"
        title="Refund Audit Record"
        description={
          selectedRefund
            ? `${selectedRefund.booking_reference} • ${selectedRefund.gateway_refund_id || `Refund #${selectedRefund.id}`}`
            : undefined
        }
        footer={
          <Button variant="secondary" size="sm" onClick={() => setSelectedRefund(null)}>
            Close
          </Button>
        }
      >
        {selectedRefund ? (
          <div className="space-y-4 text-xs">
            <dl className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-surface-2 border border-subtle">
              <div>
                <dt className="text-muted">Customer</dt>
                <dd className="font-semibold text-primary mt-0.5">
                  {selectedRefund.customer_name}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Refund Amount</dt>
                <dd className="font-display font-bold text-amber-300 mt-0.5 tabular-nums-lining">
                  {formatRupees(selectedRefund.amount, { decimals: 2 })}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Status</dt>
                <dd className="mt-1">
                  <StatusBadge status={selectedRefund.status} />
                </dd>
              </div>
              <div>
                <dt className="text-muted">Processed At</dt>
                <dd className="font-mono text-secondary mt-0.5">
                  {selectedRefund.created_at}
                </dd>
              </div>
            </dl>

            <div className="space-y-1.5">
              <div className="font-mono text-[11px] uppercase tracking-wider text-muted">
                Full Audit Reason
              </div>
              <div className="p-3.5 rounded-xl bg-canvas border border-subtle text-sm text-primary whitespace-pre-wrap break-words leading-relaxed">
                {selectedRefund.reason || "No audit reason recorded."}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

