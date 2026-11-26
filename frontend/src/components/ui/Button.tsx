import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "ghost"
  | "danger"
  | "console";

export type ButtonSize = "xs" | "sm" | "md" | "lg";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white border border-brand-500/30 shadow-brand-sm focus-visible:ring-brand-500/60",
  secondary:
    "bg-surface-2 hover:bg-surface-3 active:bg-surface-3/80 text-primary border border-subtle hover:border-strong focus-visible:ring-white/30",
  outline:
    "bg-transparent hover:bg-surface-2 active:bg-surface-3 text-primary border border-strong hover:border-white/30 focus-visible:ring-white/30",
  ghost:
    "bg-transparent hover:bg-surface-2 active:bg-surface-3 text-secondary hover:text-primary border border-transparent focus-visible:ring-white/30",
  danger:
    "bg-red-500/10 hover:bg-red-500/20 active:bg-red-500/25 text-red-400 hover:text-red-300 border border-red-500/25 focus-visible:ring-red-500/50",
  console:
    "bg-console-600 hover:bg-console-500 active:bg-console-700 text-white border border-console-500/30 shadow-console-sm focus-visible:ring-console-500/60",
};

const sizeClasses: Record<ButtonSize, string> = {
  xs: "h-8 px-2.5 text-xs font-medium rounded-lg gap-1.5",
  sm: "h-9 px-3.5 text-xs font-semibold rounded-lg gap-1.5",
  md: "h-10 px-4 text-sm font-semibold rounded-lg gap-2",
  lg: "h-11 px-5 text-sm font-semibold rounded-lg gap-2",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading = false,
      loadingText,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      children,
      type = "button",
      ...props
    },
    ref
  ) => {
    const isDisabled = Boolean(disabled || isLoading);

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading || undefined}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap select-none transition-all duration-150",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
          "disabled:opacity-50 disabled:pointer-events-none",
          variantClasses[variant],
          sizeClasses[size],
          fullWidth && "w-full",
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 shrink-0 animate-spin" aria-hidden="true" />
            <span>{loadingText ?? children}</span>
          </>
        ) : (
          <>
            {leftIcon ? <span className="shrink-0 flex items-center">{leftIcon}</span> : null}
            <span>{children}</span>
            {rightIcon ? <span className="shrink-0 flex items-center">{rightIcon}</span> : null}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = "Button";

