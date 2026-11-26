"use client";

import React, { useState } from "react";
import { DashboardHeader } from "./DashboardHeader";
import { DashboardMobileNav } from "./DashboardMobileNav";
import { DashboardNavItem, DashboardSidebar } from "./DashboardSidebar";
import { ConsoleNotificationItem } from "./NotificationPanel";

export interface DashboardShellProps {
  title: string;
  subtitle?: string;
  portalBadge?: string;
  navItems?: DashboardNavItem[];
  activeTab?: string;
  onTabChange?: (tabId: string) => void;
  hasSidebar?: boolean;
  headerIdentity?: React.ReactNode;
  sidebarFooter?: React.ReactNode;
  headerActions?: React.ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  notifications?: ConsoleNotificationItem[];
  onMarkAllNotificationsRead?: () => void;
  onMarkNotificationRead?: (id: number | string) => void;
  onViewAllNotifications?: () => void;
  children: React.ReactNode;
}

export function DashboardShell({
  title,
  subtitle,
  portalBadge = "CONSOLE",
  navItems = [],
  activeTab = "",
  onTabChange,
  hasSidebar = true,
  headerIdentity,
  sidebarFooter,
  headerActions,
  onRefresh,
  refreshing = false,
  notifications,
  onMarkAllNotificationsRead,
  onMarkNotificationRead,
  onViewAllNotifications,
  children,
}: DashboardShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const activeNavItem = navItems.find((item) => item.id === activeTab);
  const showNav = hasSidebar && navItems.length > 0 && Boolean(onTabChange);

  return (
    <div className="min-h-screen flex flex-col bg-canvas text-primary overflow-x-clip">
      <DashboardHeader
        portalBadge={portalBadge}
        activeSectionLabel={activeNavItem?.label}
        hasSidebar={showNav}
        onOpenMobileDrawer={() => setMobileDrawerOpen(true)}
        onRefresh={onRefresh}
        refreshing={refreshing}
        notifications={notifications}
        onMarkAllNotificationsRead={onMarkAllNotificationsRead}
        onMarkNotificationRead={onMarkNotificationRead}
        onViewAllNotifications={onViewAllNotifications}
        headerActions={headerActions}
      />

      {showNav && onTabChange && (
        <DashboardMobileNav
          title={title}
          subtitle={subtitle}
          navItems={navItems}
          activeTab={activeTab}
          onTabChange={onTabChange}
          drawerOpen={mobileDrawerOpen}
          onCloseDrawer={() => setMobileDrawerOpen(false)}
          headerIdentity={headerIdentity}
          footer={sidebarFooter}
        />
      )}

      <div className="flex-1 flex min-w-0 w-full">
        {showNav && onTabChange && (
          <DashboardSidebar
            title={title}
            subtitle={subtitle}
            navItems={navItems}
            activeTab={activeTab}
            onTabChange={onTabChange}
            collapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
            headerIdentity={headerIdentity}
            footer={sidebarFooter}
          />
        )}

        <main className="flex-1 min-w-0 bg-canvas">
          <div className="max-w-[1440px] mx-auto w-full px-4 sm:px-6 lg:px-8 py-5 sm:py-7">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

