export interface BookingPriceSummary {
  subtotal: number;
  discount: number;
  taxableAmount: number;
  gstAmount: number;
  finalPayable: number;
}

export function roundCurrency(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Number(value.toFixed(2));
}

export function computeBookingTotals(
  subtotal: number,
  discountAmount = 0
): BookingPriceSummary {
  const safeSubtotal = roundCurrency(Math.max(0, subtotal));
  const safeDiscount = roundCurrency(
    Math.min(safeSubtotal, Math.max(0, discountAmount))
  );
  const taxableAmount = roundCurrency(Math.max(0, safeSubtotal - safeDiscount));
  const gstAmount = roundCurrency(taxableAmount * 0.18);
  const finalPayable = roundCurrency(taxableAmount + gstAmount);

  return {
    subtotal: safeSubtotal,
    discount: safeDiscount,
    taxableAmount,
    gstAmount,
    finalPayable,
  };
}

export function formatRupees(
  amount: number,
  options: { decimals?: number; useGrouping?: boolean } = {}
): string {
  const { decimals = 0, useGrouping = true } = options;
  const safe = Number.isFinite(amount) ? amount : 0;
  if (!useGrouping) {
    return `₹${safe.toFixed(decimals)}`;
  }
  return `₹${safe.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

