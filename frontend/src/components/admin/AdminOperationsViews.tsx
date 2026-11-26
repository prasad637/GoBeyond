"use client";

import React, { useMemo, useState } from "react";
import {
  Activity,
  FileText,
  Lock,
  Megaphone,
  Plus,
  RefreshCw,
  Send,
  Tag,
  Trash2,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  ConfirmationModal,
  DashboardKpiCard,
  DataTable,
  DataTableColumn,
  FilterDropdown,
  FormModal,
  Pagination,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import {
  AdminCouponItem,
  AdminNotificationItem,
  AuditLogItem,
  NotificationOutboxItem,
  WorkerStatus,
} from "./adminTypes";

/* -------------------------------------------------------------------------- */
/* 1. COUPONS & PROMOTIONS VIEW                                               */
/* -------------------------------------------------------------------------- */
export function AdminCouponsView({
  coupons,
  onReload,
}: {
  coupons: AdminCouponItem[];
  onReload: () => Promise<void>;
}) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminCouponItem | null>(
    null
  );

  const [form, setForm] = useState({
    code: "",
    description: "",
    discount_type: "PERCENTAGE",
    discount_value: "15",
    min_order_value: "500",
    max_discount: "300",
    usage_limit: "1000",
    valid_until: "",
  });

  const filteredCoupons = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return coupons;
    return coupons.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        (c.description || "").toLowerCase().includes(q)
    );
  }, [coupons, search]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await apiRequest("/admin/coupons", {
        method: "POST",
        body: JSON.stringify({
          code: form.code.trim().toUpperCase(),
          description: form.description.trim(),
          discount_type: form.discount_type,
          discount_value: Number(form.discount_value) || 0,
          min_order_value: Number(form.min_order_value) || 0,
          max_discount: Number(form.max_discount) || 500,
          usage_limit: Number(form.usage_limit) || 1000,
          valid_until: form.valid_until
            ? new Date(form.valid_until).toISOString()
            : null,
        }),
      });
      toast.success("Coupon created", form.code.trim().toUpperCase());
      setCreateOpen(false);
      setForm({
        code: "",
        description: "",
        discount_type: "PERCENTAGE",
        discount_value: "15",
        min_order_value: "500",
        max_discount: "300",
        usage_limit: "1000",
        valid_until: "",
      });
      await onReload();
    } catch (err: any) {
      setFormError(err.message || "Failed to create coupon.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Promotional Coupons &amp; Codes
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Configure checkout promo rules, percentage caps, usage limits, and instant activation toggles.
          </p>
        </div>

        <Button
          variant="console"
          size="sm"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => {
            setFormError(null);
            setCreateOpen(true);
          }}
        >
          Create Coupon
        </Button>
      </div>

      <TableToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Filter coupon code or campaign..."
      />

      {filteredCoupons.length === 0 ? (
        <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
          No promotional coupons found.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredCoupons.map((c) => {
            const pct =
              c.usage_limit > 0
                ? Math.min(100, Math.round((c.used_count / c.usage_limit) * 100))
                : 0;
            return (
              <div
                key={c.id}
                className="rounded-2xl bg-surface border border-subtle p-5 flex flex-col justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-console-500/15 border border-console-500/35 font-mono text-sm font-bold text-console-200">
                      <Tag className="w-3.5 h-3.5" />
                      <span>{c.code}</span>
                    </span>
                    <StatusBadge
                      status={c.is_active ? "ACTIVE" : "DISABLED"}
                    />
                  </div>

                  <p className="text-xs text-secondary leading-relaxed">
                    {c.description || "Platform promotional offer"}
                  </p>

                  <div className="grid grid-cols-3 gap-2 rounded-xl bg-surface-2/70 border border-subtle p-3 text-[11px] tabular-nums-lining">
                    <div>
                      <span className="text-muted block">Discount</span>
                      <strong className="text-primary">
                        {c.discount_type === "PERCENTAGE"
                          ? `${c.discount_value}%`
                          : `₹${c.discount_value}`}
                      </strong>
                    </div>
                    <div>
                      <span className="text-muted block">Min Order</span>
                      <strong className="text-primary">
                        ₹{c.min_order_value}
                      </strong>
                    </div>
                    <div>
                      <span className="text-muted block">Max Cap</span>
                      <strong className="text-primary">₹{c.max_discount}</strong>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px] text-muted tabular-nums-lining">
                      <span>Redemptions</span>
                      <span>
                        {c.used_count} / {c.usage_limit}
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden">
                      <div
                        className="h-full bg-console-500 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-subtle flex items-center justify-between gap-2">
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={async () => {
                      await apiRequest(`/admin/coupons/${c.id}/toggle`, {
                        method: "PUT",
                      });
                      toast.success(
                        c.is_active ? "Coupon paused" : "Coupon activated",
                        c.code
                      );
                      await onReload();
                    }}
                  >
                    {c.is_active ? "Disable" : "Activate"}
                  </Button>

                  <Button
                    variant="danger"
                    size="xs"
                    leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                    onClick={() => setDeleteTarget(c)}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <FormModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
        title="Create Promotional Coupon"
        submitLabel="Publish Coupon"
        loading={saving}
        error={formError}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Coupon Code"
            required
            placeholder="e.g. HYDFEST25"
            value={form.code}
            onChange={(e) =>
              setForm({ ...form, code: e.target.value.toUpperCase() })
            }
          />
          <Select
            label="Discount Type"
            value={form.discount_type}
            onChange={(e) =>
              setForm({ ...form, discount_type: e.target.value })
            }
          >
            <option value="PERCENTAGE">Percentage (%)</option>
            <option value="FLAT">Flat Discount (₹)</option>
          </Select>
        </div>

        <Input
          label="Campaign Description"
          required
          placeholder="25% off weekend entertainment & dining bookings"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            label={form.discount_type === "PERCENTAGE" ? "Value (%)" : "Amount (₹)"}
            type="number"
            min="1"
            required
            value={form.discount_value}
            onChange={(e) =>
              setForm({ ...form, discount_value: e.target.value })
            }
          />
          <Input
            label="Min Order (₹)"
            type="number"
            min="0"
            required
            value={form.min_order_value}
            onChange={(e) =>
              setForm({ ...form, min_order_value: e.target.value })
            }
          />
          <Input
            label="Max Cap (₹)"
            type="number"
            min="0"
            required
            value={form.max_discount}
            onChange={(e) =>
              setForm({ ...form, max_discount: e.target.value })
            }
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Global Usage Limit"
            type="number"
            min="1"
            required
            value={form.usage_limit}
            onChange={(e) => setForm({ ...form, usage_limit: e.target.value })}
          />
          <Input
            label="Expires On (Optional)"
            type="datetime-local"
            value={form.valid_until}
            onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
          />
        </div>
      </FormModal>

      <ConfirmationModal
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={`Delete Coupon ${deleteTarget?.code || ""}`}
        description="Are you sure you want to permanently remove this promotional coupon? This action writes a COUPON_DELETED audit log."
        confirmLabel="Delete Coupon"
        onConfirm={async () => {
          if (!deleteTarget) return;
          await apiRequest(`/admin/coupons/${deleteTarget.id}`, {
            method: "DELETE",
          });
          toast.success("Coupon deleted", deleteTarget.code);
          setDeleteTarget(null);
          await onReload();
        }}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 2. SYSTEM BROADCASTS VIEW                                                  */
/* -------------------------------------------------------------------------- */
export function AdminBroadcastsView({
  notifications,
  total,
  page,
  pageSize,
  onPageChange,
  onReload,
}: {
  notifications: AdminNotificationItem[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (p: number) => void;
  onReload: () => Promise<void>;
}) {
  const toast = useToast();
  const [composeOpen, setComposeOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    message: "",
    target_role: "ALL",
    type: "PLATFORM_BROADCAST",
  });

  const handleBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    setFormError(null);
    try {
      const res = await apiRequest<{ recipients_count: number; target: string }>(
        "/admin/notifications/broadcast",
        {
          method: "POST",
          body: JSON.stringify(form),
        }
      );
      toast.success(
        "Platform broadcast dispatched",
        `Delivered to ${res.recipients_count} accounts (${res.target}).`
      );
      setComposeOpen(false);
      setForm({
        title: "",
        message: "",
        target_role: "ALL",
        type: "PLATFORM_BROADCAST",
      });
      await onReload();
    } catch (err: any) {
      setFormError(err.message || "Broadcast dispatch failed.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary flex items-center gap-2">
            <Megaphone className="w-5 h-5 text-console-400" />
            <span>System Broadcasts &amp; Alert Feed</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Send targeted platform-wide announcements to customers, partners, or all active accounts.
          </p>
        </div>

        <Button
          variant="console"
          size="sm"
          leftIcon={<Send className="w-4 h-4" />}
          onClick={() => {
            setFormError(null);
            setComposeOpen(true);
          }}
        >
          Send Broadcast
        </Button>
      </div>

      <div className="rounded-2xl bg-surface border border-subtle overflow-hidden">
        <div className="divide-y divide-subtle">
          {notifications.length === 0 ? (
            <div className="p-10 text-center text-xs text-muted">
              No recent platform notifications dispatched yet.
            </div>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-start justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-primary">
                      {n.title}
                    </span>
                    <StatusBadge status={n.type || "ALERT"} dot={false} />
                    <span className="text-[11px] font-mono text-muted">
                      User #{n.user_id}
                    </span>
                  </div>
                  <p className="text-xs sm:text-sm text-secondary">
                    {n.message}
                  </p>
                </div>
                <span className="text-[11px] font-mono text-muted shrink-0">
                  {n.created_at}
                </span>
              </div>
            ))
          )}
        </div>

        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      </div>

      <FormModal
        isOpen={composeOpen}
        onClose={() => setComposeOpen(false)}
        onSubmit={handleBroadcast}
        title="Dispatch Platform Broadcast"
        description="Creates targeted in-app notification records across active users and logs BROADCAST_NOTIFICATION."
        submitLabel="Send Broadcast Now"
        loading={sending}
        error={formError}
      >
        <Select
          label="Target Audience"
          value={form.target_role}
          onChange={(e) => setForm({ ...form, target_role: e.target.value })}
        >
          <option value="ALL">All Active Platform Accounts</option>
          <option value="CUSTOMER">Customers Only</option>
          <option value="PARTNER">Partner Accounts Only</option>
        </Select>
        <Input
          label="Announcement Title"
          required
          minLength={3}
          placeholder="e.g. Weekend Maintenance Window / IPL Finals Promo"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <Textarea
          label="Broadcast Message"
          required
          rows={4}
          placeholder="Enter full alert message..."
          value={form.message}
          onChange={(e) => setForm({ ...form, message: e.target.value })}
        />
      </FormModal>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 3. WORKER & OUTBOX MONITOR VIEW                                            */
/* -------------------------------------------------------------------------- */
export function AdminWorkerView({
  workerStatus,
  outboxItems,
  outboxTotal,
  outboxPage,
  outboxPageSize,
  outboxLoading,
  statusFilter,
  channelFilter,
  onStatusChange,
  onChannelChange,
  onPageChange,
  onRefresh,
}: {
  workerStatus: WorkerStatus | null;
  outboxItems: NotificationOutboxItem[];
  outboxTotal: number;
  outboxPage: number;
  outboxPageSize: number;
  outboxLoading: boolean;
  statusFilter: string;
  channelFilter: string;
  onStatusChange: (val: string) => void;
  onChannelChange: (val: string) => void;
  onPageChange: (p: number) => void;
  onRefresh: () => Promise<void>;
}) {
  const toast = useToast();
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [inspectItem, setInspectItem] = useState<NotificationOutboxItem | null>(
    null
  );

  const handleRetry = async (item: NotificationOutboxItem) => {
    setRetryingId(item.id);
    try {
      const res = await apiRequest<{ message: string; new_status: string }>(
        `/notifications/outbox/${item.id}/retry`,
        { method: "POST" }
      );
      toast.success("Outbox job retried", res.message);
      await onRefresh();
    } catch (err: any) {
      toast.error("Retry failed", err.message || "");
    } finally {
      setRetryingId(null);
    }
  };

  const columns: DataTableColumn<NotificationOutboxItem>[] = [
    {
      key: "event",
      header: "Event & Timestamp",
      render: (item) => (
        <div>
          <span className="font-mono text-xs font-bold text-console-300">
            {item.event_type}
          </span>
          <span className="block text-[11px] text-muted mt-0.5">
            {item.created_at}
          </span>
        </div>
      ),
    },
    {
      key: "channel",
      header: "Channel & Provider",
      render: (item) => (
        <div className="space-y-0.5">
          <span className="font-semibold text-xs text-primary">
            {item.channel}
          </span>
          {/* E2E expects text=MOCK_ visible via [provider_name] */}
          <span className="block font-mono text-[11px] text-muted">
            [{item.provider_name || "DEFAULT"}]
          </span>
        </div>
      ),
    },
    {
      key: "recipient",
      header: "Recipient & Title",
      render: (item) => (
        <div className="max-w-[260px]">
          <div className="text-xs font-medium text-primary truncate">
            {item.recipient}
          </div>
          <div className="text-[11px] text-secondary truncate">{item.title}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Delivery Status",
      render: (item) => (
        <div className="space-y-0.5">
          <StatusBadge status={item.status} />
          <span className="block text-[10px] font-mono text-muted">
            Retries: {item.retry_count}/{item.max_retries}
          </span>
        </div>
      ),
    },
    {
      key: "actions",
      header: "Control",
      align: "right",
      render: (item) => (
        <div
          className="flex items-center justify-end gap-1.5"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="xs"
            onClick={() => setInspectItem(item)}
          >
            Payload
          </Button>
          {["FAILED", "DEAD_LETTER", "PENDING"].includes(item.status) && (
            <Button
              variant="console"
              size="xs"
              isLoading={retryingId === item.id}
              leftIcon={<RefreshCw className="w-3 h-3" />}
              onClick={() => handleRetry(item)}
            >
              Retry
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            ARQ Worker &amp; Notification Outbox
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Live Redis queue health, durable delivery states, provider adapters, and controlled dead-letter retries.
          </p>
        </div>

        {workerStatus && (
          <div className="flex items-center gap-2">
            {/* E2E expects text=HEALTHY */}
            <StatusBadge
              status={workerStatus.is_healthy ? "HEALTHY" : "DEGRADED"}
              size="md"
            />
          </div>
        )}
      </div>

      {workerStatus && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <DashboardKpiCard
            label="Redis Broker"
            value={workerStatus.redis_connected ? "ONLINE" : "OFFLINE"}
            subtext={`Queue: ${workerStatus.queue_name}`}
            icon={<Activity className="w-4 h-4" />}
            accent={workerStatus.redis_connected ? "success" : "danger"}
          />
          <DashboardKpiCard
            label="Delivered"
            value={workerStatus.delivered_jobs_count.toLocaleString("en-IN")}
            accent="success"
          />
          <DashboardKpiCard
            label="Pending / Processing"
            value={(
              workerStatus.pending_jobs_count +
              workerStatus.processing_jobs_count
            ).toLocaleString("en-IN")}
            accent="warning"
          />
          <DashboardKpiCard
            label="Failed"
            value={workerStatus.failed_jobs_count.toLocaleString("en-IN")}
            accent="danger"
          />
          <DashboardKpiCard
            label="Dead Letter Queue"
            value={workerStatus.dead_letter_jobs_count.toLocaleString("en-IN")}
            subtext={`Checked ${workerStatus.checked_at}`}
            accent="console"
          />
        </div>
      )}

      <TableToolbar
        filters={
          <>
            <FilterDropdown
              value={statusFilter}
              onChange={onStatusChange}
              placeholder="All Delivery States"
              options={[
                { label: "Delivered", value: "DELIVERED" },
                { label: "Pending", value: "PENDING" },
                { label: "Processing", value: "PROCESSING" },
                { label: "Failed", value: "FAILED" },
                { label: "Dead Letter", value: "DEAD_LETTER" },
                { label: "Skipped", value: "SKIPPED" },
              ]}
            />
            <FilterDropdown
              value={channelFilter}
              onChange={onChannelChange}
              placeholder="All Channels"
              options={[
                { label: "Email", value: "EMAIL" },
                { label: "SMS", value: "SMS" },
                { label: "Push", value: "PUSH" },
                { label: "In-App", value: "IN_APP" },
              ]}
            />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={outboxItems}
        keyExtractor={(i) => i.id}
        loading={outboxLoading}
        onRowClick={setInspectItem}
        emptyTitle="No outbox jobs match filter"
        pagination={{
          page: outboxPage,
          pageSize: outboxPageSize,
          total: outboxTotal,
          onPageChange,
        }}
        renderMobileRow={(item) => (
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-2">
              <span className="font-mono text-xs font-bold text-console-300">
                {item.event_type}
              </span>
              <StatusBadge status={item.status} />
            </div>
            <div className="text-xs text-primary truncate">{item.recipient}</div>
            <div className="flex items-center justify-between text-[11px] font-mono text-muted">
              <span>
                {item.channel} [{item.provider_name || "DEFAULT"}]
              </span>
              <span>{item.created_at}</span>
            </div>
          </div>
        )}
      />

      <Modal
        isOpen={Boolean(inspectItem)}
        onClose={() => setInspectItem(null)}
        size="lg"
        title={
          inspectItem ? `Outbox Job #${inspectItem.id}` : "Outbox Metadata"
        }
        description={
          inspectItem
            ? `${inspectItem.event_type} · ${inspectItem.channel} [${
                inspectItem.provider_name || "DEFAULT"
              }]`
            : undefined
        }
      >
        {inspectItem && (
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-xl bg-surface-2 border border-subtle p-4">
              <div>
                <span className="text-muted block">Recipient</span>
                <strong className="text-primary">{inspectItem.recipient}</strong>
              </div>
              <div>
                <span className="text-muted block">Status</span>
                <div className="mt-1">
                  <StatusBadge status={inspectItem.status} />
                </div>
              </div>
              <div className="sm:col-span-2">
                <span className="text-muted block">Message Content</span>
                <p className="text-secondary mt-1 leading-relaxed">
                  {inspectItem.content}
                </p>
              </div>
              {inspectItem.error_message && (
                <div className="sm:col-span-2 rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-red-300">
                  Error Trace: {inspectItem.error_message}
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted block">
                Provider Response Metadata
              </span>
              <pre className="rounded-xl bg-canvas border border-subtle p-4 text-[11px] font-mono text-secondary overflow-x-auto">
                {JSON.stringify(inspectItem.provider_metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 4. IMMUTABLE AUDIT LOGS VIEW                                               */
/* -------------------------------------------------------------------------- */
export function AdminAuditLogsView({
  logs,
  total,
  page,
  pageSize,
  loading,
  actionFilter,
  resourceFilter,
  onActionChange,
  onResourceChange,
  onPageChange,
}: {
  logs: AuditLogItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  actionFilter: string;
  resourceFilter: string;
  onActionChange: (val: string) => void;
  onResourceChange: (val: string) => void;
  onPageChange: (p: number) => void;
}) {
  const [inspectLog, setInspectLog] = useState<AuditLogItem | null>(null);

  const columns: DataTableColumn<AuditLogItem>[] = [
    {
      key: "time",
      header: "UTC Timestamp",
      render: (l) => (
        <span className="font-mono text-xs text-secondary whitespace-nowrap">
          {l.created_at}
        </span>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (l) => (
        /* E2E checks text=QR_PASS_SCANNED visible! */
        <span className="font-mono text-xs font-bold text-console-300">
          {l.action}
        </span>
      ),
    },
    {
      key: "resource",
      header: "Resource",
      render: (l) => (
        <span className="text-xs text-primary">
          {l.resource_type}
          {l.resource_id ? (
            <span className="font-mono text-muted"> #{l.resource_id}</span>
          ) : (
            ""
          )}
        </span>
      ),
    },
    {
      key: "actor",
      header: "Actor",
      render: (l) => (
        <span className="text-xs text-secondary">
          {l.user_email || (l.user_id ? `User #${l.user_id}` : "SYSTEM")}
        </span>
      ),
    },
    {
      key: "payload",
      header: "JSON Details",
      align: "right",
      render: (l) => (
        <Button
          variant="ghost"
          size="xs"
          leftIcon={<FileText className="w-3.5 h-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            setInspectLog(l);
          }}
        >
          Inspect Payload
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Immutable Security &amp; Audit Logs
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Append-only forensic ledger tracking financial settlements, QR scans, KYC changes, and role mutations.
          </p>
        </div>

        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-2 border border-subtle text-[11px] font-mono text-secondary shrink-0">
          <Lock className="w-3.5 h-3.5 text-console-400" />
          <span>READ-ONLY LEDGER ({total.toLocaleString("en-IN")})</span>
        </span>
      </div>

      <TableToolbar
        filters={
          <>
            <FilterDropdown
              value={actionFilter}
              onChange={onActionChange}
              placeholder="All Actions"
              options={[
                { label: "QR Pass Scanned", value: "QR_PASS_SCANNED" },
                { label: "Partner Status Update", value: "PARTNER_STATUS_UPDATE" },
                { label: "Partner Commission Update", value: "PARTNER_COMMISSION_UPDATE" },
                { label: "Partner KYC Document Verify", value: "PARTNER_DOCUMENT_VERIFY" },
                { label: "User Status Update", value: "USER_STATUS_UPDATE" },
                { label: "Admin Booking Cancel", value: "ADMIN_BOOKING_CANCEL" },
                { label: "Admin Refund Issued", value: "ADMIN_REFUND_ISSUED" },
                { label: "Reconciliation Audit Executed", value: "RECONCILIATION_AUDIT_EXECUTED" },
                { label: "Broadcast Notification", value: "BROADCAST_NOTIFICATION" },
              ]}
            />
            <FilterDropdown
              value={resourceFilter}
              onChange={onResourceChange}
              placeholder="All Resource Types"
              options={[
                { label: "Booking", value: "BOOKING" },
                { label: "Partner", value: "PARTNER" },
                { label: "Partner Document", value: "PARTNER_DOCUMENT" },
                { label: "User", value: "USER" },
                { label: "Refund", value: "REFUND" },
                { label: "Coupon", value: "COUPON" },
                { label: "Financial Reconciliation", value: "FINANCIAL_RECONCILIATION" },
                { label: "Notification", value: "NOTIFICATION" },
              ]}
            />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={logs}
        keyExtractor={(l) => l.id}
        loading={loading}
        onRowClick={setInspectLog}
        emptyTitle="No matching audit events"
        pagination={{ page, pageSize, total, onPageChange }}
        renderMobileRow={(l) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs font-bold text-console-300">
                {l.action}
              </span>
              <span className="font-mono text-[11px] text-muted">
                {l.created_at}
              </span>
            </div>
            <div className="text-xs text-primary">
              {l.resource_type} {l.resource_id ? `#${l.resource_id}` : ""}
            </div>
            <div className="text-[11px] text-secondary">
              Actor: {l.user_email || `User #${l.user_id || "SYSTEM"}`}
            </div>
          </div>
        )}
      />

      <Modal
        isOpen={Boolean(inspectLog)}
        onClose={() => setInspectLog(null)}
        size="lg"
        title={inspectLog ? inspectLog.action : "Audit Event"}
        description={
          inspectLog
            ? `${inspectLog.resource_type} ${
                inspectLog.resource_id || ""
              } · ${inspectLog.created_at}`
            : undefined
        }
      >
        {inspectLog && (
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-xl bg-surface-2 border border-subtle p-4">
              <div>
                <span className="text-muted block">Actor Email</span>
                <strong className="text-primary">
                  {inspectLog.user_email || "SYSTEM"}
                </strong>
              </div>
              <div>
                <span className="text-muted block">Resource Reference</span>
                <strong className="font-mono text-console-300">
                  {inspectLog.resource_type} · {inspectLog.resource_id || "—"}
                </strong>
              </div>
            </div>

            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted block">
                Structured Audit JSON Payload (Read-Only)
              </span>
              <pre className="rounded-xl bg-canvas border border-subtle p-4 font-mono text-xs text-secondary overflow-x-auto leading-relaxed">
                {JSON.stringify(inspectLog.details || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

