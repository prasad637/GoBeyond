"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  Building2,
  FileText,
  IndianRupee,
  LayoutDashboard,
  Megaphone,
  ShieldAlert,
  ShieldCheck,
  Tag,
  Ticket,
  Users,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import {
  DashboardBreadcrumbs,
  DashboardNavItem,
  DashboardShell,
  ErrorState,
  LoadingSkeleton,
  ToastProvider,
  useToast,
} from "@/components/dashboard";
import {
  AdminAuditLogsView,
  AdminBookingItem,
  AdminBookingsView,
  AdminBroadcastsView,
  AdminCouponItem,
  AdminCouponsView,
  AdminFinancialsView,
  AdminNotificationItem,
  AdminOverviewView,
  AdminPartnerItem,
  AdminPartnersView,
  AdminPaymentItem,
  AdminRefundItem,
  AdminStats,
  AdminTabId,
  AdminUserItem,
  AdminUsersView,
  AdminWorkerView,
  AuditLogItem,
  NotificationOutboxItem,
  WorkerStatus,
} from "@/components/admin";

const DEFAULT_PAGE_SIZE = 15;
const BROADCAST_PAGE_SIZE = 20;
const OUTBOX_PAGE_SIZE = 20;
const AUDIT_PAGE_SIZE = 25;

const VALID_TABS: AdminTabId[] = [
  "overview",
  "partners",
  "users",
  "bookings",
  "financials",
  "coupons",
  "broadcasts",
  "worker",
  "audit",
];

