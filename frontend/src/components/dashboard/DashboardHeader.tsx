"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import {
  ArrowLeft,
  ChevronDown,
  Compass,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  ShieldCheck,
  Ticket,
  User as UserIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import {
  ConsoleNotificationItem,
  NotificationPanel,
} from "./NotificationPanel";

export interface DashboardHeaderProps {
  portalBadge?: string;
  activeSectionLabel?: string;
  hasSidebar?: boolean;
  onOpenMobileDrawer?: () => void;
  onRefresh?: () => void;
  refreshing?: boolean;
  notifications?: ConsoleNotificationItem[];
  onMarkAllNotificationsRead?: () => void;
  onMarkNotificationRead?: (id: number | string) => void;
  onViewAllNotifications?: () => void;
  headerActions?: React.ReactNode;
}

/**
 * Shared console top bar.
 * IMPORTANT: Inside <header>, ONLY the authenticated user profile dropdown wrapper
 * may use `<div className="relative">` so `header div.relative > button` reliably
 * targets the account menu in automated E2E flows.
 */
export function DashboardHeader({
  portalBadge = "CONSOLE",
  activeSectionLabel,
  hasSidebar = true,
  onOpenMobileDrawer,
  onRefresh,
  refreshing = false,
  notifications,
  onMarkAllNotificationsRead,
  onMarkNotificationRead,
  onViewAllNotifications,
  headerActions,
}: DashboardHeaderProps) {
  const { user, logout } = useAuth();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isProfileMenuOpen) return;
    const handleOutside = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setIsProfileMenuOpen(false);
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsProfileMenuOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    window.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      window.removeEventListener("keydown", handleEsc);
    };
  }, [isProfileMenuOpen]);

  const userRoles = user?.roles || [];
  const isAdmin = userRoles.includes("super_admin");
  const isPartner = userRoles.some((r) => r.startsWith("partner_"));

  return (
    <header className="sticky top-0 z-30 h-14 bg-surface/95 backdrop-blur-md border-b border-subtle px-3 sm:px-6 flex items-center justify-between gap-2 w-full">
      <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
        {hasSidebar && onOpenMobileDrawer && (
          <button
            type="button"
            onClick={onOpenMobileDrawer}
            aria-label="Open console navigation"
            className="lg:hidden w-9 h-9 rounded-lg bg-surface-2 border border-subtle hover:border-strong text-secondary hover:text-primary flex items-center justify-center transition-colors shrink-0"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}

        <Link href="/" className="flex items-center gap-2 min-w-0 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-console-600 flex items-center justify-center text-white font-display font-bold text-xs shadow-console-sm">
            GB
          </span>
          <span className="font-display font-bold text-sm tracking-wide text-primary hidden sm:inline">
            GO<span className="text-brand-500">BEYOND</span>
          </span>
        </Link>

        <span className="px-2 py-0.5 rounded-full bg-console-500/12 border border-console-500/25 text-console-300 text-[10px] sm:text-[11px] font-semibold tracking-wider uppercase shrink-0">
          {portalBadge}
        </span>

        {activeSectionLabel && (
          <span className="lg:hidden text-xs font-medium text-secondary truncate min-w-0">
            · {activeSectionLabel}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        <Link
          href="/"
          className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs font-medium text-secondary hover:text-primary transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Customer App</span>
        </Link>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh console data"
            title="Refresh data"
            className="w-9 h-9 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle hover:border-strong text-secondary hover:text-primary flex items-center justify-center transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
          </button>
        )}

        {notifications && (
          <NotificationPanel
            notifications={notifications}
            onMarkAllRead={onMarkAllNotificationsRead}
            onMarkOneRead={onMarkNotificationRead}
            onViewAll={onViewAllNotifications}
          />
        )}

        {headerActions}

        {user ? (
          <div ref={profileRef} className="relative">
            <button
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              aria-expanded={isProfileMenuOpen}
              aria-haspopup="menu"
              className="flex items-center gap-2 p-1 sm:pr-2.5 rounded-xl bg-surface-2 border border-subtle hover:border-strong transition-colors"
            >
              <span className="w-7 h-7 rounded-lg bg-console-600 flex items-center justify-center text-xs font-bold text-white uppercase shrink-0">
                {user.full_name?.charAt(0) || "U"}
              </span>
              <span className="text-xs font-medium text-primary hidden sm:block max-w-[110px] truncate">
                {user.full_name}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-muted hidden sm:block" />
            </button>

            {isProfileMenuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-56 rounded-2xl bg-surface border border-strong shadow-modal py-2 z-50 text-xs text-secondary animate-fadeIn"
              >
                <div className="px-4 py-2.5 border-b border-subtle">
                  <div className="font-semibold text-primary truncate">
                    {user.full_name}
                  </div>
                  <div className="text-muted truncate mt-0.5">{user.email}</div>
                </div>

                <Link
                  href="/"
                  role="menuitem"
                  onClick={() => setIsProfileMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                >
                  <Compass className="w-4 h-4 text-brand-400" />
                  <span>Customer Discovery</span>
                </Link>

                <Link
                  href="/profile"
                  role="menuitem"
                  onClick={() => setIsProfileMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                >
                  <UserIcon className="w-4 h-4 text-brand-400" />
                  <span>My Profile</span>
                </Link>

                <Link
                  href="/bookings"
                  role="menuitem"
                  onClick={() => setIsProfileMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 hover:text-primary transition-colors"
                >
                  <Ticket className="w-4 h-4 text-brand-400" />
                  <span>My Bookings</span>
                </Link>

                {isPartner && (
                  <Link
                    href="/partner"
                    role="menuitem"
                    onClick={() => setIsProfileMenuOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-surface-2 text-console-300 transition-colors"
                  >
                    <LayoutDashboard className="w-4 h-4" />
                    <span>Partner Console</span>
                  </Link>
                )}

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
          <Link
            href="/login"
            className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold text-white transition-colors whitespace-nowrap"
          >
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
}

