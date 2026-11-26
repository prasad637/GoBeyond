import React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface DashboardBreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function DashboardBreadcrumbs({ items, className }: DashboardBreadcrumbsProps) {
  if (!items.length) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn("flex items-center flex-wrap gap-1.5 text-xs", className)}>
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <React.Fragment key={`${item.label}-${idx}`}>
            {idx > 0 && (
              <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" aria-hidden="true" />
            )}
            {isLast ? (
              <span className="font-semibold text-primary truncate">{item.label}</span>
            ) : item.href ? (
              <Link
                href={item.href}
                className="text-secondary hover:text-primary transition-colors truncate"
              >
                {item.label}
              </Link>
            ) : item.onClick ? (
              <button
                type="button"
                onClick={item.onClick}
                className="text-secondary hover:text-primary transition-colors truncate"
              >
                {item.label}
              </button>
            ) : (
              <span className="text-muted truncate">{item.label}</span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

