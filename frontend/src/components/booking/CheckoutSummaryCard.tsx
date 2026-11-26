"use client";

import React from "react";
import { AlertCircle, ArrowRight, ShieldCheck, Tag, X } from "lucide-react";
import { computeBookingTotals } from "@/lib/pricing";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export interface CheckoutSummaryCardProps {
  subtotal: number;
  discountAmount: number;
  itemsLabel: string;
  totalLabel?: string;
  hasSelection: boolean;
  emptySelectionMessage?: string;
  couponCode: string;
  onCouponCodeChange: (val: string) => void;
  onApplyCoupon: () => void | Promise<void>;
  onClearCoupon?: () => void;
  couponMessage?: string | null;
  couponLoading?: boolean;
  bookingError?: string | null;
  isSubmitting: boolean;
  submitDisabled?: boolean;
  hideSubmitButton?: boolean;
  onSubmit: () => void;
  className?: string;
}

export function CheckoutSummaryCard({
  subtotal,
  discountAmount,
  itemsLabel,
  totalLabel = "Total Payable:",
  hasSelection,
  emptySelectionMessage = "Select an option to review price & GST breakdown.",
  couponCode,
  onCouponCodeChange,
  onApplyCoupon,
  onClearCoupon,
  couponMessage,
  couponLoading = false,
  bookingError,
  isSubmitting,
  submitDisabled = false,
  hideSubmitButton = false,
  onSubmit,
  className,
}: CheckoutSummaryCardProps) {
  const { gstAmount, finalPayable } = computeBookingTotals(subtotal, discountAmount);

  return (
    <div className={cn("space-y-4", className)}>
      {bookingError ? (
        <div
          role="alert"
          className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-start gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{bookingError}</span>
        </div>
      ) : null}

      {/* Coupon Code Box */}
      <div className="space-y-1.5">
        <div className="flex gap-2">
          <div className="relative flex-1 min-w-0">
            <Tag
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Promo code (e.g. BEYOND50)"
              aria-label="Promo coupon code"
              value={couponCode}
              onChange={(e) => onCouponCodeChange(e.target.value.toUpperCase())}
              className="w-full h-10 md:h-9 pl-9 pr-8 bg-surface-2 border border-subtle rounded-xl text-base md:text-xs font-mono uppercase text-primary placeholder:text-muted placeholder:font-sans placeholder:normal-case focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-colors"
            />
            {couponCode && onClearCoupon ? (
              <button
                type="button"
                aria-label="Remove coupon"
                onClick={onClearCoupon}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-muted hover:text-primary"
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </div>

          <Button
            variant="secondary"
            size="sm"
            isLoading={couponLoading}
            disabled={!couponCode.trim() || !hasSelection || couponLoading}
            onClick={onApplyCoupon}
            className="text-brand-400 hover:text-brand-300 h-10 md:h-9 shrink-0"
          >
            Apply
          </Button>
        </div>

        {couponMessage ? (
          <p
            className={cn(
              "text-[11px] leading-snug",
              discountAmount > 0 ? "text-emerald-400" : "text-secondary"
            )}
          >
            {couponMessage}
          </p>
        ) : null}
      </div>

      {/* Price Breakdown */}
      {hasSelection ? (
        <div className="p-3.5 bg-canvas/90 border border-subtle rounded-xl text-xs space-y-2">
          <div className="flex justify-between gap-2 text-secondary">
            <span className="truncate">{itemsLabel}</span>
            <span className="font-mono text-primary tabular-nums-lining shrink-0">
              ₹{subtotal.toFixed(2)}
            </span>
          </div>

          {discountAmount > 0 ? (
            <div className="flex justify-between gap-2 text-emerald-400">
              <span>Promo Discount:</span>
              <span className="font-mono tabular-nums-lining shrink-0">
                -₹{discountAmount.toFixed(2)}
              </span>
            </div>
          ) : null}

          <div className="flex justify-between gap-2 text-secondary">
            <span>GST Tax (18%):</span>
            <span className="font-mono text-primary tabular-nums-lining shrink-0">
              ₹{gstAmount.toFixed(2)}
            </span>
          </div>

          <div className="pt-2.5 border-t border-subtle flex justify-between items-center gap-2 font-bold text-sm">
            <span className="text-primary">{totalLabel}</span>
            <span className="font-mono text-brand-400 text-base tabular-nums-lining">
              ₹{finalPayable.toFixed(2)}
            </span>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-canvas/70 border border-subtle rounded-xl text-xs text-muted text-center">
          {emptySelectionMessage}
        </div>
      )}

      {/* Primary Coral Pay CTA */}
      {!hideSubmitButton ? (
        <>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            isLoading={isSubmitting}
            disabled={submitDisabled || !hasSelection || isSubmitting}
            rightIcon={<ArrowRight className="w-4 h-4" aria-hidden="true" />}
            onClick={onSubmit}
          >
            {finalPayable === 0
              ? "Confirm Booking (₹0.00)"
              : `Pay ₹${finalPayable.toFixed(2)} with Razorpay`}
          </Button>

          {/* Razorpay Checkout Notice */}
          <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted pt-0.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
            <span>Secured by Razorpay Checkout • Instant QR Pass</span>
          </div>
        </>
      ) : null}
    </div>
  );
}

