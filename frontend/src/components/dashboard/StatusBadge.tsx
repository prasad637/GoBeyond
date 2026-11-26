import React from "react";
import { Badge, BadgeSize, BadgeVariant } from "@/components/ui/Badge";

export interface StatusBadgeProps {
  status: string | null | undefined;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

const STATUS_VARIANT_MAP: Record<string, BadgeVariant> = {
  // Success states
  CONFIRMED: "success",
  APPROVED: "success",
  ACTIVE: "success",
  VERIFIED: "success",
  CAPTURED: "success",
  SUCCESS: "success",
  DELIVERED: "success",
  PROCESSED: "success",
  HEALTHY: "success",
  SCHEDULED: "success",
  SEATED: "success",
  VERIFIED_ENTRY_GRANTED: "success",
  CONSERVED: "success",

  // Pending / in-flight states
  PENDING: "warning",
  PENDING_APPROVAL: "warning",
  PENDING_VERIFICATION: "warning",
  PAYMENT_PENDING: "warning",
  INVENTORY_HELD: "warning",
  INITIATED: "warning",
  PROCESSING: "warning",
  SUBMITTED: "warning",
  PARTIALLY_REFUNDED: "warning",
  DEGRADED: "warning",

  // Info / completed / special states
  REFUNDED: "info",
  REFUND_PENDING: "info",
  COMPLETED: "info",
  HOUSEFULL: "console",
  CONCERT: "console",
  FESTIVAL: "console",
  EVENT: "console",

  // Danger / negative states
  CANCELLED: "danger",
  FAILED: "danger",
  REJECTED: "danger",
  SUSPENDED: "danger",
  DEACTIVATED: "danger",
  DEAD_LETTER: "danger",
  EXPIRED: "danger",
  NO_SHOW: "danger",
  INVALID: "danger",
  UNAUTHORIZED_PARTNER: "danger",

  // Vertical & misc tags
  MOVIE: "gold",
  CINEMA: "info",
  DINING: "success",
  RESTAURANT: "gold",
  SPORTS: "success",
  ACTIVITY: "console",
  ACTIVITIES: "console",
  SKIPPED: "default",
  DISABLED: "default",
};

export function resolveStatusVariant(status: string | null | undefined): BadgeVariant {
  if (!status) return "default";
  const key = status.toUpperCase().trim();
  return STATUS_VARIANT_MAP[key] || "default";
}

export function StatusBadge({
  status,
  size = "sm",
  dot = true,
  className,
}: StatusBadgeProps) {
  const display = status || "UNKNOWN";
  const variant = resolveStatusVariant(display);

  return (
    <Badge variant={variant} size={size} dot={dot} className={className}>
      {display.replace(/_/g, " ")}
    </Badge>
  );
}

