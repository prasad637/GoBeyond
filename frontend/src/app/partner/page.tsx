"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  CalendarClock,
  IndianRupee,
  Layers,
  LayoutDashboard,
  QrCode,
  Settings,
  Ticket,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  DashboardBreadcrumbs,
  DashboardNavItem,
  DashboardShell,
  ErrorState,
  LoadingSkeleton,
  StatusBadge,
  ToastProvider,
  useToast,
} from "@/components/dashboard";
import {
  ActivityRecord,
  CinemaProfile,
  DiningTableRecord,
  EventRecord,
  getVerticalLabels,
  MenuItemRecord,
  MovieShowRecord,
  MovieSummary,
  PartnerAnalytics,
  PartnerBookingItem,
  PartnerDocument,
  PartnerFinancials,
  PartnerNotificationRecord,
  PartnerProfile,
  PartnerTabId,
  ReservationRecord,
  RestaurantProfile,
  ScreenRecord,
  SportsVenueRecord,
  PartnerBookingsView,
  PartnerFinancialsView,
  PartnerListingsView,
  PartnerNotificationsView,
  PartnerOnboardingRegistration,
  PartnerOverviewView,
  PartnerQrScannerView,
  PartnerSchedulesView,
  PartnerSettingsView,
  PartnerStatusGateView,
  PartnerUnauthenticatedGate,
} from "@/components/partner";

const BOOKING_PAGE_SIZE = 15;

const VALID_TABS: PartnerTabId[] = [
  "overview",
  "listings",
  "schedules",
  "bookings",
  "scanner",
  "financials",
  "notifications",
  "settings",
];

