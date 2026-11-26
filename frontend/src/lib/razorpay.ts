import { apiRequest } from "@/lib/api";

export const RAZORPAY_CHECKOUT_SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

export interface RazorpayPaymentSuccessResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayPaymentFailedPayload {
  error?: {
    code?: string;
    description?: string;
    source?: string;
    step?: string;
    reason?: string;
    metadata?: {
      order_id?: string;
      payment_id?: string;
    };
  };
}

export interface RazorpayCheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  notes?: Record<string, string>;
  theme?: {
    color?: string;
  };
  handler: (response: RazorpayPaymentSuccessResponse) => void;
  modal?: {
    ondismiss?: () => void;
    escape?: boolean;
    confirm_close?: boolean;
  };
}

export interface RazorpayInstance {
  open: () => void;
  close?: () => void;
  on: (
    event: "payment.failed",
    callback: (payload: RazorpayPaymentFailedPayload) => void
  ) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayCheckoutOptions) => RazorpayInstance;
  }
}

export type RazorpayCheckoutOutcome =
  | { status: "paid"; response: RazorpayPaymentSuccessResponse }
  | { status: "dismissed" }
  | {
      status: "failed";
      error: {
        code?: string;
        description: string;
        reason?: string;
        order_id?: string;
        payment_id?: string;
      };
    };

let scriptLoadPromise: Promise<boolean> | null = null;

/**
 * Dynamically loads Razorpay's official Checkout.js SDK from checkout.razorpay.com.
 * Deduplicates concurrent loads and resets on script error so retries can recover cleanly.
 */
export function loadRazorpayCheckoutScript(timeoutMs = 15000): Promise<boolean> {
  if (typeof window === "undefined") {
    return Promise.resolve(false);
  }
  if (typeof window.Razorpay === "function") {
    return Promise.resolve(true);
  }
  if (scriptLoadPromise) {
    return scriptLoadPromise;
  }

  scriptLoadPromise = new Promise<boolean>((resolve) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${RAZORPAY_CHECKOUT_SCRIPT_URL}"]`
    );

    let finished = false;
    let activeScript: HTMLScriptElement | null = existing;
    const finish = (ok: boolean) => {
      if (finished) return;
      finished = true;
      window.clearTimeout(timer);
      if (!ok) {
        scriptLoadPromise = null;
        if (activeScript && typeof window.Razorpay !== "function") {
          activeScript.remove();
        }
      }
      resolve(ok);
    };

    const timer = window.setTimeout(() => finish(false), timeoutMs);

    if (existing) {
      if (typeof window.Razorpay === "function") {
        finish(true);
        return;
      }
      existing.addEventListener("load", () => finish(typeof window.Razorpay === "function"), {
        once: true,
      });
      existing.addEventListener("error", () => finish(false), { once: true });
      return;
    }

    const script = document.createElement("script");
    activeScript = script;
    script.src = RAZORPAY_CHECKOUT_SCRIPT_URL;
    script.async = true;
    script.onload = () => finish(typeof window.Razorpay === "function");
    script.onerror = () => finish(false);
    document.head.appendChild(script);
  });

  return scriptLoadPromise;
}

export interface OpenRazorpayCheckoutParams {
  keyId: string;
  orderId: string;
  amountInRupees: number;
  currency?: string;
  description: string;
  openTimeoutMs?: number;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  notes?: Record<string, string>;
}

const DEFAULT_CHECKOUT_OPEN_TIMEOUT_MS = 8000;
const RAZORPAY_IFRAME_ORIGINS = new Set([
  "https://api.razorpay.com",
  "https://checkout.razorpay.com",
]);

function isRazorpayOverlayVisible(): boolean {
  if (typeof document === "undefined") return false;
  const containers = Array.from(document.querySelectorAll<HTMLElement>(".razorpay-container"));
  return containers.some((container) => {
    const cs = window.getComputedStyle(container);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") {
      return false;
    }
    const iframe = container.querySelector<HTMLIFrameElement>(
      "iframe.razorpay-checkout-frame, iframe"
    );
    if (!iframe) return false;
    const rect = iframe.getBoundingClientRect();
    return rect.width > 50 && rect.height > 50;
  });
}

