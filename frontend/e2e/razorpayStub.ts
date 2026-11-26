import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { Page } from '@playwright/test';

export type RazorpayStubMode = 'paid' | 'dismiss' | 'fail' | 'stall';

function resolveRazorpaySecret(): string {
  if (process.env.RAZORPAY_KEY_SECRET) {
    return process.env.RAZORPAY_KEY_SECRET;
  }
  const candidateEnvPaths = [
    path.resolve(process.cwd(), '.env'),
    path.resolve(process.cwd(), '..', '.env'),
  ];
  for (const envPath of candidateEnvPaths) {
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf-8');
      for (const rawLine of content.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) continue;
        const eq = line.indexOf('=');
        if (eq > 0 && line.slice(0, eq).trim() === 'RAZORPAY_KEY_SECRET') {
          return line
            .slice(eq + 1)
            .trim()
            .replace(/^["']|["']$/g, '');
        }
      }
    }
  }
  throw new Error('RAZORPAY_KEY_SECRET not found in environment or .env for Playwright HMAC signing');
}

export interface RazorpayStubController {
  setMode: (mode: RazorpayStubMode) => void;
  getInvocations: () => Array<{ order_id: string; amount: number; currency: string; mode: RazorpayStubMode }>;
}

/**
 * Registers a Playwright-only route handler for `https://checkout.razorpay.com/v1/checkout.js`
 * and exposes genuine HMAC-SHA256 signing + test mode control across navigations so backend
 * `/api/v1/payments/verify-signature` performs real cryptographic signature verification.
 */
export async function installRazorpayTestStub(
  page: Page,
  initialMode: RazorpayStubMode = 'paid'
): Promise<RazorpayStubController> {
  const secret = resolveRazorpaySecret();
  let currentMode: RazorpayStubMode = initialMode;
  const invocations: Array<{ order_id: string; amount: number; currency: string; mode: RazorpayStubMode }> = [];

  await page.exposeFunction('__pwComputeRazorpayHmac', (orderId: string, paymentId: string) => {
    return crypto
      .createHmac('sha256', secret)
      .update(`${orderId}|${paymentId}`)
      .digest('hex');
  });

  await page.exposeFunction('__pwGetRazorpayMode', () => currentMode);

  await page.exposeFunction(
    '__pwRecordRazorpayOpen',
    (meta: { order_id: string; amount: number; currency: string; mode: RazorpayStubMode }) => {
      invocations.push(meta);
    }
  );

  await page.route('https://checkout.razorpay.com/v1/checkout.js', async (route) => {
    const stubJs = `
      (function () {
        window.Razorpay = function (options) {
          this.options = options;
          this.handlers = {};
          this.on = function (evt, cb) {
            this.handlers[evt] = this.handlers[evt] || [];
            this.handlers[evt].push(cb);
          };
          this.close = function () {};
          this.open = function () {
            var self = this;
            setTimeout(async function () {
              var mode = await window.__pwGetRazorpayMode();
              await window.__pwRecordRazorpayOpen({
                order_id: self.options.order_id,
                amount: self.options.amount,
                currency: self.options.currency,
                mode: mode
              });
              if (mode === 'stall') {
                // Reproduces silent Razorpay iframe failure: hidden .razorpay-container with 0x0 iframe and zero callbacks
                var stuckDiv = document.createElement('div');
                stuckDiv.className = 'razorpay-container';
                stuckDiv.style.display = 'none';
                var stuckIframe = document.createElement('iframe');
                stuckIframe.className = 'razorpay-checkout-frame';
                stuckDiv.appendChild(stuckIframe);
                document.body.appendChild(stuckDiv);
                return;
              }
              if (mode === 'dismiss') {
                if (self.options && self.options.modal && typeof self.options.modal.ondismiss === 'function') {
                  self.options.modal.ondismiss();
                }
                return;
              }
              if (mode === 'fail') {
                var cbs = self.handlers['payment.failed'] || [];
                var failPayload = {
                  error: {
                    code: 'BAD_REQUEST_ERROR',
                    description: 'E2E simulated payment authorization decline',
                    source: 'bank',
                    step: 'payment_authentication',
                    reason: 'payment_failed',
                    metadata: {
                      order_id: self.options.order_id,
                      payment_id: 'pay_pwfail_' + Date.now()
                    }
                  }
                };
                cbs.forEach(function (fn) { fn(failPayload); });
                return;
              }
              var payId = 'pay_pw_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
              var sig = await window.__pwComputeRazorpayHmac(self.options.order_id, payId);
              if (self.options && typeof self.options.handler === 'function') {
                self.options.handler({
                  razorpay_order_id: self.options.order_id,
                  razorpay_payment_id: payId,
                  razorpay_signature: sig
                });
              }
            }, 60);
          };
        };
      })();
    `;
    await route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: stubJs,
    });
  });

  return {
    setMode: (mode: RazorpayStubMode) => {
      currentMode = mode;
    },
    getInvocations: () => [...invocations],
  };
}