function PartnerConsoleInner() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const [activeTab, setActiveTab] = useState<PartnerTabId>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [partnerProfile, setPartnerProfile] = useState<PartnerProfile | null>(null);
  const [documents, setDocuments] = useState<PartnerDocument[]>([]);
  const [analytics, setAnalytics] = useState<PartnerAnalytics | null>(null);
  const [financials, setFinancials] = useState<PartnerFinancials | null>(null);
  const [notifications, setNotifications] = useState<PartnerNotificationRecord[]>([]);

  // Bookings paginated state
  const [bookings, setBookings] = useState<PartnerBookingItem[]>([]);
  const [bookingsTotal, setBookingsTotal] = useState(0);
  const [bookingsPage, setBookingsPage] = useState(1);
  const [bookingsLoading, setBookingsLoading] = useState(false);
  const [bookingSearch, setBookingSearch] = useState("");
  const [bookingStatusFilter, setBookingStatusFilter] = useState("");
  const [bookingStartDate, setBookingStartDate] = useState("");
  const [bookingEndDate, setBookingEndDate] = useState("");

  // Vertical-specific state
  const [restaurantProfile, setRestaurantProfile] =
    useState<RestaurantProfile | null>(null);
  const [menus, setMenus] = useState<MenuItemRecord[]>([]);
  const [tables, setTables] = useState<DiningTableRecord[]>([]);
  const [reservations, setReservations] = useState<ReservationRecord[]>([]);

  const [cinemaProfile, setCinemaProfile] = useState<CinemaProfile | null>(null);
  const [screens, setScreens] = useState<ScreenRecord[]>([]);
  const [shows, setShows] = useState<MovieShowRecord[]>([]);
  const [movies, setMovies] = useState<MovieSummary[]>([]);

  const [events, setEvents] = useState<EventRecord[]>([]);
  const [venues, setVenues] = useState<SportsVenueRecord[]>([]);
  const [activities, setActivities] = useState<ActivityRecord[]>([]);

  // Read optional ?tab=... param safely on client mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    const param = new URLSearchParams(window.location.search).get("tab");
    if (param && VALID_TABS.includes(param as PartnerTabId)) {
      setActiveTab(param as PartnerTabId);
    }
  }, []);

  const handleTabChange = useCallback((tabId: string) => {
    const clean = tabId as PartnerTabId;
    setActiveTab(clean);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", clean);
      window.history.replaceState({}, "", url.toString());
    }
  }, []);

  const loadVerticalData = useCallback(async (partnerType: string) => {
    try {
      if (partnerType === "RESTAURANT") {
        const [rProf, rMenu, rTbl, rRes] = await Promise.all([
          apiRequest<RestaurantProfile>("/partners/restaurant/profile").catch(
            () => null
          ),
          apiRequest<MenuItemRecord[]>("/partners/restaurant/menus").catch(
            () => []
          ),
          apiRequest<DiningTableRecord[]>("/partners/restaurant/tables").catch(
            () => []
          ),
          apiRequest<ReservationRecord[]>(
            "/partners/restaurant/reservations"
          ).catch(() => []),
        ]);
        setRestaurantProfile(rProf);
        setMenus(rMenu || []);
        setTables(rTbl || []);
        setReservations(rRes || []);
      } else if (partnerType === "CINEMA") {
        const [cProf, cScr, cShw, cMov] = await Promise.all([
          apiRequest<CinemaProfile>("/partners/cinema/profile").catch(() => null),
          apiRequest<ScreenRecord[]>("/partners/cinema/screens").catch(() => []),
          apiRequest<MovieShowRecord[]>("/partners/cinema/shows").catch(() => []),
          apiRequest<MovieSummary[]>("/partners/cinema/movies").catch(() => []),
        ]);
        setCinemaProfile(cProf);
        setScreens(cScr || []);
        setShows(cShw || []);
        setMovies(cMov || []);
      } else if (partnerType === "EVENT") {
        const evList = await apiRequest<EventRecord[]>("/partners/events").catch(
          () => []
        );
        setEvents(evList || []);
      } else if (partnerType === "SPORTS" || partnerType === "ACTIVITIES") {
        const [vList, aList] = await Promise.all([
          apiRequest<SportsVenueRecord[]>("/partners/sports/venues").catch(
            () => []
          ),
          apiRequest<ActivityRecord[]>("/partners/activities").catch(() => []),
        ]);
        setVenues(vList || []);
        setActivities(aList || []);
      }
    } catch {
      // handled per section cleanly
    }
  }, []);

  const loadBookings = useCallback(
    async (targetPage = bookingsPage) => {
      setBookingsLoading(true);
      try {
        const params = new URLSearchParams();
        params.set("page", String(targetPage));
        params.set("page_size", String(BOOKING_PAGE_SIZE));
        if (bookingSearch.trim()) params.set("search", bookingSearch.trim());
        if (bookingStatusFilter) params.set("status", bookingStatusFilter);
        if (bookingStartDate) params.set("start_date", bookingStartDate);
        if (bookingEndDate) params.set("end_date", bookingEndDate);

        const res = await apiRequest<{
          total: number;
          page: number;
          page_size: number;
          bookings: PartnerBookingItem[];
        }>(`/partners/bookings?${params.toString()}`);
        setBookings(res.bookings || []);
        setBookingsTotal(res.total || 0);
      } catch (err: any) {
        toast.error("Unable to fetch bookings", err.message || "");
      } finally {
        setBookingsLoading(false);
      }
    },
    [
      bookingsPage,
      bookingSearch,
      bookingStatusFilter,
      bookingStartDate,
      bookingEndDate,
      toast,
    ]
  );

  const loadInitialData = useCallback(async () => {
    if (!user) return;
    setFetchError(null);
    try {
      const profile = await apiRequest<PartnerProfile>("/partners/profile");
      setPartnerProfile(profile);

      const docs = await apiRequest<PartnerDocument[]>("/partners/documents").catch(
        () => []
      );
      setDocuments(docs || []);

      if (profile.status !== "APPROVED") {
        return;
      }

      const [anl, fin, ntf] = await Promise.all([
        apiRequest<PartnerAnalytics>("/partners/analytics").catch(() => null),
        apiRequest<PartnerFinancials>("/partners/financials").catch(() => null),
        apiRequest<PartnerNotificationRecord[]>("/partners/notifications").catch(
          () => []
        ),
      ]);

      setAnalytics(anl);
      setFinancials(fin);
      setNotifications(ntf || []);

      await Promise.all([
        loadVerticalData(profile.partner_type),
        loadBookings(1),
      ]);
    } catch (err: any) {
      const msgLower = String(err?.message || "").toLowerCase();
      if (
        err.status === 404 ||
        (err.status === 403 &&
          !msgLower.includes("deactivated") &&
          !msgLower.includes("suspended"))
      ) {
        setPartnerProfile(null);
      } else {
        setFetchError(err.message || "Unable to load Partner Portal.");
      }
    } finally {
      setLoading(false);
    }
  }, [user, loadVerticalData]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!authLoading) {
      if (user) {
        loadInitialData();
      } else {
        setLoading(false);
      }
    }
  }, [authLoading, user, loadInitialData]);

  // Refetch bookings when filter/page changes (only if approved partner)
  useEffect(() => {
    if (partnerProfile?.status === "APPROVED") {
      const timer = setTimeout(() => {
        loadBookings(bookingsPage);
      }, 220);
      return () => clearTimeout(timer);
    }
  }, [
    partnerProfile?.status,
    bookingsPage,
    bookingSearch,
    bookingStatusFilter,
    bookingStartDate,
    bookingEndDate,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadInitialData();
    setRefreshing(false);
    toast.info("Console synced with live backend");
  };

  const handleMarkOneRead = async (id: number | string) => {
    try {
      await apiRequest(`/partners/notifications/${id}/read`, {
        method: "PUT",
      });
      setNotifications((prev) =>
        prev.map((n) => (String(n.id) === String(id) ? { ...n, is_read: true } : n))
      );
    } catch {
      // ignore transient
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await apiRequest("/partners/notifications/read-all", { method: "PUT" });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      toast.success("All notifications marked as read");
    } catch (err: any) {
      toast.error("Failed to update notifications", err.message || "");
    }
  };

  if (authLoading || loading) {
    return (
      <DashboardShell title="Partner Portal" portalBadge="PARTNER" hasSidebar={false}>
        <LoadingSkeleton showSidebar />
      </DashboardShell>
    );
  }

  if (!user) {
    return (
      <DashboardShell title="Partner Portal" portalBadge="PARTNER" hasSidebar={false}>
        <PartnerUnauthenticatedGate
          onGoToLogin={() => router.push("/login?redirect=/partner")}
        />
      </DashboardShell>
    );
  }

  if (fetchError && !partnerProfile) {
    return (
      <DashboardShell title="Partner Portal" portalBadge="PARTNER" hasSidebar={false}>
        <div className="py-12">
          <ErrorState
            title="Unable to connect to Partner Console"
            description={fetchError}
            onRetry={loadInitialData}
          />
        </div>
      </DashboardShell>
    );
  }

  // Non-partner logged-in user -> Onboarding Form
  if (!partnerProfile) {
    return (
      <DashboardShell title="Partner Onboarding" portalBadge="ONBOARDING" hasSidebar={false}>
        <PartnerOnboardingRegistration
          userEmail={user.email}
          userPhone={user.phone}
          onSuccess={loadInitialData}
        />
      </DashboardShell>
    );
  }

  // Non-approved gates (PENDING_APPROVAL, PENDING_VERIFICATION, REJECTED, SUSPENDED)
  if (partnerProfile.status !== "APPROVED") {
    return (
      <DashboardShell
        title={partnerProfile.business_name}
        portalBadge={partnerProfile.status.replace(/_/g, " ")}
        hasSidebar={false}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      >
        <PartnerStatusGateView
          partnerProfile={partnerProfile}
          documents={documents}
          onDocumentsUpdated={loadInitialData}
        />
      </DashboardShell>
    );
  }

  const verticalMeta = getVerticalLabels(partnerProfile.partner_type);
  const unreadNotifs = notifications.filter((n) => !n.is_read).length;

  const navItems: DashboardNavItem[] = [
    {
      id: "overview",
      label: "Overview",
      icon: <LayoutDashboard className="w-4 h-4" />,
      section: "Operations",
    },
    {
      id: "listings",
      label: "Listings & Catalog",
      icon: <Layers className="w-4 h-4" />,
      section: "Operations",
    },
    {
      id: "schedules",
      label: verticalMeta.scheduleTitle,
      icon: <CalendarClock className="w-4 h-4" />,
      section: "Operations",
    },
    {
      id: "bookings",
      label: "Bookings",
      icon: <Ticket className="w-4 h-4" />,
      badge: analytics?.pending_bookings || 0,
      section: "Operations",
    },
    {
      // Exact E2E selector match: aside button:has-text("Gate QR Scanner")
      id: "scanner",
      label: "Gate QR Scanner",
      icon: <QrCode className="w-4 h-4" />,
      section: "Operations",
    },
    {
      // Exact E2E selector match: aside button:has-text("Financials & Payouts")
      id: "financials",
      label: "Financials & Payouts",
      icon: <IndianRupee className="w-4 h-4" />,
      section: "Finance & Admin",
    },
    {
      id: "notifications",
      label: "Notifications",
      icon: <Bell className="w-4 h-4" />,
      badge: unreadNotifs,
      section: "Finance & Admin",
    },
    {
      id: "settings",
      label: "Profile & KYC",
      icon: <Settings className="w-4 h-4" />,
      section: "Finance & Admin",
    },
  ];

  const activeNavObj = navItems.find((item) => item.id === activeTab);

  return (
    <DashboardShell
      title={partnerProfile.business_name}
      subtitle={verticalMeta.badge}
      portalBadge="PARTNER"
      navItems={navItems}
      activeTab={activeTab}
      onTabChange={handleTabChange}
      onRefresh={handleRefresh}
      refreshing={refreshing}
      notifications={notifications}
      onMarkAllNotificationsRead={handleMarkAllRead}
      onMarkNotificationRead={handleMarkOneRead}
      onViewAllNotifications={() => handleTabChange("notifications")}
      headerIdentity={
        <div className="rounded-xl bg-surface-2/85 border border-subtle p-3 space-y-2 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-primary truncate">
              {partnerProfile.business_name}
            </span>
            <StatusBadge status={partnerProfile.status} size="sm" />
          </div>
          <div className="flex items-center justify-between text-[11px] text-muted">
            <span>{partnerProfile.partner_type}</span>
            <span className="font-mono text-console-300">
              Fee {(partnerProfile.commission_rate * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      }
      sidebarFooter={
        <div className="text-[11px] text-muted space-y-1">
          <div className="font-semibold text-secondary">Single-Tenant Isolation</div>
          <p className="leading-snug">
            All inventory, QR scans, and ledger settlements are strictly isolated to Partner #{partnerProfile.id}.
          </p>
        </div>
      }
    >
      <div className="space-y-5">
        <DashboardBreadcrumbs
          items={[
            { label: "Partner Console", onClick: () => handleTabChange("overview") },
            { label: activeNavObj?.label || "Overview" },
          ]}
        />

        {activeTab === "overview" && (
          <PartnerOverviewView
            partnerProfile={partnerProfile}
            analytics={analytics}
            notifications={notifications}
            onNavigate={handleTabChange}
          />
        )}

        {activeTab === "listings" && (
          <PartnerListingsView
            partnerProfile={partnerProfile}
            onNavigate={handleTabChange}
            restaurantProfile={restaurantProfile}
            menus={menus}
            tables={tables}
            cinemaProfile={cinemaProfile}
            screens={screens}
            shows={shows}
            movies={movies}
            events={events}
            venues={venues}
            activities={activities}
            onReloadVertical={() => loadVerticalData(partnerProfile.partner_type)}
          />
        )}

        {activeTab === "schedules" && (
          <PartnerSchedulesView
            partnerProfile={partnerProfile}
            reservations={reservations}
            shows={shows}
            screens={screens}
            movies={movies}
            events={events}
            activities={activities}
            onReloadVertical={() => loadVerticalData(partnerProfile.partner_type)}
          />
        )}

        {activeTab === "bookings" && (
          <PartnerBookingsView
            bookings={bookings}
            total={bookingsTotal}
            page={bookingsPage}
            pageSize={BOOKING_PAGE_SIZE}
            loading={bookingsLoading}
            search={bookingSearch}
            statusFilter={bookingStatusFilter}
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
            financials={financials}
          />
        )}

        {activeTab === "scanner" && (
          <PartnerQrScannerView
            businessName={partnerProfile.business_name}
            onVerified={loadInitialData}
          />
        )}

        {activeTab === "financials" && (
          <PartnerFinancialsView financials={financials} />
        )}

        {activeTab === "notifications" && (
          <PartnerNotificationsView
            notifications={notifications}
            onMarkOneRead={handleMarkOneRead}
            onMarkAllRead={handleMarkAllRead}
          />
        )}

        {activeTab === "settings" && (
          <PartnerSettingsView
            partnerProfile={partnerProfile}
            documents={documents}
            onReloadProfile={loadInitialData}
          />
        )}
      </div>
    </DashboardShell>
  );
}

export default function PartnerDashboardPage() {
  return (
    <ToastProvider>
      <PartnerConsoleInner />
    </ToastProvider>
  );
}