function cleanupStuckRazorpayContainers(): void {
  if (typeof document === "undefined") return;
  document.querySelectorAll(".razorpay-container").forEach((node) => {
    try {
      node.remove();
    } catch {
      // ignore DOM cleanup failure
    }
  });
}

/**
 * Opens Razorpay Standard Checkout modal and settles strictly once with
 * paid / dismissed / failed outcome. Includes an initialization watchdog so
 * silent iframe auth/network failures (where Checkout.js leaves .razorpay-container
 * hidden at 0x0 without firing callbacks) never strand the UI in infinite loading.
 */
export async function openRazorpayCheckout(
  params: OpenRazorpayCheckoutParams
): Promise<RazorpayCheckoutOutcome> {
  const sdkReady = await loadRazorpayCheckoutScript();
  if (!sdkReady || typeof window.Razorpay !== "function") {
    return {
      status: "failed",
      error: {
        code: "SDK_LOAD_ERROR",
        description:
          "Unable to load Razorpay Checkout SDK. Please check your connection and try again.",
        order_id: params.orderId,
      },
    };
  }

  if (!params.keyId || !params.orderId) {
    return {
      status: "failed",
      error: {
        code: "INVALID_ORDER_CONFIG",
        description: "Payment gateway configuration is incomplete for this order.",
        order_id: params.orderId,
      },
    };
  }

  const openTimeoutMs =
    typeof params.openTimeoutMs === "number" && params.openTimeoutMs > 0
      ? params.openTimeoutMs
      : DEFAULT_CHECKOUT_OPEN_TIMEOUT_MS;

  return new Promise<RazorpayCheckoutOutcome>((resolve) => {
    let settled = false;
    let everVisible = false;
    let faultDetected = false;
    let rzpInstance: RazorpayInstance | null = null;
    let pollTimer: number | null = null;
    let openTimer: number | null = null;
    let faultTimer: number | null = null;
    let collapseTimer: number | null = null;

    const clearCollapseTimer = () => {
      if (collapseTimer !== null) {
        window.clearTimeout(collapseTimer);
        collapseTimer = null;
      }
    };

    const cleanupWatchers = () => {
      if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
      if (openTimer !== null) {
        window.clearTimeout(openTimer);
        openTimer = null;
      }
      if (faultTimer !== null) {
        window.clearTimeout(faultTimer);
        faultTimer = null;
      }
      clearCollapseTimer();
      window.removeEventListener("message", handleWindowMessage);
      document.removeEventListener("securitypolicyviolation", handleCspViolation);
    };

    const settle = (outcome: RazorpayCheckoutOutcome) => {
      if (settled) return;
      settled = true;
      cleanupWatchers();
      resolve(outcome);
    };

    const abortModal = (code: string, reason: string, description: string) => {
      if (settled) return;
      try {
        rzpInstance?.close?.();
      } catch {
        // ignore close errors on uninitialized modal
      }
      cleanupStuckRazorpayContainers();
      settle({
        status: "failed",
        error: {
          code,
          reason,
          description,
          order_id: params.orderId,
        },
      });
    };

    const handleWindowMessage = (event: MessageEvent) => {
      if (settled) return;
      if (!RAZORPAY_IFRAME_ORIGINS.has(event.origin)) return;

      let parsed: Record<string, any> | null = null;
      if (typeof event.data === "string") {
        try {
          parsed = JSON.parse(event.data);
        } catch {
          return;
        }
      } else if (event.data && typeof event.data === "object") {
        parsed = event.data as Record<string, any>;
      }

      if (parsed?.event === "fault") {
        faultDetected = true;
        if (faultTimer === null) {
          // Give Razorpay Checkout.js a short window to invoke payment.failed/ondismiss first
          faultTimer = window.setTimeout(() => {
            if (settled) return;
            abortModal(
              "CHECKOUT_INIT_FAULT",
              "gateway_authentication_or_init_failed",
              "Razorpay Checkout could not initialize for this order (verify gateway keys/sandbox configuration or retry). Your held inventory has been released."
            );
          }, 1200);
        }
      }
    };

    const handleCspViolation = (event: SecurityPolicyViolationEvent) => {
      if (settled) return;
      if ((event.blockedURI || "").toLowerCase().includes("razorpay")) {
        abortModal(
          "CHECKOUT_CSP_BLOCKED",
          "csp_violation",
          "Browser security policy blocked the Razorpay Checkout frame. Please allow Razorpay checkout scripts/frames and retry."
        );
      }
    };

    try {
      const amountInPaise = Math.max(100, Math.round(Number(params.amountInRupees) * 100));
      window.addEventListener("message", handleWindowMessage);
      document.addEventListener("securitypolicyviolation", handleCspViolation);

      const rzp = new window.Razorpay!({
        key: params.keyId,
        amount: amountInPaise,
        currency: params.currency || "INR",
        name: "GO BEYOND",
        description: params.description,
        order_id: params.orderId,
        prefill: params.prefill,
        notes: params.notes,
        theme: { color: "#F43F5E" },
        handler: (response: RazorpayPaymentSuccessResponse) => {
          settle({ status: "paid", response });
        },
        modal: {
          escape: true,
          confirm_close: true,
          ondismiss: () => {
            settle({ status: "dismissed" });
          },
        },
      });
      rzpInstance = rzp;

      rzp.on("payment.failed", (payload: RazorpayPaymentFailedPayload) => {
        try {
          rzp.close?.();
        } catch {
          // ignore close errors
        }
        const err = payload?.error || {};
        settle({
          status: "failed",
          error: {
            code: err.code || "PAYMENT_FAILED",
            description:
              err.description ||
              "Payment authorization failed. No amount was captured for this booking.",
            reason: err.reason,
            order_id: err.metadata?.order_id || params.orderId,
            payment_id: err.metadata?.payment_id,
          },
        });
      });

      pollTimer = window.setInterval(() => {
        if (settled) {
          cleanupWatchers();
          return;
        }
        const visibleNow = isRazorpayOverlayVisible();
        if (visibleNow) {
          everVisible = true;
          clearCollapseTimer();
          return;
        }
        // Checkout.js often shows a 100% dark loading container before collapsing to display:none on 401/fault
        if (everVisible && collapseTimer === null) {
          const graceMs = faultDetected ? 300 : 1200;
          collapseTimer = window.setTimeout(() => {
            if (settled || isRazorpayOverlayVisible()) return;
            abortModal(
              faultDetected ? "CHECKOUT_INIT_FAULT" : "CHECKOUT_MODAL_CLOSED",
              faultDetected
                ? "gateway_authentication_or_init_failed"
                : "gateway_closed_without_callback",
              "Razorpay Checkout could not complete initialization and closed unexpectedly. Your held inventory has been released."
            );
          }, graceMs);
        }
      }, 200);

      openTimer = window.setTimeout(() => {
        if (settled || (everVisible && isRazorpayOverlayVisible() && !faultDetected)) {
          return;
        }
        if (everVisible && !isRazorpayOverlayVisible()) {
          abortModal(
            "CHECKOUT_MODAL_UNAVAILABLE",
            "gateway_closed_before_ready",
            "Razorpay checkout window closed before payment could proceed. Your held inventory has been released."
          );
          return;
        }
        if (!everVisible) {
          abortModal(
            "CHECKOUT_MODAL_UNAVAILABLE",
            "gateway_open_timeout",
            "Razorpay checkout window did not open in time. Please check your gateway configuration or network/popup settings and retry. Your held inventory has been released."
          );
        }
      }, openTimeoutMs);

      rzp.open();
    } catch (err: any) {
      cleanupStuckRazorpayContainers();
      settle({
        status: "failed",
        error: {
          code: "CHECKOUT_INIT_ERROR",
          description: err?.message || "Failed to initialize Razorpay checkout modal.",
          order_id: params.orderId,
        },
      });
    }
  });
}

