import React from "react";
import { cn } from "@/lib/cn";

export type BadgeVariant =
  | "default"
  | "brand"
  | "console"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "gold"
  | "veg"
  | "nonveg";

export type BadgeSize = "sm" | "md";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  icon?: React.ReactNode;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-surface-2 text-secondary border-subtle",
  brand: "bg-brand-500/12 text-brand-400 border-brand-500/25",
  console: "bg-console-500/12 text-console-400 border-console-500/25",
  success: "bg-emerald-500/12 text-emerald-400 border-emerald-500/25",
  warning: "bg-amber-500/12 text-amber-300 border-amber-500/25",
  danger: "bg-red-500/12 text-red-400 border-red-500/25",
  info: "bg-sky-500/12 text-sky-400 border-sky-500/25",
  gold: "bg-amber-400/12 text-amber-300 border-amber-400/30",
  veg: "bg-emerald-500/12 text-emerald-400 border-emerald-500/30",
  nonveg: "bg-red-500/12 text-red-400 border-red-500/30",
};

const dotClasses: Record<BadgeVariant, string> = {
  default: "bg-gray-400",
  brand: "bg-brand-400",
  console: "bg-console-400",
  success: "bg-emerald-400",
  warning: "bg-amber-400",
  danger: "bg-red-400",
  info: "bg-sky-400",
  gold: "bg-amber-400",
  veg: "bg-emerald-400",
  nonveg: "bg-red-400",
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-[11px] leading-tight gap-1.5",
  md: "px-2.5 py-1 text-xs leading-tight gap-1.5",
};

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  (
    {
      className,
      variant = "default",
      size = "sm",
      dot = false,
      icon,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center font-semibold border rounded-full whitespace-nowrap tracking-wide",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {dot ? (
          <span
            className={cn("w-1.5 h-1.5 rounded-full shrink-0", dotClasses[variant])}
            aria-hidden="true"
          />
        ) : null}
        {icon ? <span className="shrink-0 flex items-center">{icon}</span> : null}
        <span>{children}</span>
      </span>
    );
  }
);

Badge.displayName = "Badge";

