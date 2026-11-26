"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLocation } from "@/context/LocationContext";
import { apiRequest } from "@/lib/api";
import {
  NavbarSearch,
  MobileSearchModal,
} from "@/components/discovery/NavbarSearch";
import {
  Film,
  UtensilsCrossed,
  CalendarDays,
  Trophy,
  Compass,
  MapPin,
  Search,
  User as UserIcon,
  LogOut,
  ChevronDown,
  LayoutDashboard,
  ShieldCheck,
  Ticket,
  Menu,
  X,
  Bell,
} from "lucide-react";
import { cn } from "@/lib/cn";

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { selectedCity, selectedLocality, openLocationModal } = useLocation();

  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
  const [isSportsVertical, setIsSportsVertical] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const profileMenuRef = useRef<HTMLDivElement>(null);

  // Close menus on route transitions & sync vertical context from URL search params
  useEffect(() => {
    setIsProfileMenuOpen(false);
    setIsMobileMenuOpen(false);
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setIsSportsVertical(
        pathname.startsWith("/activities/") && params.get("vertical") === "sports"
      );
    }
  }, [pathname]);

  // Listen for MobileBottomNav search button events
  useEffect(() => {
    const handleOpenSearch = () => {
      setIsMobileMenuOpen(false);
      setIsMobileSearchOpen(true);
    };
    window.addEventListener("gobeyond:open-search", handleOpenSearch);
    return () => window.removeEventListener("gobeyond:open-search", handleOpenSearch);
  }, []);

  // Close profile dropdown on outside click or Escape
  useEffect(() => {
    if (!isProfileMenuOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        profileMenuRef.current &&
        !profileMenuRef.current.contains(event.target as Node)
      ) {
        setIsProfileMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsProfileMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isProfileMenuOpen]);

  // Poll unread notifications count cleanly when authenticated
  useEffect(() => {
    if (!user) {
      setUnreadCount(0);
      return;
    }
    const fetchUnread = async () => {
      try {
        const res = await apiRequest<{ unread_count: number }>(
          "/notifications/unread-count"
        );
        if (res && typeof res.unread_count === "number") {
          setUnreadCount(res.unread_count);
        }
      } catch {
        // Silent background check
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, [user, pathname]);

  const categories = [
    { name: "Movies", href: "/movies", icon: Film },
    { name: "Dining", href: "/dining", icon: UtensilsCrossed },
    { name: "Events", href: "/events", icon: CalendarDays },
    { name: "Sports", href: "/sports", icon: Trophy },
    { name: "Activities", href: "/activities", icon: Compass },
  ];

  const userRoles = user?.roles || [];
  const isAdmin = userRoles.includes("super_admin");
  const isPartner = userRoles.some((r) => r.startsWith("partner_"));

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-canvas/90 backdrop-blur-md border-b border-subtle">
        <div className="max-w-editorial mx-auto px-2.5 sm:px-6 lg:px-8">
          {/* Primary Unified Top Row */}
          <div className="flex items-center justify-between gap-1.5 sm:gap-3 h-14 md:h-16">
            {/* Brand & Location */}
            <div className="flex items-center gap-1.5 sm:gap-3.5 min-w-0">
              <Link href="/" className="flex items-center gap-1.5 sm:gap-2 group shrink-0">
                <span className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg sm:rounded-xl bg-brand-500 flex items-center justify-center shadow-brand-sm group-hover:bg-brand-600 transition-colors">
                  <Compass className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </span>
                <div className="flex flex-col">
                  <span className="font-display font-extrabold text-sm sm:text-lg tracking-wide text-primary leading-none">
                    GO<span className="text-brand-500">BEYOND</span>
                  </span>
                  <span className="text-[10px] tracking-[0.14em] text-muted font-medium mt-0.5 hidden xl:block leading-none">
                    DISCOVER. BOOK. EXPERIENCE.
                  </span>
                </div>
              </Link>

              {/* Location Selector Pill */}
              <button
                type="button"
                onClick={openLocationModal}
                aria-label={`Change location (${
                  selectedLocality
                    ? `${selectedLocality.name}, ${selectedCity}`
                    : selectedCity
                })`}
                title={
                  selectedLocality
                    ? `${selectedLocality.name}, ${selectedCity}`
                    : selectedCity
                }
                className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 sm:py-1.5 rounded-full bg-surface-2 hover:bg-surface-3 border border-subtle hover:border-strong text-[11px] sm:text-xs font-medium text-secondary hover:text-primary transition-colors min-w-0 max-w-[140px] sm:max-w-[220px]"
              >
                <MapPin className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-brand-500 shrink-0" />
                <span className="truncate sm:hidden">
                  {selectedLocality ? selectedLocality.name : selectedCity}
                </span>
                <span className="hidden sm:inline truncate">
                  {selectedLocality
                    ? `${selectedLocality.name}, ${selectedCity}`
                    : selectedCity}
                </span>
                <ChevronDown className="w-3 h-3 text-muted shrink-0" />
              </button>
            </div>

            {/* Interactive Global Search (Desktop & Tablet >=md) */}
            <div className="hidden md:flex flex-1 min-w-0 max-w-md lg:max-w-lg mx-2 lg:mx-4">
              <NavbarSearch />
            </div>

            {/* Right Utility & Auth Actions */}
            <div className="flex items-center gap-1 sm:gap-2.5 shrink-0">
              {/* Mobile Search Modal Trigger (hidden for signed-in <sm where BottomNav & Drawer host Search) */}
              <button
                type="button"
                onClick={() => setIsMobileSearchOpen(true)}
                aria-label="Open global search"
                className={cn(
                  user ? "hidden sm:flex md:hidden" : "flex md:hidden",
                  "w-8 h-8 rounded-lg bg-surface-2 border border-subtle hover:border-strong items-center justify-center text-secondary hover:text-primary transition-colors"
                )}
              >
                <Search className="w-4 h-4" />
              </button>

              {/* Admin / Partner Role Quick Pills (Desktop) */}
              {isAdmin && (
                <Link
                  href="/admin"
                  className="hidden lg:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-300 text-xs font-semibold hover:bg-amber-500/20 transition-colors whitespace-nowrap"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Super Admin</span>
                </Link>
              )}

              {isPartner && !isAdmin && (
                <Link
                  href="/partner"
                  className="hidden lg:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-console-500/12 border border-console-500/25 text-console-300 text-xs font-semibold hover:bg-console-500/20 transition-colors whitespace-nowrap"
                >
                  <LayoutDashboard className="w-3.5 h-3.5" />
                  <span>Partner Portal</span>
                </Link>
              )}

              {/* Notifications Bell */}
              {user && (
                <Link
                  href="/notifications"
                  className="relative w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-surface-2 border border-subtle hover:border-strong text-secondary hover:text-primary flex items-center justify-center transition-colors"
                  aria-label="Notifications & Alerts"
                  title="Notifications & Alerts"
                >
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-brand-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center tabular-nums-lining">
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                  )}
                </Link>
              )}

              {/* Authenticated User Profile Menu OR Guest Sign In */}
              {user ? (
                <div ref={profileMenuRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setIsProfileMenuOpen((prev) => !prev)}
                    aria-expanded={isProfileMenuOpen}
                    aria-haspopup="menu"
                    className="flex items-center gap-2 p-0.5 sm:p-1 sm:pr-2.5 rounded-xl bg-surface-2 border border-subtle hover:border-strong transition-colors"
                  >
                    <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center text-xs font-bold text-white uppercase shrink-0">
                      {user.full_name?.charAt(0) || "U"}
                    </div>
                    <span className="text-xs font-medium text-primary hidden sm:block max-w-[96px] truncate">
                      {user.full_name}
                    </span>
                    <ChevronDown className="w-3.5 h-3.5 text-muted hidden sm:block" />
                  </button>

                  {isProfileMenuOpen && (
                    <div
                      role="menu"
                      className="absolute right-0 mt-2 w-60 rounded-2xl bg-surface border border-strong shadow-modal py-2 z-50 text-xs text-secondary animate-fadeIn"
                    >
                      <div className="px-4 py-2.5 border-b border-subtle">
                        <div className="font-semibold text-primary truncate">
                          {user.full_name}
                        </div>
                        <div className="text-muted truncate mt-0.5">{user.email}</div>
                      </div>

                      <Link
                        href="/notifications"
                        role="menuitem"
                        onClick={() => setIsProfileMenuOpen(false)}
                        className="flex items-center justify-between px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                      >
                        <span className="flex items-center gap-2.5">
                          <Bell className="w-4 h-4 text-console-400" />
                          <span>Notifications & Alerts</span>
                        </span>
                        {unreadCount > 0 && (
                          <span className="px-1.5 py-0.5 rounded-full bg-brand-500/15 text-brand-400 text-[11px] font-bold tabular-nums-lining">
                            {unreadCount}
                          </span>
                        )}
                      </Link>

                      <Link
                        href="/profile"
                        role="menuitem"
                        onClick={() => setIsProfileMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                      >
                        <UserIcon className="w-4 h-4 text-brand-400" />
                        <span>My Profile & Preferences</span>
                      </Link>

                      <Link
                        href="/bookings"
                        role="menuitem"
                        onClick={() => setIsProfileMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                      >
                        <Ticket className="w-4 h-4 text-brand-400" />
                        <span>My Bookings & Passes</span>
                      </Link>

                      {isAdmin && (
                        <Link
                          href="/admin"
                          role="menuitem"
                          onClick={() => setIsProfileMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 text-amber-300 transition-colors"
                        >
                          <ShieldCheck className="w-4 h-4" />
                          <span>Admin Console</span>
                        </Link>
                      )}

                      {isPartner && (
                        <Link
                          href="/partner"
                          role="menuitem"
                          onClick={() => setIsProfileMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 text-console-300 transition-colors"
                        >
                          <LayoutDashboard className="w-4 h-4" />
                          <span>Partner Dashboard</span>
                        </Link>
                      )}

                      <div className="border-t border-subtle mt-1.5 pt-1.5">
                        <button
                          type="button"
                          role="menuitem"
                          onClick={() => {
                            setIsProfileMenuOpen(false);
                            logout();
                          }}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-red-400 hover:bg-red-500/10 transition-colors text-left"
                        >
                          <LogOut className="w-4 h-4" />
                          <span>Sign Out</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <Link
                    href="/login"
                    className="px-2 sm:px-3 py-1.5 rounded-lg text-[11px] sm:text-xs font-semibold text-primary sm:text-secondary hover:text-primary bg-surface-2 sm:bg-transparent border border-subtle sm:border-transparent hover:bg-surface-2 transition-colors whitespace-nowrap"
                  >
                    Sign In
                  </Link>
                  <Link
                    href="/register"
                    className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white shadow-brand-sm transition-colors whitespace-nowrap"
                  >
                    <UserIcon className="w-3.5 h-3.5" />
                    <span>Get Started</span>
                  </Link>
                </div>
              )}

              {/* Mobile Hamburger Drawer Toggle */}
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen((prev) => !prev)}
                aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={isMobileMenuOpen}
                className="md:hidden w-8 h-8 rounded-lg text-secondary hover:text-primary hover:bg-surface-2 border border-subtle flex items-center justify-center transition-colors"
              >
                {isMobileMenuOpen ? (
                  <X className="w-4 h-4 sm:w-5 sm:h-5" />
                ) : (
                  <Menu className="w-4 h-4 sm:w-5 sm:h-5" />
                )}
              </button>
            </div>
          </div>

          {/* Desktop Category Sub-Navigation Bar */}
          <nav
            aria-label="Entertainment verticals"
            className="hidden md:flex items-center gap-6 lg:gap-8 h-10 border-t border-subtle text-xs font-medium"
          >
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isActive =
                cat.href === "/sports"
                  ? pathname.startsWith("/sports") || isSportsVertical
                  : cat.href === "/activities"
                  ? pathname.startsWith("/activities") && !isSportsVertical
                  : pathname.startsWith(cat.href);
              return (
                <Link
                  key={cat.name}
                  href={cat.href}
                  className={cn(
                    "h-full inline-flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap",
                    isActive
                      ? "border-brand-500 text-primary font-semibold"
                      : "border-transparent text-secondary hover:text-primary hover:border-strong"
                  )}
                >
                  <Icon
                    className={cn(
                      "w-3.5 h-3.5",
                      isActive ? "text-brand-500" : "text-muted"
                    )}
                  />
                  <span>{cat.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* Mobile Drawer Menu */}
          {isMobileMenuOpen && (
            <div className="md:hidden py-4 border-t border-subtle space-y-3 animate-slideInTop">
              <button
                type="button"
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  setIsMobileSearchOpen(true);
                }}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-surface-2 border border-subtle text-sm text-secondary hover:text-primary transition-colors text-left"
              >
                <Search className="w-4 h-4 text-brand-400" />
                <span>Search movies, dining, events, turfs...</span>
              </button>

              <div className="grid grid-cols-2 gap-1.5">
                {categories.map((cat) => {
                  const Icon = cat.icon;
                  const isActive =
                    cat.href === "/sports"
                      ? pathname.startsWith("/sports") || isSportsVertical
                      : cat.href === "/activities"
                      ? pathname.startsWith("/activities") && !isSportsVertical
                      : pathname.startsWith(cat.href);
                  return (
                    <Link
                      key={cat.name}
                      href={cat.href}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium border transition-colors",
                        isActive
                          ? "bg-brand-500/12 border-brand-500/40 text-primary font-semibold"
                          : "bg-surface-2/60 border-subtle text-secondary hover:text-primary hover:bg-surface-2"
                      )}
                    >
                      <Icon className="w-4 h-4 text-brand-500 shrink-0" />
                      <span>{cat.name}</span>
                    </Link>
                  );
                })}
              </div>

              <div className="pt-2 border-t border-subtle space-y-1">
                {user ? (
                  <>
                    <Link
                      href="/profile"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                    >
                      <UserIcon className="w-4 h-4 text-brand-500" />
                      <span>My Account Profile</span>
                    </Link>
                    <Link
                      href="/bookings"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                    >
                      <Ticket className="w-4 h-4 text-brand-500" />
                      <span>My Bookings & Passes</span>
                    </Link>
                    <Link
                      href="/notifications"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="flex items-center justify-between px-3 py-2.5 rounded-xl text-sm text-secondary hover:bg-surface-2 hover:text-primary transition-colors"
                    >
                      <span className="flex items-center gap-3">
                        <Bell className="w-4 h-4 text-console-400" />
                        <span>Notifications</span>
                      </span>
                      {unreadCount > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-brand-500/15 text-brand-400 text-xs font-semibold tabular-nums-lining">
                          {unreadCount}
                        </span>
                      )}
                    </Link>
                    {isPartner && (
                      <Link
                        href="/partner"
                        onClick={() => setIsMobileMenuOpen(false)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-console-300 hover:bg-surface-2 transition-colors"
                      >
                        <LayoutDashboard className="w-4 h-4" />
                        <span>Partner Portal</span>
                      </Link>
                    )}
                    {isAdmin && (
                      <Link
                        href="/admin"
                        onClick={() => setIsMobileMenuOpen(false)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-amber-300 hover:bg-surface-2 transition-colors"
                      >
                        <ShieldCheck className="w-4 h-4" />
                        <span>Super Admin Console</span>
                      </Link>
                    )}
                  </>
                ) : (
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <Link
                      href="/login"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-surface-2 border border-subtle text-sm font-semibold text-primary"
                    >
                      <span>Sign In</span>
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-sm font-semibold text-white"
                    >
                      <span>Get Started</span>
                    </Link>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </header>

      <MobileSearchModal
        isOpen={isMobileSearchOpen}
        onClose={() => setIsMobileSearchOpen(false)}
      />
    </>
  );
}
