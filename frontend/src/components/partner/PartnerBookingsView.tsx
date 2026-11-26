"use client";

import React, { useMemo, useState } from "react";
import { Copy, Download, Eye, Ticket } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import {
  DataTable,
  DataTableColumn,
  DateRangeFilter,
  FilterDropdown,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import {
  exportRowsToCsv,
  PartnerBookingItem,
  PartnerFinancials,
} from "./partnerTypes";

export function PartnerBookingsView({
  bookings,
  total,
  page,
  pageSize,
  loading,
  search,
  statusFilter,
  startDate,
  endDate,
  onSearchChange,
  onStatusChange,
  onStartDateChange,
  onEndDateChange,
  onClearDates,
  onPageChange,
  financials,
}: {
  bookings: PartnerBookingItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  search: string;
  statusFilter: string;
  startDate: string;
  endDate: string;
  onSearchChange: (val: string) => void;
  onStatusChange: (val: string) => void;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  onClearDates: () => void;
  onPageChange: (nextPage: number) => void;
  financials: PartnerFinancials | null;
}) {
  const toast = useToast();
  const [inspecting, setInspecting] = useState<PartnerBookingItem | null>(null);

  const matchedFinancial = useMemo(() => {
    if (!inspecting || !financials?.transactions) return null;
    return (
      financials.transactions.find(
        (t) => t.booking_reference === inspecting.booking_reference
      ) || null
    );
  }, [inspecting, financials]);

  const handleExportCsv = () => {
    exportRowsToCsv(
      `gobeyond-partner-bookings-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Reference", "Customer", "Email", "Phone", "Vertical", "Status", "Amount (INR)", "Created At"],
      bookings.map((b) => [
        b.booking_reference,
        b.customer_name,
        b.customer_email,
        b.customer_phone,
        b.booking_type,
        b.status,
        b.amount.toFixed(2),
        b.created_at,
      ])
    );
    toast.success("CSV exported", `${bookings.length} booking rows exported.`);
  };

  const columns: DataTableColumn<PartnerBookingItem>[] = [
    {
      key: "ref",
      header: "Reference",
      render: (b) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {b.booking_reference}
          </span>
          <span className="block text-[11px] text-muted mt-0.5">
            {b.created_at ? b.created_at.slice(0, 16).replace("T", " ") : "—"}
          </span>
        </div>
      ),
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
      key: "items",
      header: "Line Items",
      render: (b) => (
        <div className="text-xs text-secondary max-w-[260px] truncate">
          {b.items && b.items.length > 0
            ? b.items.map((i) => `${i.quantity}x ${i.name}`).join(", ")
            : b.booking_type}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (b) => <StatusBadge status={b.status} />,
    },
    {
      key: "amount",
      header: "Payable",
      align: "right",
      render: (b) => (
        <span className="font-display font-bold text-primary tabular-nums-lining">
          {formatRupees(b.amount, { decimals: 2 })}
        </span>
      ),
    },
    {
      key: "inspect",
      header: "",
      align: "right",
      render: (b) => (
        <Button
          variant="ghost"
          size="xs"
          leftIcon={<Eye className="w-3.5 h-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            setInspecting(b);
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
            Establishment Bookings &amp; Orders
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Tenant-isolated customer reservations, ticket orders, and line-item manifests.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Download className="w-4 h-4" />}
          onClick={handleExportCsv}
          disabled={bookings.length === 0}
        >
          Export Page CSV
        </Button>
      </div>

      <TableToolbar
        searchValue={search}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search ref (GB-...), customer name, email or phone..."
        filters={
          <>
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
        loading={loading}
        onRowClick={(b) => setInspecting(b)}
        emptyTitle="No establishment bookings found"
        emptyDescription="Confirmed or in-flight orders belonging to your venue will appear here."
        pagination={{
          page,
          pageSize,
          total,
          onPageChange,
        }}
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
              {b.items?.map((i) => `${i.quantity}x ${i.name}`).join(", ")}
            </div>
            <div className="flex items-center justify-between pt-1 text-xs">
              <span className="font-mono text-muted">
                {b.created_at?.slice(0, 16).replace("T", " ")}
              </span>
              <span className="font-display font-bold text-primary tabular-nums-lining">
                {formatRupees(b.amount, { decimals: 2 })}
              </span>
            </div>
          </div>
        )}
      />

      {/* Deep Booking Inspector Modal (Zero-500 tenant-safe inspector) */}
      <Modal
        isOpen={Boolean(inspecting)}
        onClose={() => setInspecting(null)}
        size="lg"
        title={
          inspecting
            ? `Order ${inspecting.booking_reference}`
            : "Booking Details"
        }
        description={
          inspecting
            ? `${inspecting.booking_type} · ${inspecting.created_at
                ?.slice(0, 16)
                .replace("T", " ")}`
            : undefined
        }
      >
        {inspecting && (
          <div className="space-y-5 text-xs sm:text-sm">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-surface-2 border border-subtle">
              <div>
                <span className="text-[11px] text-muted uppercase tracking-wider block">
                  Customer
                </span>
                <span className="font-semibold text-primary block mt-0.5">
                  {inspecting.customer_name}
                </span>
                <span className="text-xs text-secondary block">
                  {inspecting.customer_email}
                </span>
                <span className="text-xs text-muted block">
                  {inspecting.customer_phone}
                </span>
              </div>
              <div>
                <span className="text-[11px] text-muted uppercase tracking-wider block">
                  Order Status
                </span>
                <div className="mt-1.5">
                  <StatusBadge status={inspecting.status} />
                </div>
              </div>
              <div>
                <span className="text-[11px] text-muted uppercase tracking-wider block">
                  Customer Total
                </span>
                <span className="font-display text-lg font-bold text-primary tabular-nums-lining block mt-0.5">
                  {formatRupees(inspecting.amount, { decimals: 2 })}
                </span>
              </div>
            </div>

            {inspecting.qr_code_token && (
              <div className="rounded-xl bg-surface-2/60 border border-subtle px-4 py-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <span className="text-[11px] text-muted block">
                    Gate Pass Token
                  </span>
                  <span className="font-mono text-xs text-console-300 truncate block">
                    {inspecting.qr_code_token}
                  </span>
                </div>
                <Button
                  variant="secondary"
                  size="xs"
                  leftIcon={<Copy className="w-3.5 h-3.5" />}
                  onClick={() => {
                    navigator.clipboard?.writeText(
                      inspecting.qr_code_token || ""
                    );
                    toast.info("QR token copied");
                  }}
                >
                  Copy
                </Button>
              </div>
            )}

            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <Ticket className="w-3.5 h-3.5 text-console-400" />
                <span>Booking Line Items ({inspecting.items?.length || 0})</span>
              </h4>
              <div className="rounded-xl border border-subtle overflow-hidden divide-y divide-subtle">
                {(inspecting.items || []).map((item) => (
                  <div
                    key={item.id}
                    className="px-4 py-3 bg-surface-2/40 flex items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="font-semibold text-primary">
                        {item.name}
                      </div>
                      <div className="text-muted mt-0.5">
                        {item.item_type} · Qty {item.quantity} ×{" "}
                        {formatRupees(item.unit_price, { decimals: 2 })}
                      </div>
                    </div>
                    <span className="font-mono font-bold text-primary tabular-nums-lining">
                      {formatRupees(item.subtotal, { decimals: 2 })}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {matchedFinancial && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted">
                  Settlement Attribution
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-console-500/8 border border-console-500/25 text-xs tabular-nums-lining">
                  <div>
                    <span className="text-muted block">Captured</span>
                    <strong className="text-primary">
                      {formatRupees(matchedFinancial.captured_amount, {
                        decimals: 2,
                      })}
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted block">Refunded</span>
                    <strong className="text-amber-300">
                      {formatRupees(matchedFinancial.refund_amount, {
                        decimals: 2,
                      })}
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted block">Platform Fee</span>
                    <strong className="text-console-300">
                      {formatRupees(matchedFinancial.platform_fee, {
                        decimals: 2,
                      })}
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted block">Your Payout</span>
                    <strong className="text-emerald-300">
                      {formatRupees(matchedFinancial.partner_payout, {
                        decimals: 2,
                      })}
                    </strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