function AdminConsoleInner() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const [activeTab, setActiveTab] = useState<AdminTabId>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  // Overview & Ledger
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [ledger, setLedger] = useState<Record<string, any> | null>(null);

  // Partners State
  const [partners, setPartners] = useState<AdminPartnerItem[]>([]);
  const [partnersTotal, setPartnersTotal] = useState(0);
  const [partnersPage, setPartnersPage] = useState(1);
  const [partnersLoading, setPartnersLoading] = useState(false);
  const [partnerSearch, setPartnerSearch] = useState("");
  const [partnerStatusFilter, setPartnerStatusFilter] = useState("");
  const [partnerTypeFilter, setPartnerTypeFilter] = useState("");

  // Users State
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userSearch, setUserSearch] = useState("");
  const [userRoleFilter, setUserRoleFilter] = useState("");
  const [userStatusFilter, setUserStatusFilter] = useState("");

  // Bookings State
  const [bookings, setBookings] = useState<AdminBookingItem[]>([]);
  const [bookingsTotal, setBookingsTotal] = useState(0);
  const [bookingsPage, setBookingsPage] = useState(1);
  const [bookingsLoading, setBookingsLoading] = useState(false);
  const [bookingSearch, setBookingSearch] = useState("");
  const [bookingStatusFilter, setBookingStatusFilter] = useState("");
  const [bookingTypeFilter, setBookingTypeFilter] = useState("");
  const [bookingStartDate, setBookingStartDate] = useState("");
  const [bookingEndDate, setBookingEndDate] = useState("");

  // Financials State
  const [payments, setPayments] = useState<AdminPaymentItem[]>([]);
  const [paymentsTotal, setPaymentsTotal] = useState(0);
  const [paymentsPage, setPaymentsPage] = useState(1);
  const [paymentsLoading, setPaymentsLoading] = useState(false);
  const [paymentSearch, setPaymentSearch] = useState("");
  const [paymentStatusFilter, setPaymentStatusFilter] = useState("");

  const [refunds, setRefunds] = useState<AdminRefundItem[]>([]);
  const [refundsTotal, setRefundsTotal] = useState(0);
  const [refundsPage, setRefundsPage] = useState(1);
  const [refundsLoading, setRefundsLoading] = useState(false);
  const [refundStatusFilter, setRefundStatusFilter] = useState("");

  // Coupons & Broadcasts
  const [coupons, setCoupons] = useState<AdminCouponItem[]>([]);
  const [broadcasts, setBroadcasts] = useState<AdminNotificationItem[]>([]);
  const [broadcastsTotal, setBroadcastsTotal] = useState(0);
  const [broadcastsPage, setBroadcastsPage] = useState(1);

  // Worker & Outbox
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null);
  const [outboxItems, setOutboxItems] = useState<NotificationOutboxItem[]>([]);
  const [outboxTotal, setOutboxTotal] = useState(0);
  const [outboxPage, setOutboxPage] = useState(1);
  const [outboxLoading, setOutboxLoading] = useState(false);
  const [outboxStatusFilter, setOutboxStatusFilter] = useState("");
  const [outboxChannelFilter, setOutboxChannelFilter] = useState("");

  // Audit Logs
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [auditResourceFilter, setAuditResourceFilter] = useState("");

  const isSuperAdmin = Boolean(
    user?.roles?.includes("super_admin") || user?.roles?.includes("admin")
  );

  // Safe client-only query param synchronization (?tab=...)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = new URLSearchParams(window.location.search).get("tab");
    if (!raw) return;
    const mapped = raw === "notifications" ? "broadcasts" : raw;
    if (VALID_TABS.includes(mapped as AdminTabId)) {
      setActiveTab(mapped as AdminTabId);
    }
  }, []);

  const handleTabChange = useCallback((tabId: string) => {
    const clean = tabId as AdminTabId;
    setActiveTab(clean);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", clean);
      window.history.replaceState({}, "", url.toString());
    }
  }, []);

  /* ----------------------------- API LOADERS ------------------------------ */
  const loadStatsAndLedger = useCallback(async () => {
    setStatsError(null);
    try {
      const [s, l] = await Promise.all([
        apiRequest<AdminStats>("/admin/stats"),
        apiRequest<Record<string, any>>("/admin/financials/ledger").catch(
          () => null
        ),
      ]);
      setStats(s);
      setLedger(l || s);
    } catch (err: any) {
      setStatsError(err.message || "Unable to fetch platform telemetry.");
    }
  }, []);

  const loadPartners = useCallback(async () => {
    setPartnersLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(partnersPage));
      params.set("page_size", String(DEFAULT_PAGE_SIZE));
      if (partnerSearch.trim()) params.set("search", partnerSearch.trim());
      if (partnerStatusFilter) params.set("status", partnerStatusFilter);
      if (partnerTypeFilter) params.set("partner_type", partnerTypeFilter);

      const res = await apiRequest<{
        total: number;
        partners: AdminPartnerItem[];
      }>(`/admin/partners?${params.toString()}`);
      setPartners(res.partners || []);
      setPartnersTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load partners", err.message || "");
    } finally {
      setPartnersLoading(false);
    }
  }, [partnersPage, partnerSearch, partnerStatusFilter, partnerTypeFilter, toast]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(usersPage));
      params.set("page_size", String(DEFAULT_PAGE_SIZE));
      if (userSearch.trim()) params.set("search", userSearch.trim());
      if (userRoleFilter) params.set("role", userRoleFilter);
      if (userStatusFilter) params.set("account_status", userStatusFilter);

      const res = await apiRequest<{
        total: number;
        users: AdminUserItem[];
      }>(`/admin/users?${params.toString()}`);
      setUsers(res.users || []);
      setUsersTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load customer directory", err.message || "");
    } finally {
      setUsersLoading(false);
    }
  }, [usersPage, userSearch, userRoleFilter, userStatusFilter, toast]);

  const loadBookings = useCallback(async () => {
    setBookingsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(bookingsPage));
      params.set("page_size", String(DEFAULT_PAGE_SIZE));
      if (bookingSearch.trim()) params.set("search", bookingSearch.trim());
      if (bookingStatusFilter) params.set("status", bookingStatusFilter);
      if (bookingTypeFilter) params.set("booking_type", bookingTypeFilter);
      if (bookingStartDate) params.set("start_date", bookingStartDate);
      if (bookingEndDate) params.set("end_date", `${bookingEndDate} 23:59:59`);

      const res = await apiRequest<{
        total: number;
        bookings: AdminBookingItem[];
      }>(`/admin/bookings?${params.toString()}`);
      setBookings(res.bookings || []);
      setBookingsTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load bookings", err.message || "");
    } finally {
      setBookingsLoading(false);
    }
  }, [
    bookingsPage,
    bookingSearch,
    bookingStatusFilter,
    bookingTypeFilter,
    bookingStartDate,
    bookingEndDate,
    toast,
  ]);

  const loadPayments = useCallback(async () => {
    setPaymentsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(paymentsPage));
      params.set("page_size", String(DEFAULT_PAGE_SIZE));
      if (paymentSearch.trim()) params.set("search", paymentSearch.trim());
      if (paymentStatusFilter) params.set("status", paymentStatusFilter);

      const res = await apiRequest<{
        total: number;
        payments: AdminPaymentItem[];
      }>(`/admin/payments?${params.toString()}`);
      setPayments(res.payments || []);
      setPaymentsTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load payments ledger", err.message || "");
    } finally {
      setPaymentsLoading(false);
    }
  }, [paymentsPage, paymentSearch, paymentStatusFilter, toast]);

  const loadRefunds = useCallback(async () => {
    setRefundsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(refundsPage));
      params.set("page_size", String(DEFAULT_PAGE_SIZE));
      if (refundStatusFilter) params.set("status", refundStatusFilter);

      const res = await apiRequest<{
        total: number;
        refunds: AdminRefundItem[];
      }>(`/admin/refunds?${params.toString()}`);
      setRefunds(res.refunds || []);
      setRefundsTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load refunds ledger", err.message || "");
    } finally {
      setRefundsLoading(false);
    }
  }, [refundsPage, refundStatusFilter, toast]);

  const loadCoupons = useCallback(async () => {
    try {
      const list = await apiRequest<AdminCouponItem[]>("/admin/coupons");
      setCoupons(list || []);
    } catch {
      // ignore background sync
    }
  }, []);

  const loadBroadcasts = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: String(broadcastsPage),
        page_size: String(BROADCAST_PAGE_SIZE),
      });
      const res = await apiRequest<{
        total: number;
        notifications: AdminNotificationItem[];
      }>(`/admin/notifications?${params.toString()}`);
      setBroadcasts(res.notifications || []);
      setBroadcastsTotal(res.total || 0);
    } catch {
      // ignore background sync
    }
  }, [broadcastsPage]);

  const loadWorkerAndOutbox = useCallback(async () => {
    setOutboxLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(outboxPage),
        page_size: String(OUTBOX_PAGE_SIZE),
      });
      if (outboxStatusFilter) params.set("status", outboxStatusFilter);
      if (outboxChannelFilter) params.set("channel", outboxChannelFilter);

      const [ws, ob] = await Promise.all([
        apiRequest<WorkerStatus>("/notifications/worker/status").catch(
          () => null
        ),
        apiRequest<{ total: number; items: NotificationOutboxItem[] }>(
          `/notifications/outbox?${params.toString()}`
        ).catch(() => ({ total: 0, items: [] })),
      ]);
      setWorkerStatus(ws);
      setOutboxItems(ob.items || []);
      setOutboxTotal(ob.total || 0);
    } finally {
      setOutboxLoading(false);
    }
  }, [outboxPage, outboxStatusFilter, outboxChannelFilter]);

  const loadAuditLogs = useCallback(async () => {
    setAuditLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(auditPage),
        page_size: String(AUDIT_PAGE_SIZE),
      });
      if (auditActionFilter) params.set("action", auditActionFilter);
      if (auditResourceFilter) params.set("resource_type", auditResourceFilter);

      const res = await apiRequest<{
        total: number;
        logs: AuditLogItem[];
      }>(`/admin/audit-logs?${params.toString()}`);
      setAuditLogs(res.logs || []);
      setAuditTotal(res.total || 0);
    } catch (err: any) {
      toast.error("Failed to load audit logs", err.message || "");
    } finally {
      setAuditLoading(false);
    }
  }, [auditPage, auditActionFilter, auditResourceFilter, toast]);

  /* -------------------------- INITIAL & REACTIVE SYNC --------------------- */
  const loadInitialConsole = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      loadStatsAndLedger(),
      loadPartners(),
      loadUsers(),
      loadBookings(),
      loadPayments(),
      loadRefunds(),
      loadCoupons(),
      loadBroadcasts(),
      loadWorkerAndOutbox(),
      loadAuditLogs(),
    ]);
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!authLoading) {
      if (user && isSuperAdmin) {
        loadInitialConsole();
      } else {
        setLoading(false);
      }
    }
  }, [authLoading, user, isSuperAdmin, loadInitialConsole]);

  // Debounced reactive reload when filter/page state changes
  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    const t = setTimeout(() => {
      loadPartners();
    }, 240);
    return () => clearTimeout(t);
  }, [isSuperAdmin, partnersPage, partnerSearch, partnerStatusFilter, partnerTypeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    const t = setTimeout(() => {
      loadUsers();
    }, 240);
    return () => clearTimeout(t);
  }, [isSuperAdmin, usersPage, userSearch, userRoleFilter, userStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    const t = setTimeout(() => {
      loadBookings();
    }, 240);
    return () => clearTimeout(t);
  }, [
    isSuperAdmin,
    bookingsPage,
    bookingSearch,
    bookingStatusFilter,
    bookingTypeFilter,
    bookingStartDate,
    bookingEndDate,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    const t = setTimeout(() => {
      loadPayments();
    }, 240);
    return () => clearTimeout(t);
  }, [isSuperAdmin, paymentsPage, paymentSearch, paymentStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    loadRefunds();
  }, [isSuperAdmin, refundsPage, refundStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    loadBroadcasts();
  }, [isSuperAdmin, broadcastsPage]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    loadWorkerAndOutbox();
  }, [isSuperAdmin, outboxPage, outboxStatusFilter, outboxChannelFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isSuperAdmin || loading) return;
    loadAuditLogs();
  }, [isSuperAdmin, auditPage, auditActionFilter, auditResourceFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload audit logs automatically whenever admin opens Audit tab so recent events (e.g. QR scans) appear immediately
  useEffect(() => {
    if (isSuperAdmin && activeTab === "audit") {
      loadAuditLogs();
    } else if (isSuperAdmin && activeTab === "worker") {
      loadWorkerAndOutbox();
    }
  }, [isSuperAdmin, activeTab, loadAuditLogs, loadWorkerAndOutbox]);

  const handleGlobalRefresh = async () => {
    setRefreshing(true);
    await loadInitialConsole();
    setRefreshing(false);
    toast.info("Platform telemetry refreshed");
  };

  /* --------------------------- LOADING & AUTH GATES ----------------------- */
  if (authLoading || (isSuperAdmin && loading)) {
    return (
      <DashboardShell title="Super Admin" portalBadge="ADMIN" hasSidebar={false}>
        <LoadingSkeleton showSidebar />
      </DashboardShell>
    );
  }

  // Unauthenticated gate — preserves exact E2E selectors:
  // h1:has-text("Restricted Area") & button:has-text("Authenticate with Admin Credentials")
  if (!user) {
    return (
      <DashboardShell title="Super Admin" portalBadge="ADMIN" hasSidebar={false}>
        <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center p-4">
          <div className="max-w-md w-full rounded-2xl bg-surface border border-subtle p-7 sm:p-8 text-center shadow-modal space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-red-500/12 border border-red-500/30 flex items-center justify-center mx-auto text-red-400">
              <ShieldAlert className="w-8 h-8" />
            </div>

            <div className="space-y-2">
              <span className="inline-block px-2.5 py-0.5 rounded-full bg-console-500/12 border border-console-500/25 text-console-300 text-[11px] font-semibold uppercase tracking-wider">
                Super Admin Security Gate
              </span>
              <h1 className="font-display text-2xl font-bold text-primary tracking-tight">
                Restricted Area
              </h1>
              <p className="text-sm text-secondary leading-relaxed">
                The Super Admin Console is strictly reserved for authorized platform executives.
              </p>
            </div>

            <Button
              variant="console"
              size="lg"
              fullWidth
              onClick={() => router.push("/login?redirect=/admin")}
            >
              Authenticate with Admin Credentials
            </Button>
          </div>
        </div>
      </DashboardShell>
    );
  }

  // Authenticated non-admin RBAC block
  if (!isSuperAdmin) {
    return (
      <DashboardShell title="Access Restricted" portalBadge="403 FORBIDDEN" hasSidebar={false}>
        <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center p-4">
          <div className="max-w-md w-full rounded-2xl bg-surface border border-red-500/30 p-7 sm:p-8 text-center shadow-modal space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-red-500/12 border border-red-500/30 flex items-center justify-center mx-auto text-red-400">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <div className="space-y-2">
              <h1 className="font-display text-2xl font-bold text-primary tracking-tight">
                Super Admin Role Required
              </h1>
              <p className="text-sm text-secondary leading-relaxed">
                Signed in as <strong className="text-primary">{user.email}</strong>. This account does not have{" "}
                <code className="font-mono text-xs text-console-300">super_admin</code> clearance.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2.5">
              <Link href="/" className="flex-1">
                <Button
                  variant="secondary"
                  size="md"
                  fullWidth
                  leftIcon={<ArrowLeft className="w-4 h-4" />}
                >
                  Customer App
                </Button>
              </Link>
              {user.roles?.some((r) => r.startsWith("partner_")) && (
                <Link href="/partner" className="flex-1">
                  <Button variant="console" size="md" fullWidth>
                    Partner Console
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </DashboardShell>
    );
  }

  /* --------------------------- SIDEBAR NAVIGATION ------------------------- */
  const failedOrDlqCount =
    (workerStatus?.failed_jobs_count || 0) +
    (workerStatus?.dead_letter_jobs_count || 0);

  const navItems: DashboardNavItem[] = [
    {
      id: "overview",
      label: "Overview",
      icon: <LayoutDashboard className="w-4 h-4" />,
      section: "Executive",
    },
    {
      // E2E matches aside button:has-text("Partner Management")
      id: "partners",
      label: "Partner Management",
      icon: <Building2 className="w-4 h-4" />,
      badge: stats?.pending_partner_verifications || 0,
      section: "Executive",
    },
    {
      // E2E matches aside button:has-text("Customer Directory")
      id: "users",
      label: "Customer Directory",
      icon: <Users className="w-4 h-4" />,
      section: "Operations",
    },
    {
      // E2E matches aside button:has-text("Booking Operations")
      id: "bookings",
      label: "Booking Operations",
      icon: <Ticket className="w-4 h-4" />,
      section: "Operations",
    },
    {
      // E2E matches aside button:has-text("Financials & Payments")
      id: "financials",
      label: "Financials & Payments",
      icon: <IndianRupee className="w-4 h-4" />,
      badge: stats?.requires_financial_reconciliation ? "!" : undefined,
      section: "Finance",
    },
    {
      id: "coupons",
      label: "Coupons & Promos",
      icon: <Tag className="w-4 h-4" />,
      section: "Growth & Alerts",
    },
    {
      id: "broadcasts",
      label: "System Broadcasts",
      icon: <Megaphone className="w-4 h-4" />,
      section: "Growth & Alerts",
    },
    {
      // E2E matches aside button:has-text("Worker & Outbox")
      id: "worker",
      label: "Worker & Outbox",
      icon: <Activity className="w-4 h-4" />,
      badge: failedOrDlqCount > 0 ? failedOrDlqCount : undefined,
      section: "System Health",
    },
    {
      // E2E matches aside button:has-text("Immutable Audit Logs")
      id: "audit",
      label: "Immutable Audit Logs",
      icon: <FileText className="w-4 h-4" />,
      section: "System Health",
    },
  ];

  const activeNavObj = navItems.find((n) => n.id === activeTab);

  return (
    <DashboardShell
      title="Super Admin"
      subtitle="Enterprise Control & Ledger"
      portalBadge="ADMIN"
      navItems={navItems}
      activeTab={activeTab}
      onTabChange={handleTabChange}
      onRefresh={handleGlobalRefresh}
      refreshing={refreshing}
      notifications={broadcasts.slice(0, 8)}
      onViewAllNotifications={() => handleTabChange("broadcasts")}
      headerIdentity={
        <div className="rounded-xl bg-surface-2/85 border border-subtle p-3 space-y-1.5 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-primary truncate">
              {user.full_name}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-console-500/20 text-console-300 font-mono text-[10px] font-bold">
              ROOT
            </span>
          </div>
          <div className="text-[11px] text-muted truncate">{user.email}</div>
        </div>
      }
      sidebarFooter={
        <div className="text-[11px] text-muted space-y-1">
          <div className="font-semibold text-secondary">Audit Integrity Active</div>
          <p className="leading-snug">
            All partner KYC approvals, commission updates, refunds, and cancellations emit immutable logs.
          </p>
        </div>
      }
    >
      <div className="space-y-5">
        <DashboardBreadcrumbs
          items={[
            { label: "Super Admin", onClick: () => handleTabChange("overview") },
            { label: activeNavObj?.label || "Overview" },
          ]}
        />

        {statsError && activeTab === "overview" && (
          <ErrorState
            title="Executive telemetry temporarily unavailable"
            description={statsError}
            onRetry={loadInitialConsole}
          />
        )}

        {activeTab === "overview" && !statsError && (
          <AdminOverviewView stats={stats} onNavigate={handleTabChange} />
        )}

        {activeTab === "partners" && (
          <AdminPartnersView
            partners={partners}
            total={partnersTotal}
            page={partnersPage}
            pageSize={DEFAULT_PAGE_SIZE}
            loading={partnersLoading}
            search={partnerSearch}
            statusFilter={partnerStatusFilter}
            typeFilter={partnerTypeFilter}
            onSearchChange={(v) => {
              setPartnerSearch(v);
              setPartnersPage(1);
            }}
            onStatusChange={(v) => {
              setPartnerStatusFilter(v);
              setPartnersPage(1);
            }}
            onTypeChange={(v) => {
              setPartnerTypeFilter(v);
              setPartnersPage(1);
            }}
            onPageChange={setPartnersPage}
            onRefreshData={async () => {
              await Promise.all([loadPartners(), loadStatsAndLedger(), loadAuditLogs()]);
            }}
          />
        )}

        {activeTab === "users" && (
          <AdminUsersView
            users={users}
            total={usersTotal}
            page={usersPage}
            pageSize={DEFAULT_PAGE_SIZE}
            loading={usersLoading}
            search={userSearch}
            roleFilter={userRoleFilter}
            statusFilter={userStatusFilter}
            currentUserId={user.id}
            onSearchChange={(v) => {
              setUserSearch(v);
              setUsersPage(1);
            }}
            onRoleChange={(v) => {
              setUserRoleFilter(v);
              setUsersPage(1);
            }}
            onStatusChange={(v) => {
              setUserStatusFilter(v);
              setUsersPage(1);
            }}
            onPageChange={setUsersPage}
            onRefreshData={async () => {
              await Promise.all([loadUsers(), loadStatsAndLedger(), loadAuditLogs()]);
            }}
          />
        )}

        {activeTab === "bookings" && (
          <AdminBookingsView
            bookings={bookings}
            total={bookingsTotal}
            page={bookingsPage}
            pageSize={DEFAULT_PAGE_SIZE}
            loading={bookingsLoading}
            search={bookingSearch}
            statusFilter={bookingStatusFilter}
            typeFilter={bookingTypeFilter}
            startDate={bookingStartDate}
            endDate={bookingEndDate}
            onSearchChange={(v) => {
              setBookingSearch(v);
              setBookingsPage(1);
            }}
            onStatusChange={(v) => {
              setBookingStatusFilter(v);
              setBookingsPage(1);
            }}
            onTypeChange={(v) => {
              setBookingTypeFilter(v);
              setBookingsPage(1);
            }}
            onStartDateChange={(v) => {
              setBookingStartDate(v);
              setBookingsPage(1);
            }}
            onEndDateChange={(v) => {
              setBookingEndDate(v);
              setBookingsPage(1);
            }}
            onClearDates={() => {
              setBookingStartDate("");
              setBookingEndDate("");
              setBookingsPage(1);
            }}
            onPageChange={setBookingsPage}
            onRefreshData={async () => {
              await Promise.all([
                loadBookings(),
                loadStatsAndLedger(),
                loadPayments(),
                loadRefunds(),
                loadAuditLogs(),
              ]);
            }}
          />
        )}

        {activeTab === "financials" && (
          <AdminFinancialsView
            ledger={ledger}
            payments={payments}
            paymentsTotal={paymentsTotal}
            paymentsPage={paymentsPage}
            paymentsPageSize={DEFAULT_PAGE_SIZE}
            paymentsLoading={paymentsLoading}
            paymentSearch={paymentSearch}
            paymentStatusFilter={paymentStatusFilter}
            onPaymentSearchChange={(v) => {
              setPaymentSearch(v);
              setPaymentsPage(1);
            }}
            onPaymentStatusChange={(v) => {
              setPaymentStatusFilter(v);
              setPaymentsPage(1);
            }}
            onPaymentPageChange={setPaymentsPage}
            refunds={refunds}
            refundsTotal={refundsTotal}
            refundsPage={refundsPage}
            refundsPageSize={DEFAULT_PAGE_SIZE}
            refundsLoading={refundsLoading}
            refundStatusFilter={refundStatusFilter}
            onRefundStatusChange={(v) => {
              setRefundStatusFilter(v);
              setRefundsPage(1);
            }}
            onRefundPageChange={setRefundsPage}
            onReconciled={async () => {
              await Promise.all([
                loadStatsAndLedger(),
                loadPayments(),
                loadRefunds(),
                loadAuditLogs(),
              ]);
            }}
          />
        )}

        {activeTab === "coupons" && (
          <AdminCouponsView
            coupons={coupons}
            onReload={async () => {
              await Promise.all([loadCoupons(), loadAuditLogs()]);
            }}
          />
        )}

        {activeTab === "broadcasts" && (
          <AdminBroadcastsView
            notifications={broadcasts}
            total={broadcastsTotal}
            page={broadcastsPage}
            pageSize={BROADCAST_PAGE_SIZE}
            onPageChange={setBroadcastsPage}
            onReload={async () => {
              await Promise.all([loadBroadcasts(), loadAuditLogs()]);
            }}
          />
        )}

        {activeTab === "worker" && (
          <AdminWorkerView
            workerStatus={workerStatus}
            outboxItems={outboxItems}
            outboxTotal={outboxTotal}
            outboxPage={outboxPage}
            outboxPageSize={OUTBOX_PAGE_SIZE}
            outboxLoading={outboxLoading}
            statusFilter={outboxStatusFilter}
            channelFilter={outboxChannelFilter}
            onStatusChange={(v) => {
              setOutboxStatusFilter(v);
              setOutboxPage(1);
            }}
            onChannelChange={(v) => {
              setOutboxChannelFilter(v);
              setOutboxPage(1);
            }}
            onPageChange={setOutboxPage}
            onRefresh={async () => {
              await Promise.all([loadWorkerAndOutbox(), loadAuditLogs()]);
            }}
          />
        )}

        {activeTab === "audit" && (
          <AdminAuditLogsView
            logs={auditLogs}
            total={auditTotal}
            page={auditPage}
            pageSize={AUDIT_PAGE_SIZE}
            loading={auditLoading}
            actionFilter={auditActionFilter}
            resourceFilter={auditResourceFilter}
            onActionChange={(v) => {
              setAuditActionFilter(v);
              setAuditPage(1);
            }}
            onResourceChange={(v) => {
              setAuditResourceFilter(v);
              setAuditPage(1);
            }}
            onPageChange={setAuditPage}
          />
        )}
      </div>
    </DashboardShell>
  );
}

export default function AdminDashboardPage() {
  return (
    <ToastProvider>
      <AdminConsoleInner />
    </ToastProvider>
  );
}
