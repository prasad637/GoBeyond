"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Film, Search, Ticket, User as UserIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/cn";

export default function MobileBottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  const openMobileSearch = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("gobeyond:open-search"));
    }
  };

  const navItems = [
    {
      label: "Explore",
      href: "/",
      icon: Compass,
      isActive: pathname === "/",
    },
    {
      label: "Movies",
      href: "/movies",
      icon: Film,
      isActive: pathname.startsWith("/movies"),
    },
    {
      label: "Search",
      href: null,
      icon: Search,
      isActive: false,
      onClick: openMobileSearch,
    },
    {
      label: "Bookings",
      href: "/bookings",
      icon: Ticket,
      isActive: pathname.startsWith("/bookings"),
    },
    {
      label: user ? "Profile" : "Sign In",
      href: user ? "/profile" : "/login",
      icon: UserIcon,
      isActive: user
        ? pathname.startsWith("/profile") || pathname.startsWith("/notifications")
        : pathname === "/login" || pathname === "/register",
    },
  ];

  return (
    <nav
      aria-label="Mobile quick navigation"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface/95 backdrop-blur-md border-t border-subtle pb-[env(safe-area-inset-bottom)]"
    >
      <div className="grid grid-cols-5 h-16 max-w-md mx-auto px-1">
        {navItems.map((item) => {
          const Icon = item.icon;

          if (!item.href && item.onClick) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={item.onClick}
                className="flex flex-col items-center justify-center gap-1 text-secondary hover:text-primary active:text-brand-400 transition-colors"
              >
                <Icon className="w-5 h-5" aria-hidden="true" />
                <span className="text-[11px] font-medium leading-none">{item.label}</span>
              </button>
            );
          }

          return (
            <Link
              key={item.label}
              href={item.href!}
              className={cn(
                "flex flex-col items-center justify-center gap-1 transition-colors relative",
                item.isActive ? "text-brand-500 font-semibold" : "text-secondary hover:text-primary"
              )}
            >
              {item.isActive && (
                <span
                  aria-hidden="true"
                  className="absolute top-0 w-7 h-0.5 rounded-full bg-brand-500"
                />
              )}
              <Icon className="w-5 h-5" aria-hidden="true" />
              <span className="text-[11px] leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

