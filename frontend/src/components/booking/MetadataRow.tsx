import React from "react";
import { cn } from "@/lib/cn";

export interface MetadataItem {
  id: string;
  icon?: React.ReactNode;
  label: string;
  value?: React.ReactNode;
  accent?: "default" | "champagne" | "brand" | "success";
}

export interface MetadataRowProps {
  items: MetadataItem[];
  className?: string;
}

const accentClasses: Record<NonNullable<MetadataItem["accent"]>, string> = {
  default: "text-secondary",
  champagne: "text-champagne font-semibold",
  brand: "text-brand-400 font-semibold",
  success: "text-emerald-400 font-semibold",
};

export function MetadataRow({ items, className }: MetadataRowProps) {
  const visibleItems = items.filter((item) => Boolean(item.label || item.value));
  if (visibleItems.length === 0) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-2 text-xs sm:text-sm",
        className
      )}
    >
      {visibleItems.map((item) => (
        <div
          key={item.id}
          className={cn(
            "inline-flex items-center gap-1.5 min-w-0",
            accentClasses[item.accent ?? "default"]
          )}
        >
          {item.icon ? <span className="shrink-0">{item.icon}</span> : null}
          <span className="truncate">{item.value ?? item.label}</span>
        </div>
      ))}
    </div>
  );
}