export interface BookingSummaryForCheckout {
  id: number;
  booking_reference: string;
  status: string;
  final_payable: number;
  qr_code_token?: string | null;
}

export type CompleteCheckoutResult =
  | {
      status: "confirmed";
      reference: string;
      qr_token: string;
      amount: number;
    }
  | {
      status: "refund_pending";
      reference: string;
      message: string;
    }
  | {
      status: "dismissed";
      message: string;
    }
  | {
      status: "failed";
      message: string;
    };

/**
 * Server-authoritative end-to-end payment completion for an initiated booking:
 * 1. Immediately confirms zero-payable (100% coupon discount) bookings without opening gateway modal.
 * 2. Creates Razorpay order on backend (amount computed exclusively on backend).
 * 3. Launches official Razorpay Checkout.js modal.
 * 4. Verifies HMAC-SHA256 signature on backend and checks for late-payment REFUND_PENDING.
 * 5. Releases held inventory immediately on dismissal, failure, or transport interruption.
 */
export async function completeRazorpayCheckoutForBooking(params: {
  booking: BookingSummaryForCheckout;
  description: string;
  idempotencyKey?: string;
  prefill?: { name?: string; email?: string; contact?: string };
}): Promise<CompleteCheckoutResult> {
  const { booking, description, idempotencyKey, prefill } = params;

  if (booking.status === "CONFIRMED") {
    return {
      status: "confirmed",
      reference: booking.booking_reference,
      qr_token: booking.qr_code_token || "",
      amount: Number(booking.final_payable || 0),
    };
  }

  let orderRes: {
    order_id: string;
    booking_reference: string;
    amount: number;
    currency: string;
    key_id: string;
    booking_id: number;
  };

  try {
    orderRes = await apiRequest("/payments/create-order", {
      method: "POST",
      body: JSON.stringify({
        booking_id: booking.id,
        idempotency_key: idempotencyKey,
      }),
    });
  } catch (err: any) {
    // Release unpaid hold immediately so inventory isn't stranded
    await apiRequest(`/bookings/${booking.id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: "Order creation failed before payment" }),
    }).catch(() => {});
    return {
      status: "failed",
      message: err?.message || "Unable to initiate Razorpay payment order.",
    };
  }

  const gatewayKey =
    orderRes.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "";

  const outcome = await openRazorpayCheckout({
    keyId: gatewayKey,
    orderId: orderRes.order_id,
    amountInRupees: orderRes.amount,
    currency: orderRes.currency || "INR",
    description,
    prefill,
    notes: {
      booking_reference: orderRes.booking_reference || booking.booking_reference,
    },
  });

  if (outcome.status === "dismissed") {
    await apiRequest(`/bookings/${booking.id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: "Payment checkout dismissed by customer" }),
    }).catch(() => {});
    return {
      status: "dismissed",
      message: "Payment was cancelled before completion. Any temporary hold has been released.",
    };
  }

  if (outcome.status === "failed") {
    try {
      await apiRequest("/payments/report-failure", {
        method: "POST",
        body: JSON.stringify({
          booking_id: booking.id,
          razorpay_order_id: outcome.error.order_id || orderRes.order_id,
          razorpay_payment_id: outcome.error.payment_id,
          error_code: outcome.error.code,
          error_description: outcome.error.description,
          error_reason: outcome.error.reason,
        }),
      });
    } catch {
      await apiRequest(`/bookings/${booking.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: "Payment failure fallback release" }),
      }).catch(() => {});
    }
    return {
      status: "failed",
      message: outcome.error.description || "Payment could not be completed. Held inventory has been released.",
    };
  }

  // Verify gateway signature strictly on backend before issuing confirmation/QR pass
  try {
    const verifyRes = await apiRequest<{
      success: boolean;
      status: string;
      booking_reference: string;
      payment_id: string;
      qr_code_token?: string;
      message?: string;
    }>("/payments/verify-signature", {
      method: "POST",
      body: JSON.stringify({
        booking_id: booking.id,
        razorpay_order_id: outcome.response.razorpay_order_id || orderRes.order_id,
        razorpay_payment_id: outcome.response.razorpay_payment_id,
        razorpay_signature: outcome.response.razorpay_signature,
        idempotency_key: idempotencyKey,
      }),
    });

    if (verifyRes.success && verifyRes.status === "CONFIRMED") {
      return {
        status: "confirmed",
        reference: verifyRes.booking_reference,
        qr_token: verifyRes.qr_code_token || "",
        amount: Number(orderRes.amount),
      };
    }

    return {
      status: "refund_pending",
      reference: verifyRes.booking_reference || booking.booking_reference,
      message:
        verifyRes.message ||
        "Payment arrived after the booking hold expired. Automatic refund has been initiated.",
    };
  } catch (err: any) {
    return {
      status: "failed",
      message:
        err?.message ||
        "Payment signature verification failed. Please check your bookings before retrying.",
    };
  }
}

