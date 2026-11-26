"use client";

import React, { useState } from "react";
import { Eye, ShieldAlert, Ticket, UserCheck } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import {
  ConfirmationModal,
  DataTable,
  DataTableColumn,
  FilterDropdown,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import { AdminUserBookingSummary, AdminUserItem } from "./adminTypes";

export function AdminUsersView({
  users,
  total,
  page,
  pageSize,
  loading,
  search,
  roleFilter,
  statusFilter,
  currentUserId,
  onSearchChange,
  onRoleChange,
  onStatusChange,
  onPageChange,
  onRefreshData,
}: {
  users: AdminUserItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  search: string;
  roleFilter: string;
  statusFilter: string;
  currentUserId?: number;
  onSearchChange: (val: string) => void;
  onRoleChange: (val: string) => void;
  onStatusChange: (val: string) => void;
  onPageChange: (nextPage: number) => void;
  onRefreshData: () => Promise<void>;
}) {
  const toast = useToast();

  const [inspectUser, setInspectUser] = useState<AdminUserItem | null>(null);
  const [userBookings, setUserBookings] = useState<AdminUserBookingSummary[]>(
    []
  );
  const [loadingBookings, setLoadingBookings] = useState(false);

  const [statusModal, setStatusModal] = useState<{
    user: AdminUserItem;
    nextStatus: "ACTIVE" | "SUSPENDED" | "DEACTIVATED";
  } | null>(null);

  const openUserInspector = async (u: AdminUserItem) => {
    setInspectUser(u);
    setLoadingBookings(true);
    try {
      const history = await apiRequest<AdminUserBookingSummary[]>(
        `/admin/users/${u.id}/bookings`
      );
      setUserBookings(history || []);
    } catch {
      setUserBookings([]);
    } finally {
      setLoadingBookings(false);
    }
  };

  const columns: DataTableColumn<AdminUserItem>[] = [
    {
      key: "user",
      header: "Account Holder",
      render: (u) => (
        <div>
          <div className="font-semibold text-primary">{u.full_name}</div>
          <div className="text-[11px] text-muted">
            {u.email} · {u.phone}
          </div>
        </div>
      ),
    },
    {
      key: "roles",
      header: "Roles",
      render: (u) => (
        <div className="flex flex-wrap gap-1">
          {u.roles.map((r) => (
            <span
              key={r}
              className="px-2 py-0.5 rounded-md bg-surface-2 border border-subtle text-[10px] font-mono text-secondary"
            >
              {r}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "city",
      header: "Locality",
      render: (u) => (
        <span className="text-xs text-secondary">
          {u.locality_name
            ? `${u.locality_name}, ${u.city_name || ""}`
            : u.city_name || "—"}
        </span>
      ),
    },
    {
      key: "bookings",
      header: "Orders",
      align: "right",
      render: (u) => (
        <span className="font-mono font-bold text-primary tabular-nums-lining">
          {u.total_bookings}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (u) => <StatusBadge status={u.account_status} />,
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (u) => {
        const isSelf = currentUserId === u.id;
        return (
          <div
            className="flex items-center justify-end gap-1.5"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="xs"
              leftIcon={<Eye className="w-3.5 h-3.5" />}
              onClick={() => openUserInspector(u)}
            >
              History
            </Button>
            {u.account_status === "ACTIVE" ? (
              <Button
                variant="danger"
                size="xs"
                disabled={isSelf}
                title={isSelf ? "Cannot suspend your own active admin account" : undefined}
                onClick={() =>
                  setStatusModal({ user: u, nextStatus: "SUSPENDED" })
                }
              >
                Suspend
              </Button>
            ) : (
              <Button
                variant="console"
                size="xs"
                onClick={() =>
                  setStatusModal({ user: u, nextStatus: "ACTIVE" })
                }
              >
                Reactivate
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Customer &amp; Account Directory
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Inspect user profiles, booking histories, and revoke active refresh sessions cleanly.
          </p>
        </div>
        <span className="text-xs font-mono text-muted tabular-nums-lining">
          {total.toLocaleString("en-IN")} total users
        </span>
      </div>

      <TableToolbar
        searchValue={search}
        onSearchChange={onSearchChange}
        /* Exact placeholder checked by E2E! */
        searchPlaceholder="Search customer name, email, phone..."
        filters={
          <>
            {/* Fixed role slugs matching exact DB role names */}
            <FilterDropdown
              value={roleFilter}
              onChange={onRoleChange}
              placeholder="All Roles"
              options={[
                { label: "Customer", value: "customer" },
                { label: "Restaurant Partner", value: "partner_restaurant" },
                { label: "Cinema Partner", value: "partner_cinema" },
                { label: "Event Partner", value: "partner_event" },
                { label: "Sports / Activities Partner", value: "partner_sports" },
                { label: "Super Admin", value: "super_admin" },
              ]}
            />
            <FilterDropdown
              value={statusFilter}
              onChange={onStatusChange}
              placeholder="All Account States"
              options={[
                { label: "Active", value: "ACTIVE" },
                { label: "Pending Approval", value: "PENDING_APPROVAL" },
                { label: "Suspended", value: "SUSPENDED" },
                { label: "Deactivated", value: "DEACTIVATED" },
              ]}
            />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={users}
        keyExtractor={(u) => u.id}
        loading={loading}
        onRowClick={openUserInspector}
        emptyTitle="No matching accounts"
        emptyDescription="Try searching by full name, email, or registered phone."
        pagination={{ page, pageSize, total, onPageChange }}
        renderMobileRow={(u) => (
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-sm text-primary">
                  {u.full_name}
                </div>
                <div className="text-xs text-muted">{u.email}</div>
              </div>
              <StatusBadge status={u.account_status} />
            </div>
            <div className="flex items-center justify-between text-xs pt-1">
              <span className="font-mono text-secondary">
                {u.roles.join(", ")}
              </span>
              <span className="text-primary font-semibold">
                {u.total_bookings} bookings
              </span>
            </div>
          </div>
        )}
      />

      {/* User Inspector + Booking History Modal */}
      <Modal
        isOpen={Boolean(inspectUser)}
        onClose={() => setInspectUser(null)}
        size="lg"
        title={inspectUser ? inspectUser.full_name : "Account Inspector"}
        description={
          inspectUser
            ? `${inspectUser.email} · ${inspectUser.phone}`
            : undefined
        }
      >
        {inspectUser && (
          <div className="space-y-5 text-xs sm:text-sm">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-surface-2 border border-subtle">
              <div>
                <span className="text-[11px] text-muted block">Account Status</span>
                <div className="mt-1">
                  <StatusBadge status={inspectUser.account_status} />
                </div>
              </div>
              <div>
                <span className="text-[11px] text-muted block">Assigned Roles</span>
                <div className="mt-1 font-mono text-xs text-console-300">
                  {inspectUser.roles.join(", ")}
                </div>
              </div>
              <div>
                <span className="text-[11px] text-muted block">Total Orders</span>
                <strong className="font-display text-lg text-primary block mt-0.5 tabular-nums-lining">
                  {inspectUser.total_bookings}
                </strong>
              </div>
            </div>

            {currentUserId !== inspectUser.id && (
              <div className="flex items-center justify-end gap-2">
                {inspectUser.account_status !== "ACTIVE" && (
                  <Button
                    variant="console"
                    size="xs"
                    leftIcon={<UserCheck className="w-3.5 h-3.5" />}
                    onClick={() =>
                      setStatusModal({ user: inspectUser, nextStatus: "ACTIVE" })
                    }
                  >
                    Reactivate Account
                  </Button>
                )}
                {inspectUser.account_status !== "SUSPENDED" && (
                  <Button
                    variant="danger"
                    size="xs"
                    leftIcon={<ShieldAlert className="w-3.5 h-3.5" />}
                    onClick={() =>
                      setStatusModal({
                        user: inspectUser,
                        nextStatus: "SUSPENDED",
                      })
                    }
                  >
                    Suspend &amp; Revoke Sessions
                  </Button>
                )}
              </div>
            )}

            <div className="space-y-2.5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <Ticket className="w-3.5 h-3.5 text-console-400" />
                <span>Booking History ({userBookings.length})</span>
              </h4>

              {loadingBookings ? (
                <div className="py-6 text-center text-xs text-muted">
                  Loading customer bookings...
                </div>
              ) : userBookings.length === 0 ? (
                <div className="rounded-xl border border-dashed border-subtle p-6 text-center text-xs text-muted">
                  This account has not placed any bookings yet.
                </div>
              ) : (
                <div className="rounded-xl border border-subtle divide-y divide-subtle max-h-64 overflow-y-auto">
                  {userBookings.map((b) => (
                    <div
                      key={b.id}
                      className="px-4 py-3 bg-surface-2/40 flex items-center justify-between gap-3 text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-console-300">
                            {b.booking_reference}
                          </span>
                          <StatusBadge status={b.booking_type} dot={false} />
                          <StatusBadge status={b.status} />
                        </div>
                        <div className="text-muted mt-0.5">
                          {b.items_count} item(s) · {b.created_at}
                        </div>
                      </div>
                      <strong className="font-display text-sm text-primary tabular-nums-lining">
                        {formatRupees(b.final_payable, { decimals: 2 })}
                      </strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmationModal
        isOpen={Boolean(statusModal)}
        onClose={() => setStatusModal(null)}
        title={
          statusModal
            ? `${statusModal.nextStatus} Account — ${statusModal.user.full_name}`
            : ""
        }
        description={
          statusModal?.nextStatus === "ACTIVE"
            ? `Restore active access for ${statusModal.user.email}?`
            : `Suspending ${statusModal?.user.email} immediately revokes all active JWT refresh tokens and records an immutable audit event.`
        }
        confirmLabel={
          statusModal?.nextStatus === "ACTIVE"
            ? "Reactivate User"
            : "Confirm Suspension"
        }
        variant={statusModal?.nextStatus === "ACTIVE" ? "console" : "danger"}
        requireNotes={statusModal?.nextStatus !== "ACTIVE"}
        showNotesInput
        onConfirm={async (reason) => {
          if (!statusModal) return;
          await apiRequest(`/admin/users/${statusModal.user.id}/status`, {
            method: "PUT",
            body: JSON.stringify({
              account_status: statusModal.nextStatus,
              reason: reason || undefined,
            }),
          });
          toast.success(
            "User status updated",
            `${statusModal.user.email} -> ${statusModal.nextStatus}`
          );
          const updatedId = statusModal.user.id;
          const nextSt = statusModal.nextStatus;
          setStatusModal(null);
          if (inspectUser?.id === updatedId) {
            setInspectUser((prev) =>
              prev ? { ...prev, account_status: nextSt } : null
            );
          }
          await onRefreshData();
        }}
      />
    </div>
  );
}

