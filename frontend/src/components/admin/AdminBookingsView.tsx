"use client";

import React, { useState } from "react";
import { Download, Eye, Landmark, RefreshCcw, Ticket, XCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  ConfirmationModal,
  DataTable,
  DataTableColumn,
  DateRangeFilter,
  FilterDropdown,
  FormModal,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import { exportRowsToCsv } from "@/components/partner";
import { AdminBookingDetail, AdminBookingItem } from "./adminTypes";

export function AdminBookingsView({
  bookings,
  total,
  page,
  pageSize,
  loading,
  search,
  statusFilter,
  typeFilter,
  startDate,
  endDate,
  onSearchChange,
  onStatusChange,
  onTypeChange,
  onStartDateChange,
  onEndDateChange,
  onClearDates,
  onPageChange,
  onRefreshData,
}: {
  bookings: AdminBookingItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  search: string;
  statusFilter: string;
  typeFilter: string;
  startDate: string;
  endDate: string;
  onSearchChange: (val: string) => void;
  onStatusChange: (val: string) => void;
  onTypeChange: (val: string) => void;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  onClearDates: () => void;
  onPageChange: (nextPage: number) => void;
  onRefreshData: () => Promise<void>;
}) {
  const toast = useToast();
  const [inspectingBooking, setInspectingBooking] =
    useState<AdminBookingDetail | null>(null);
  const [loadingInspect, setLoadingInspect] = useState(false);

  const [cancelTargetRef, setCancelTargetRef] = useState<string | null>(null);

  const [refundTarget, setRefundTarget] = useState<AdminBookingDetail | null>(
    null
  );
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundLoading, setRefundLoading] = useState(false);
  const [refundError, setRefundError] = useState<string | null>(null);

  const openBookingDetail = async (bookingRef: string) => {
    setLoadingInspect(true);
    try {
      const detail = await apiRequest<AdminBookingDetail>(
        `/admin/bookings/${encodeURIComponent(bookingRef)}`
      );
      setInspectingBooking(detail);
    } catch (err: any) {
      toast.error("Unable to inspect booking", err.message || "");
    } finally {
      setLoadingInspect(false);
    }
  };

  const handleSubmitRefund = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!refundTarget) return;
    if (refundReason.trim().length < 3) {
      setRefundError("Audit reason must be at least 3 characters.");
      return;
    }
    setRefundLoading(true);
    setRefundError(null);
    try {
      const payload: { reason: string; amount?: number } = {
        reason: refundReason.trim(),
      };
      if (refundAmount.trim() !== "") {
        const parsed = Number(refundAmount);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          setRefundError("Enter a positive refund amount in INR.");
          setRefundLoading(false);
          return;
        }
        payload.amount = parsed;
      }

      const res = await apiRequest<{
        gateway_refund_id: string;
        amount: number;
      }>(`/admin/bookings/${encodeURIComponent(refundTarget.booking_reference)}/refund`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast.success(
        "Admin refund issued",
        `Refund ${res.gateway_refund_id} for ${formatRupees(res.amount, {
          decimals: 2,
        })}`
      );
      const refCode = refundTarget.booking_reference;
      setRefundTarget(null);
      await onRefreshData();
      if (inspectingBooking?.booking_reference === refCode) {
        await openBookingDetail(refCode);
      }
    } catch (err: any) {
      setRefundError(err.message || "Unable to issue refund.");
    } finally {
      setRefundLoading(false);
    }
  };

  const columns: DataTableColumn<AdminBookingItem>[] = [
    {
      key: "ref",
      header: "Reference",
      render: (b) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {b.booking_reference}
          </span>
          <span className="block text-[11px] text-muted mt-0.5">
            {b.created_at}
          </span>
        </div>
      ),
    },
    {
      key: "vertical",
      header: "Vertical",
      render: (b) => <StatusBadge status={b.booking_type} dot={false} />,
    },
    {
      key: "customer",
      header: "Customer",
      render: (b) => (
        <div>
          <div className="font-medium text-primary">{b.customer_name}</div>
          <div className="text-[11px] text-muted">{b.customer_email}</div>
        </div>
      ),
    },
    {
      key: "summary",
      header: "Order Items",
      render: (b) => (
        <span className="text-xs text-secondary max-w-[240px] truncate block">
          {b.items_summary || b.booking_type}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (b) => <StatusBadge status={b.status} />,
    },
    {
      key: "payable",
      header: "Payable",
      align: "right",
      render: (b) => (
        <span className="font-display font-bold text-primary tabular-nums-lining">
          {formatRupees(b.final_payable, { decimals: 2 })}
        </span>
      ),
    },
    {
      key: "inspect",
      header: "Actions",
      align: "right",
      render: (b) => (
        <Button
          variant="ghost"
          size="xs"
          leftIcon={<Eye className="w-3.5 h-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            openBookingDetail(b.booking_reference);
          }}
        >
          Inspect
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Cross-Vertical Booking Operations
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Inspect customer orders across Movies, Dining, Events, Sports &amp; Activities; cancel holds or issue verified refunds.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Download className="w-4 h-4" />}
          disabled={bookings.length === 0}
          onClick={() => {
            exportRowsToCsv(
              `gobeyond-admin-bookings-${new Date().toISOString().slice(0, 10)}.csv`,
              ["Reference", "Vertical", "Customer", "Email", "Summary", "Status", "Payable", "Created"],
              bookings.map((b) => [
                b.booking_reference,
                b.booking_type,
                b.customer_name,
                b.customer_email,
                b.items_summary,
                b.status,
                b.final_payable.toFixed(2),
                b.created_at,
              ])
            );
            toast.success("Booking manifest exported");
          }}
        >
          Export Page CSV
        </Button>
      </div>

      <TableToolbar
        searchValue={search}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search booking ref, customer email or name..."
        filters={
          <>
            <FilterDropdown
              value={typeFilter}
              onChange={onTypeChange}
              placeholder="All Verticals"
              options={[
                { label: "Movies", value: "MOVIE" },
                { label: "Dining", value: "DINING" },
                { label: "Events", value: "EVENT" },
                { label: "Sports", value: "SPORTS" },
                { label: "Activities", value: "ACTIVITY" },
              ]}
            />
            <FilterDropdown
              value={statusFilter}
              onChange={onStatusChange}
              placeholder="All Statuses"
              options={[
                { label: "Confirmed", value: "CONFIRMED" },
                { label: "Payment Pending", value: "PAYMENT_PENDING" },
                { label: "Inventory Held", value: "INVENTORY_HELD" },
                { label: "Cancelled", value: "CANCELLED" },
                { label: "Refunded", value: "REFUNDED" },
                { label: "Failed", value: "FAILED" },
              ]}
            />
            <DateRangeFilter
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={onStartDateChange}
              onEndDateChange={onEndDateChange}
              onClear={onClearDates}
            />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={bookings}
        keyExtractor={(b) => b.id}
        loading={loading || loadingInspect}
        onRowClick={(b) => openBookingDetail(b.booking_reference)}
        emptyTitle="No bookings found"
        emptyDescription="Modify search or date range filters to inspect orders."
        pagination={{ page, pageSize, total, onPageChange }}
        renderMobileRow={(b) => (
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-mono text-xs font-bold text-console-300">
                  {b.booking_reference}
                </div>
                <div className="font-semibold text-sm text-primary mt-0.5">
                  {b.customer_name}
                </div>
              </div>
              <StatusBadge status={b.status} />
            </div>
            <div className="text-xs text-secondary truncate">
              {b.booking_type} · {b.items_summary}
            </div>
            <div className="flex items-center justify-between text-xs pt-1">
              <span className="font-mono text-muted">{b.created_at}</span>
              <strong className="font-display text-primary tabular-nums-lining">
                {formatRupees(b.final_payable, { decimals: 2 })}
              </strong>
            </div>
          </div>
        )}
      />

      {/* Deep Booking Inspector Modal */}
      <Modal
        isOpen={Boolean(inspectingBooking)}
        onClose={() => setInspectingBooking(null)}
        size="xl"
        title={
          inspectingBooking
            ? `Booking ${inspectingBooking.booking_reference}`
            : "Booking Details"
        }
        description={
          inspectingBooking
            ? `${inspectingBooking.booking_type} · ${
                inspectingBooking.created_at || ""
              }`
            : undefined
        }
      >
        {inspectingBooking && (
          <div className="space-y-5 text-xs sm:text-sm">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-surface-2 border border-subtle">
              <div>
                <span className="text-[11px] text-muted block">Customer</span>
                <div className="font-semibold text-primary mt-0.5">
                  {inspectingBooking.customer.name}
                </div>
                <div className="text-xs text-secondary">
                  {inspectingBooking.customer.email}
                </div>
                <div className="text-xs text-muted">
                  {inspectingBooking.customer.phone}
                </div>
              </div>
              <div>
                <span className="text-[11px] text-muted block">Status</span>
                <div className="mt-1.5">
                  <StatusBadge status={inspectingBooking.status} />
                </div>
                {inspectingBooking.cancellation_reason && (
                  <p className="text-[11px] text-red-400 mt-1.5">
                    Reason: {inspectingBooking.cancellation_reason}
                  </p>
                )}
              </div>
              <div className="space-y-1 text-xs tabular-nums-lining">
                <div className="flex justify-between text-secondary">
                  <span>Subtotal:</span>
                  <span>
                    {formatRupees(inspectingBooking.total_amount, {
                      decimals: 2,
                    })}
                  </span>
                </div>
                <div className="flex justify-between text-secondary">
                  <span>Discount:</span>
                  <span className="text-emerald-300">
                    -{formatRupees(inspectingBooking.discount_amount, {
                      decimals: 2,
                    })}
                  </span>
                </div>
                <div className="flex justify-between text-secondary">
                  <span>GST / Tax:</span>
                  <span>
                    {formatRupees(inspectingBooking.tax_amount, {
                      decimals: 2,
                    })}
                  </span>
                </div>
                <div className="flex justify-between font-bold text-primary pt-1 border-t border-subtle">
                  <span>Final Payable:</span>
                  <span>
                    {formatRupees(inspectingBooking.final_payable, {
                      decimals: 2,
                    })}
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center justify-end gap-2">
              {!["CANCELLED", "REFUNDED"].includes(inspectingBooking.status) && (
                <Button
                  variant="danger"
                  size="sm"
                  leftIcon={<XCircle className="w-4 h-4" />}
                  onClick={() =>
                    setCancelTargetRef(inspectingBooking.booking_reference)
                  }
                >
                  Cancel Booking
                </Button>
              )}
              {inspectingBooking.payments.some((p) =>
                ["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED"].includes(p.status)
              ) && (
                <Button
                  variant="console"
                  size="sm"
                  leftIcon={<RefreshCcw className="w-4 h-4" />}
                  onClick={() => {
                    setRefundTarget(inspectingBooking);
                    setRefundAmount("");
                    setRefundReason("");
                    setRefundError(null);
                  }}
                >
                  Issue Admin Refund
                </Button>
              )}
            </div>

            {/* Line Items */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <Ticket className="w-3.5 h-3.5 text-console-400" />
                <span>Order Line Items ({inspectingBooking.items.length})</span>
              </h4>
              <div className="rounded-xl border border-subtle divide-y divide-subtle">
                {inspectingBooking.items.map((item) => (
                  <div
                    key={item.id}
                    className="px-4 py-2.5 bg-surface-2/40 flex items-center justify-between gap-2 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-primary">
                        {item.name}
                      </span>
                      <span className="text-muted ml-2">
                        ({item.item_type} · {item.quantity} ×{" "}
                        {formatRupees(item.unit_price, { decimals: 2 })})
                      </span>
                    </div>
                    <span className="font-mono font-bold text-primary tabular-nums-lining">
                      {formatRupees(item.subtotal, { decimals: 2 })}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Payments & Refunds Split */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                  <Landmark className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Gateway Payments ({inspectingBooking.payments.length})</span>
                </h4>
                {inspectingBooking.payments.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-subtle p-4 text-center text-xs text-muted">
                    No payment transactions.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {inspectingBooking.payments.map((p) => (
                      <div
                        key={p.id}
                        className="rounded-xl bg-surface-2 border border-subtle p-3 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-primary">
                            {p.payment_gateway}
                          </span>
                          <StatusBadge status={p.status} />
                        </div>
                        <div className="font-mono text-[11px] text-muted truncate">
                          Order: {p.gateway_order_id || "—"}
                        </div>
                        <div className="font-mono text-[11px] text-secondary truncate">
                          Pay ID: {p.gateway_payment_id || "—"}
                        </div>
                        <div className="font-bold text-primary tabular-nums-lining">
                          {formatRupees(p.amount, { decimals: 2 })} {p.currency}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                  <RefreshCcw className="w-3.5 h-3.5 text-amber-400" />
                  <span>Refund Ledger ({inspectingBooking.refunds.length})</span>
                </h4>
                {inspectingBooking.refunds.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-subtle p-4 text-center text-xs text-muted">
                    No refunds recorded for this booking.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {inspectingBooking.refunds.map((r) => (
                      <div
                        key={r.id}
                        className="rounded-xl bg-surface-2 border border-subtle p-3 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-console-300">
                            {r.gateway_refund_id || `Refund #${r.id}`}
                          </span>
                          <StatusBadge status={r.status} />
                        </div>
                        <div className="font-bold text-amber-300 tabular-nums-lining">
                          {formatRupees(r.amount, { decimals: 2 })}
                        </div>
                        {r.reason && (
                          <div className="text-[11px] text-secondary">
                            {r.reason}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Cancel Booking Confirmation */}
      <ConfirmationModal
        isOpen={Boolean(cancelTargetRef)}
        onClose={() => setCancelTargetRef(null)}
        title={`Cancel Booking ${cancelTargetRef || ""}`}
        description="This immediately marks the booking as CANCELLED and logs an immutable admin audit record. Note: issue refunds separately if funds were captured."
        confirmLabel="Cancel Booking"
        variant="danger"
        requireNotes
        notesLabel="Cancellation Reason (Min 3 characters)"
        onConfirm={async (reason) => {
          if (!cancelTargetRef) return;
          await apiRequest(
            `/admin/bookings/${encodeURIComponent(
              cancelTargetRef
            )}/cancel?reason=${encodeURIComponent(reason)}`,
            { method: "POST" }
          );
          toast.success("Booking cancelled", cancelTargetRef);
          const refCode = cancelTargetRef;
          setCancelTargetRef(null);
          await onRefreshData();
          if (inspectingBooking?.booking_reference === refCode) {
            await openBookingDetail(refCode);
          }
        }}
      />

      {/* Issue Admin Refund Modal */}
      <FormModal
        isOpen={Boolean(refundTarget)}
        onClose={() => setRefundTarget(null)}
        onSubmit={handleSubmitRefund}
        title={
          refundTarget
            ? `Issue Refund — ${refundTarget.booking_reference}`
            : "Issue Refund"
        }
        description="Enforces strict backend remaining-balance validation to prevent over-refunds."
        submitLabel="Execute Refund"
        loading={refundLoading}
        error={refundError}
      >
        <Input
          label="Partial Amount in INR (Leave blank for full remaining balance)"
          type="number"
          step="0.01"
          min="0.01"
          placeholder="Optional e.g. 250.00"
          value={refundAmount}
          onChange={(e) => setRefundAmount(e.target.value)}
        />
        <Textarea
          label="Mandatory Audit Justification"
          required
          placeholder="Describe customer escalation, double-charge, or show cancellation reason..."
          value={refundReason}
          onChange={(e) => setRefundReason(e.target.value)}
        />
      </FormModal>
    </div>
  );
}

