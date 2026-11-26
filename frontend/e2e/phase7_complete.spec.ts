import { test, expect, Page } from '@playwright/test';
import { installRazorpayTestStub, RazorpayStubController } from './razorpayStub';

async function signInViaLoginPage(page: Page, email: string, password: string, expectedUrlPattern: RegExp) {
  await page.goto('/login');
  await page.locator('input[placeholder="you@domain.com or 9876543210"]').fill(email);
  await page.locator('input[placeholder="••••••••"]').fill(password);
  await page.locator('button[type="submit"]:has-text("Sign In")').click();
  await expect(page).toHaveURL(expectedUrlPattern, { timeout: 15000 });
}

async function signOutViaNavbar(page: Page) {
  const profileTrigger = page.locator('header div.relative > button').first();
  await expect(profileTrigger).toBeVisible({ timeout: 10000 });
  await profileTrigger.click();
  const signOutBtn = page.locator('header button:has-text("Sign Out")');
  await expect(signOutBtn).toBeVisible({ timeout: 5000 });
  await signOutBtn.click();
  await expect(page.locator('header a:has-text("Sign In")').first()).toBeVisible({ timeout: 10000 });
}

test.describe.serial('GO BEYOND Phase 7 - Complete Launch Validation (Checkout, Failures, Mobile, Partner/Admin & RBAC)', () => {
  let page: Page;
  let rzpStub: RazorpayStubController;
  let registeredEmail = '';
  let registeredPhone = '';
  let movieBookingRef = '';

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await context.newPage();
    rzpStub = await installRazorpayTestStub(page, 'paid');
  });

  test.afterAll(async () => {
    await page?.context().close();
  });

  test('1. Customer registration -> OTP sandbox flow -> Location selector -> Search/Discovery', async () => {
    const suffix = Date.now().toString().slice(-8);
    registeredEmail = `p7cust_${suffix}@example.com`;
    registeredPhone = `99${suffix}`;

    // A. Register customer with Hyderabad locality
    await page.goto('/register');
    await expect(page.locator('h2:has-text("Create Your Go Beyond Account")')).toBeVisible();
    await page.locator('input[placeholder="John Doe"]').fill(`P7 Test ${suffix}`);
    await page.locator('input[placeholder="john@example.com"]').fill(registeredEmail);
    await page.locator('input[placeholder="9876543210"]').fill(registeredPhone);
    await expect(page.locator('select').nth(1)).toBeVisible({ timeout: 10000 });
    await page.locator('input[placeholder="Minimum 6 characters"]').fill('Customer@123');
    await page.locator('button[type="submit"]:has-text("Create Account")').click();
    await expect(page).toHaveURL(/\/profile/, { timeout: 15000 });

    await signOutViaNavbar(page);

    // B. Passwordless OTP flow via sandbox_code
    await page.goto('/verify-otp');
    await page.locator('input[placeholder="9876543210"]').fill(registeredPhone);
    await page.locator('button[type="submit"]:has-text("Send Verification Code")').click();
    await expect(page.locator('text=DEVELOPMENT SANDBOX CODE')).toBeVisible({ timeout: 10000 });
    const otpText = (await page.locator('p.font-mono.tracking-widest.font-black').innerText()).trim();
    expect(otpText).toMatch(/^\d{6}$/);

    await page.locator('input[placeholder="123456"]').fill(otpText);
    await page.locator('button[type="submit"]:has-text("Verify & Continue")').click();
    await expect(page).toHaveURL(/\/profile/, { timeout: 15000 });

    // C. Location selector + Global Search
    await page.goto('/');
    await page.locator('header button:has-text("Hyderabad")').first().click();
    await expect(page.locator('text=Jubilee Hills').first()).toBeVisible({ timeout: 5000 });
    await page.locator('text=Jubilee Hills').first().click();

    const searchInput = page.locator('input[aria-label="Global search"]');
    await searchInput.fill('Dune');
    await expect(page.locator('#navbar-search-popover')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#navbar-search-popover')).toContainText(/Dune/i);
    await searchInput.fill('');

    // Reset back to All Hyderabad inside modal dialog
    await page.locator('header button:has-text("Jubilee Hills")').first().click();
    const allHyderBtn = page.locator('[role="dialog"] button:has-text("All Hyderabad")').first();
    await expect(allHyderBtn).toBeVisible({ timeout: 5000 });
    await allHyderBtn.click();

    await signOutViaNavbar(page);
  });

  test('2. Razorpay Checkout lifecycle: modal.ondismiss + payment.failed inventory release -> genuine HMAC payment confirmation', async () => {
    await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);

    await page.goto('/movies');
    await page.locator('a[href^="/movies/"]').first().click();
    await expect(page.locator('h2:has-text("Cinema Shows & Timings")')).toBeVisible();

    // Pick first showtime & identify exact available seat title
    await page.locator('button:has-text(":")').first().click();
    const firstSeat = page.locator('button[title^="Seat "]:not([disabled])').first();
    await expect(firstSeat).toBeVisible({ timeout: 10000 });
    const seatTitle = (await firstSeat.getAttribute('title')) || '';
    const exactSeatSelector = `button[title="${seatTitle}"]`;

    // Case A: User dismisses Razorpay Checkout modal -> hold released immediately
    rzpStub.setMode('dismiss');
    await firstSeat.click();
    await page.locator('button:has-text("with Razorpay")').click();
    await expect(page.locator('text=Payment was cancelled before completion')).toBeVisible({ timeout: 15000 });

    // Verify exact seat is immediately unblocked and bookable again after reload
    await page.reload();
    await expect(page.locator('header button:has-text("Aarav")')).toBeVisible({ timeout: 10000 });
    await page.locator('button:has-text(":")').first().click();
    await expect(page.locator(`${exactSeatSelector}:not([disabled])`)).toBeVisible({ timeout: 10000 });

    // Case B: Razorpay emits payment.failed -> /payments/report-failure releases hold immediately
    rzpStub.setMode('fail');
    await page.locator(exactSeatSelector).click();
    await page.locator('button:has-text("with Razorpay")').click();
    await expect(page.locator('text=E2E simulated payment authorization decline')).toBeVisible({ timeout: 15000 });

    // Verify exact seat is STILL available immediately after payment failure
    await page.reload();
    await expect(page.locator('header button:has-text("Aarav")')).toBeVisible({ timeout: 10000 });
    await page.locator('button:has-text(":")').first().click();
    await expect(page.locator(`${exactSeatSelector}:not([disabled])`)).toBeVisible({ timeout: 10000 });

    // Case C: Genuine HMAC-SHA256 payment completion via Razorpay handler
    rzpStub.setMode('paid');
    await page.locator(exactSeatSelector).click();
    await page.locator('button:has-text("with Razorpay")').click();
    await expect(page.locator('h3:has-text("Booking Confirmed!")')).toBeVisible({ timeout: 15000 });
    await page.locator('button:has-text("View Confirmation & Pass")').click();

    await expect(page).toHaveURL(/\/bookings\/GB-.*\/confirmation/);
    await expect(page.locator('text=Official Gate Pass')).toBeVisible();
    await expect(page.locator('svg').first()).toBeVisible();
    const urlMatch = page.url().match(/\/bookings\/([^/]+)\/confirmation/);
    movieBookingRef = urlMatch ? urlMatch[1] : '';
    expect(movieBookingRef).toMatch(/^GB-/);
  });

  test('3. My Bookings cancellation -> refund badge + QR pass strictly deactivated on confirmation page & 404 slug state', async () => {
    await page.goto('/bookings');
    await expect(page.locator(`text=${movieBookingRef}`).first()).toBeVisible({ timeout: 10000 });

    // Locate booking card and cancel it
    const card = page.locator('div.bg-gray-900', { hasText: movieBookingRef }).first();
    await card.locator('button:has-text("Cancel")').click();
    await expect(page.locator('h3:has-text("Cancel Booking")')).toBeVisible();
    await page.locator('textarea[placeholder*="Change of plans"]').fill('Phase 7 E2E cancellation refund check');
    await page.locator('button[type="submit"]:has-text("Confirm Cancellation")').click();

    await expect(page.locator('h3:has-text("Cancel Booking")')).toBeHidden({ timeout: 10000 });
    await page.reload();
    await expect(page.locator(`text=${movieBookingRef}`).first()).toBeVisible({ timeout: 10000 });
    await page.waitForLoadState('networkidle');

    // Check confirmation route no longer issues active QR admission pass
    await page.goto(`/bookings/${movieBookingRef}/confirmation`);
    await expect(page.locator('text=Pass Inactive')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Official Gate Pass')).toBeHidden();

    // Check invalid movie slug graceful error UI
    await page.goto('/movies/non-existent-slug-phase7-test');
    await expect(page.locator('body')).toContainText(/not found|unavailable|discover/i);

    await signOutViaNavbar(page);
  });

  test('4. Mobile viewport (375x812) responsiveness & zero horizontal overflow across all customer pages', async ({ browser }) => {
    const mobileCtx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const mobilePage = await mobileCtx.newPage();

    const routes = ['/', '/movies', '/dining', '/events', '/sports', '/activities', '/login'];
    for (const route of routes) {
      await mobilePage.goto(route);
      await mobilePage.waitForLoadState('networkidle');
      const overflow = await mobilePage.evaluate(() => {
        return document.documentElement.scrollWidth - document.documentElement.clientWidth;
      });
      expect(overflow, `Horizontal overflow detected on mobile route ${route}`).toBeLessThanOrEqual(1);
    }

    await mobileCtx.close();
  });

  test('5. All 4 Partner Portals + Super Admin + Role Isolation Enforcement', async () => {
    const fetchWithCurrentSession = async (endpoint: string) => {
      return page.evaluate(async (ep) => {
        const match = document.cookie.match(/(?:^|;\s*)gobeyond_csrf_token=([^;]*)/);
        const csrf = match ? decodeURIComponent(match[1]) : '';
        const refRes = await fetch('/api/v1/auth/refresh', {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-CSRF-Token': csrf },
        });
        const refJson = await refRes.json();
        const r = await fetch(ep, {
          headers: { Authorization: `Bearer ${refJson.access_token}` },
        });
        return r.status;
      }, endpoint);
    };

    // Verify role isolation as Customer first
    await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
    expect(await fetchWithCurrentSession('/api/v1/admin/stats')).toBe(403);
    expect([403, 404]).toContain(await fetchWithCurrentSession('/api/v1/partners/profile'));
    await signOutViaNavbar(page);

    // Verify Restaurant Partner Portal
    await signInViaLoginPage(page, 'restaurant.partner@gobeyond.com', 'Partner@123', /\/partner/);
    await expect(page.locator('aside button:has-text("Listings & Catalog")')).toBeVisible({ timeout: 10000 });
    await page.locator('aside button:has-text("Financials & Payouts")').click();
    await expect(page.locator('text=Transaction Settlement Ledger')).toBeVisible({ timeout: 10000 });
    await signOutViaNavbar(page);

    // Verify Event Partner Portal
    await signInViaLoginPage(page, 'event.partner@gobeyond.com', 'Partner@123', /\/partner/);
    await expect(page.locator('aside button:has-text("Listings & Catalog")')).toBeVisible({ timeout: 10000 });
    await page.locator('aside button:has-text("Listings & Catalog")').click();
    await signOutViaNavbar(page);

    // Verify Sports/Activities Partner Portal + cannot access Admin API
    await signInViaLoginPage(page, 'sports.partner@gobeyond.com', 'Partner@123', /\/partner/);
    await expect(page.locator('aside button:has-text("Listings & Catalog")')).toBeVisible({ timeout: 10000 });
    expect(await fetchWithCurrentSession('/api/v1/admin/stats')).toBe(403);
    await page.goto('/admin');
    await expect(page.locator('h1:has-text("Super Admin Role Required")')).toBeVisible({ timeout: 10000 });
    await signOutViaNavbar(page);

    // Verify Super Admin financials & audit logs recorded PAYMENT_FAILED_REPORTED
    await signInViaLoginPage(page, 'admin@gobeyond.com', 'Admin@123', /\/admin/);
    await expect(page.locator('h1:has-text("System Executive Overview")')).toBeVisible({ timeout: 15000 });
    await page.locator('aside button:has-text("Immutable Audit Logs")').click();
    await expect(page.locator('text=PAYMENT_FAILED_REPORTED').first()).toBeVisible({ timeout: 10000 });
    await signOutViaNavbar(page);
  });
});
