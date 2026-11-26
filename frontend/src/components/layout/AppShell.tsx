"use client";

import React from "react";
import { usePathname } from "next/navigation";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import MobileBottomNav from "@/components/layout/MobileBottomNav";
import AuthModal from "@/components/auth/AuthModal";
import LocationSelectorModal from "@/components/location/LocationSelectorModal";

export interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname() || "/";

  const isConsoleRoute =
    pathname.startsWith("/partner") || pathname.startsWith("/admin");

  return (
    <div className="min-h-screen flex flex-col bg-canvas text-primary overflow-x-clip">
      {!isConsoleRoute && <Navbar />}

      {isConsoleRoute ? (
        <div className="flex-1 w-full min-w-0 bg-canvas text-primary">
          {children}
        </div>
      ) : (
        <main className="flex-1 w-full min-w-0 bg-canvas text-primary pb-20 md:pb-0">
          {children}
        </main>
      )}

      {!isConsoleRoute && (
        <>
          <Footer />
          <MobileBottomNav />
        </>
      )}

      <AuthModal />
      <LocationSelectorModal />
    </div>
  );
}

