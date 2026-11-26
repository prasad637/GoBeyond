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
  ShieldCheck,
  Ticket,
  User as UserIcon,
  X,
} from "lucide-react";
import { cn } from "@/lib/cn";

export interface ConsoleNavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: number | string;
}

export interface ConsoleShellProps {
  title: string;
  subtitle?: string;
  portalBadge?: string;
  navItems?: ConsoleNavItem[];
  activeTab?: string;
  onTabChange?: (tabId: string) => void;
  headerIdentity?: React.ReactNode;
  sidebarFooter?: React.ReactNode;
  headerActions?: React.ReactNode;
  hasSidebar?: boolean;
  children: React.ReactNode;
}

export default function ConsoleShell({
  title,
  subtitle,
  portalBadge = "CONSOLE",
  navItems = [],
  activeTab,
  onTabChange,
  headerIdentity,
  sidebarFooter,
  headerActions,
  hasSidebar = true,
  children,
}: ConsoleShellProps) {
  const { user, logout } = useAuth();
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
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

  useEffect(() => {
    if (!isMobileDrawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsMobileDrawerOpen(false);
    };
    window.addEventListener("keydown", handleEsc);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", handleEsc);
    };
  }, [isMobileDrawerOpen]);

  const userRoles = user?.roles || [];
  const isAdmin = userRoles.includes("super_admin");
  const isPartner = userRoles.some((r) => r.startsWith("partner_"));
  const activeNavItem = navItems.find((item) => item.id === activeTab);

  return (
    <div className="min-h-screen flex flex-col bg-canvas text-primary">
      {/* Dedicated Console Topbar */}
      <header className="sticky top-0 z-30 h-14 bg-surface/95 backdrop-blur-md border-b border-subtle px-3 sm:px-6 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          {hasSidebar && navItems.length > 0 && (
            <button
              type="button"
              onClick={() => setIsMobileDrawerOpen(true)}
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

          <span className="px-2 py-0.5 rounded-full bg-console-500/12 border border-console-500/25 text-console-300 text-[11px] font-semibold tracking-wider uppercase shrink-0">
            {portalBadge}
          </span>

          {activeNavItem && (
            <span className="lg:hidden text-xs font-medium text-secondary truncate">
              · {activeNavItem.label}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <Link
            href="/"
            className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs font-medium text-secondary hover:text-primary transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Customer App</span>
          </Link>

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

      {/* Mobile/Tablet Quick Scrollable Tab Strip (<lg) */}
      {hasSidebar && navItems.length > 0 && (
        <div className="lg:hidden bg-surface/60 border-b border-subtle px-3 py-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {navItems.map((item) => {
            const isActive = item.id === activeTab;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onTabChange?.(item.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap border transition-colors shrink-0",
                  isActive
                    ? "bg-console-600 border-console-500 text-white font-semibold"
                    : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                )}
              >
                <span className="shrink-0 flex items-center">{item.icon}</span>
                <span>{item.label}</span>
                {item.badge !== undefined && Number(item.badge) > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-brand-500 text-white text-[10px] font-bold leading-none">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Main Console Workspace */}
      <div className="flex-1 flex min-w-0">
        {hasSidebar && navItems.length > 0 && (
          <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 bg-surface border-r border-subtle p-5 justify-between gap-6">
            <div className="space-y-6">
              <div className="space-y-1">
                <h2 className="font-display text-base font-bold text-primary tracking-tight">
                  {title}
                </h2>
                {subtitle ? (
                  <p className="text-xs text-muted leading-snug">{subtitle}</p>
                ) : null}
              </div>

              {headerIdentity}

              <nav aria-label={`${title} navigation`} className="space-y-1 text-xs font-medium">
                {navItems.map((item) => {
                  const isActive = item.id === activeTab;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onTabChange?.(item.id)}
                      className={cn(
                        "w-full flex items-center justify-between gap-2.5 px-3 py-2.5 rounded-xl transition-colors text-left",
                        isActive
                          ? "bg-console-600/20 text-console-200 border border-console-500/30 font-semibold"
                          : "text-secondary hover:text-primary hover:bg-surface-2 border border-transparent"
                      )}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <span className={cn("shrink-0", isActive ? "text-console-400" : "text-muted")}>
                          {item.icon}
                        </span>
                        <span className="truncate">{item.label}</span>
                      </span>

                      {item.badge !== undefined && Number(item.badge) > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-bold tabular-nums-lining shrink-0">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            {sidebarFooter ? (
              <div className="pt-5 border-t border-subtle">{sidebarFooter}</div>
            ) : null}
          </aside>
        )}

        <div className="flex-1 min-w-0 bg-canvas">{children}</div>
      </div>

      {/* Mobile/Tablet Slide-Over Console Drawer */}
      {hasSidebar && navItems.length > 0 && isMobileDrawerOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden flex"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setIsMobileDrawerOpen(false);
          }}
        >
          <div
            aria-hidden="true"
            onClick={() => setIsMobileDrawerOpen(false)}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm animate-fadeIn"
          />
          <div className="relative z-10 w-72 max-w-[85vw] bg-surface border-r border-strong h-full p-5 flex flex-col justify-between overflow-y-auto shadow-modal">
            <div className="space-y-5">
              <div className="flex items-center justify-between pb-3 border-b border-subtle">
                <div>
                  <div className="font-display font-bold text-sm text-primary">
                    {title}
                  </div>
                  {subtitle && (
                    <div className="text-[11px] text-muted mt-0.5">{subtitle}</div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setIsMobileDrawerOpen(false)}
                  aria-label="Close console navigation"
                  className="p-2 rounded-lg text-secondary hover:text-primary hover:bg-surface-2"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {headerIdentity}

              <div className="space-y-1 text-xs font-medium">
                {navItems.map((item) => {
                  const isActive = item.id === activeTab;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        onTabChange?.(item.id);
                        setIsMobileDrawerOpen(false);
                      }}
                      className={cn(
                        "w-full flex items-center justify-between gap-2.5 px-3 py-2.5 rounded-xl transition-colors text-left",
                        isActive
                          ? "bg-console-600/20 text-console-200 border border-console-500/30 font-semibold"
                          : "text-secondary hover:text-primary hover:bg-surface-2 border border-transparent"
                      )}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <span className="shrink-0">{item.icon}</span>
                        <span className="truncate">{item.label}</span>
                      </span>
                      {item.badge !== undefined && Number(item.badge) > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-bold">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="pt-4 border-t border-subtle space-y-3">
              {sidebarFooter}
              <Link
                href="/"
                onClick={() => setIsMobileDrawerOpen(false)}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-surface-2 border border-subtle text-xs font-semibold text-primary"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Customer App</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

