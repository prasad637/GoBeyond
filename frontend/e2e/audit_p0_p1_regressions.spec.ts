import { test, expect, Page } from '@playwright/test';
import { installRazorpayTestStub, RazorpayStubController } from './razorpayStub';

async function signInViaLoginPage(
  page: Page,
  email: string,
  password: string,
  expectedUrlPattern: RegExp
) {
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

test.describe('GO BEYOND — Option B (P0 + P1) Audit Regressions', () => {
  test('AUD-M1-01 & AUD-M1-05: Sports cards render real local images with zero SPORTS fallback overlap; seed media assets load', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/sports');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('article a[href^="/sports/"]').first()).toBeVisible({ timeout: 10000 });

    // Confirm no fallback watermark badge "sports" overlaps Venue Details
    const watermarkBadges = page.locator('article span:text-is("sports")');
    expect(await watermarkBadges.count()).toBe(0);

    // Confirm card images loaded properly
    const imgStatus = await page.evaluate(() =>
      Array.from(document.querySelectorAll('article img')).map((img) => ({
        alt: img.getAttribute('alt'),
        src: img.getAttribute('src'),
        complete: (img as HTMLImageElement).complete,
        naturalWidth: (img as HTMLImageElement).naturalWidth,
      }))
    );
    expect(imgStatus.length).toBeGreaterThanOrEqual(2);
    for (const img of imgStatus) {
      expect(img.complete, `Image did not finish loading: ${img.src}`).toBe(true);
      expect(img.naturalWidth, `Broken image detected: ${img.src}`).toBeGreaterThan(0);
    }

    // Also verify movies & activities curated seed posters/cards loaded cleanly
    for (const route of ['/movies', '/activities']) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      const cards = await page.evaluate(() =>
        Array.from(document.querySelectorAll('main img')).map((img) => {
          (img as HTMLImageElement).scrollIntoView();
          return {
            alt: img.getAttribute('alt'),
            src: img.getAttribute('src'),
            complete: (img as HTMLImageElement).complete,
            naturalWidth: (img as HTMLImageElement).naturalWidth,
          };
        })
      );
      expect(cards.length).toBeGreaterThanOrEqual(2);
      for (const img of cards) {
        expect(img.complete && img.naturalWidth > 0, `Broken image on ${route}: ${img.src}`).toBe(true);
      }
    }
  });

  test('AUD-M1-03: Global search popover renders real loaded thumbnails via SafeMediaImage (no GB placeholder)', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[aria-label="Global search"]');
    await searchInput.fill('Dune');
    const popover = page.locator('#navbar-search-popover');
    await expect(popover).toBeVisible({ timeout: 10000 });
    await expect(popover).toContainText(/Dune: Part Two/i);

    // Wait briefly for thumbnail load and verify img naturalWidth > 0 and no "GB" text fallback
    await expect(popover.locator('img').first()).toBeVisible({ timeout: 5000 });
    await expect
      .poll(async () =>
        popover.evaluate((el) => {
          const imgs = Array.from(el.querySelectorAll('img'));
          return imgs.every((i) => i.complete && i.naturalWidth > 0);
        })
      )
      .toBe(true);

    expect(await popover.locator('div:text-is("GB")').count()).toBe(0);
  });

  test('AUD-M1-04: Activities hides SPORTS venues, while Sports -> Court detail uses Sports context and sends booking_type=SPORTS', async ({
    browser,
  }) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    try {
      await page.goto('/activities');
      await page.waitForLoadState('networkidle');
      // Sports chip must not appear on /activities
      expect(await page.locator('button:text-is("Sports")').count()).toBe(0);
      // Sports court must not appear under /activities listing
      await expect(page.locator('body')).not.toContainText('BWF Synthetic Badminton Court');

      // Also verify Homepage Activities rail excludes SPORTS courts
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      const actSection = page.locator('#activities-experiences');
      await expect(actSection).not.toContainText('Floodlit 5-a-Side Astroturf Football');

      // Navigate /sports -> court link with ?vertical=sports
      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await page.goto('/sports');
      await page.waitForLoadState('networkidle');

      const courtLink = page.locator('a[href^="/activities/"]:has-text("Book Slot")').first();
      await expect(courtLink).toBeVisible({ timeout: 10000 });
      const href = await courtLink.getAttribute('href');
      expect(href).toContain('vertical=sports');
      await courtLink.click();
      await page.waitForLoadState('networkidle');

      // Active Sports navbar tab & Sports breadcrumb
      const sportsNav = page.locator('header nav a:has-text("Sports")');
      await expect(sportsNav).toHaveClass(/border-brand-500/);
      await expect(page.locator('nav[aria-label="Breadcrumb"]')).toContainText('Sports');

      // Intercept /bookings/apply-coupon to verify booking_type === "SPORTS"
      let capturedCouponPayload: Record<string, any> | null = null;
      await page.route('**/api/v1/bookings/apply-coupon', async (route) => {
        capturedCouponPayload = route.request().postDataJSON();
        await route.continue();
      });

      const slotBtn = page.locator('button:has-text("left")').first();
      await expect(slotBtn).toBeVisible({ timeout: 10000 });
      await slotBtn.click();

      await page.locator('input[aria-label="Promo coupon code"]').fill('BEYOND50');
      await page.locator('button:has-text("Apply")').click();
      await expect.poll(() => capturedCouponPayload?.booking_type).toBe('SPORTS');
    } finally {
      await context.close();
    }
  });

  test('AUD-M1-02: Profile fetches ?city_slug=hyderabad localities, preserves Jubilee Hills & supports updates', async ({
    browser,
  }) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    try {
      const requestedUrls: string[] = [];
      page.on('request', (req) => {
        if (req.url().includes('/locations/localities')) {
          requestedUrls.push(req.url());
        }
      });

      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await page.waitForLoadState('networkidle');

      expect(requestedUrls.some((u) => u.includes('city_slug=hyderabad'))).toBe(true);
      expect(requestedUrls.some((u) => /[?&]city=/.test(u))).toBe(false);

      const localitySelect = page.locator('#profile-locality-select');
      await expect(localitySelect).toBeVisible({ timeout: 10000 });
      await expect.poll(async () => localitySelect.locator('option').count()).toBeGreaterThanOrEqual(11);

      const initialVal = await localitySelect.inputValue();
      const selectedText = await localitySelect.evaluate(
        (el: HTMLSelectElement) => el.options[el.selectedIndex]?.text || ''
      );
      expect(initialVal).not.toBe('');
      expect(selectedText).not.toContain('All');

      // Save & verify persistence across reload using a distinct locality, then restore initial value
      const targetName = selectedText === 'Madhapur' ? 'Jubilee Hills' : 'Madhapur';
      const targetVal = await localitySelect.evaluate((el: HTMLSelectElement, name: string) => {
        const opt = Array.from(el.options).find((o) => o.text === name);
        return opt?.value || '';
      }, targetName);
      expect(targetVal).not.toBe('');

      await localitySelect.selectOption(targetVal);
      await page.locator('button[type="submit"]:has-text("Save Profile Details")').click();
      await expect(page.locator('text=Profile details updated successfully!')).toBeVisible({ timeout: 10000 });

      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('#profile-locality-select')).toHaveValue(targetVal);

      // Restore original locality cleanly
      await page.locator('#profile-locality-select').selectOption(initialVal);
      await page.locator('button[type="submit"]:has-text("Save Profile Details")').click();
      await expect(page.locator('text=Profile details updated successfully!')).toBeVisible({ timeout: 10000 });
    } finally {
      await context.close();
    }
  });

  test('AUD-M2-02 & AUD-M2-01: Mobile 375px single-row seat map & Desktop sticky Pay CTA visible after Razorpay dismissal', async ({
    browser,
  }) => {
    // 1. Mobile 375x812 single-row seat grid + modal checkout
    const mobileCtx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const mobilePage = await mobileCtx.newPage();

    try {
      await signInViaLoginPage(mobilePage, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await mobilePage.goto('/movies/devara-part-1');
      await mobilePage.waitForLoadState('networkidle');

      await mobilePage.locator('button:has-text(":")').first().click();
      const seatDMobile = mobilePage.locator('button[title^="Seat D"]:not([disabled])').last();
      await expect(seatDMobile).toBeVisible({ timeout: 10000 });

      // Check all 12 seats in Row A lie on one horizontal line (no wrapping) & dialog fits 375px width
      const layoutMetrics = await mobilePage.evaluate(() => {
        const rowAButtons = Array.from(
          document.querySelectorAll('[role="dialog"] button[title^="Seat A"]')
        ) as HTMLButtonElement[];
        const tops = rowAButtons.map((b) => Math.round(b.getBoundingClientRect().top));
        const rights = rowAButtons.map((b) => b.getBoundingClientRect().right);
        const dialog = document.querySelector('[role="dialog"]') as HTMLElement | null;
        const dialogRect = dialog?.getBoundingClientRect();
        return {
          countA: rowAButtons.length,
          maxTopDelta: tops.length > 0 ? Math.max(...tops) - Math.min(...tops) : 999,
          maxRight: rights.length > 0 ? Math.max(...rights) : 999,
          dialogRight: dialogRect?.right ?? 999,
          docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      });

      expect(layoutMetrics.countA).toBe(12);
      expect(layoutMetrics.maxTopDelta).toBeLessThanOrEqual(2);
      expect(layoutMetrics.maxRight).toBeLessThanOrEqual(layoutMetrics.dialogRight + 2);
      expect(layoutMetrics.docOverflow).toBeLessThanOrEqual(1);

      // Select available Classic seat and verify pinned footer Pay CTA sits inside 812px viewport
      await seatDMobile.scrollIntoViewIfNeeded();
      await seatDMobile.click();
      const mobilePayBtn = mobilePage.locator('[role="dialog"] button:has-text("Pay ₹")');
      await expect(mobilePayBtn).toBeVisible({ timeout: 5000 });
      const btnBox = await mobilePayBtn.boundingBox();
      expect(btnBox).not.toBeNull();
      expect(btnBox!.y + btnBox!.height).toBeLessThanOrEqual(812);
    } finally {
      await mobileCtx.close();
    }

    // 2. Desktop 1440x900 Razorpay dismissal keeps error alert + Pay CTA inside viewport
    const deskCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const deskPage = await deskCtx.newPage();
    const rzpStub: RazorpayStubController = await installRazorpayTestStub(deskPage, 'dismiss');

    try {
      await signInViaLoginPage(deskPage, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await deskPage.goto('/movies/devara-part-1');
      await deskPage.waitForLoadState('networkidle');

      await deskPage.locator('button:has-text(":")').first().click();
      const seatDDesk = deskPage.locator('button[title^="Seat D"]:not([disabled])').last();
      await expect(seatDDesk).toBeVisible({ timeout: 10000 });
      await seatDDesk.click();

      const payBtn = deskPage.locator('[role="dialog"] button:has-text("Pay ₹")');
      await expect(payBtn).toBeVisible({ timeout: 5000 });
      await payBtn.click();

      const alertBanner = deskPage.locator('[role="dialog"] [role="alert"]');
      await expect(alertBanner).toBeVisible({ timeout: 10000 });

      // Both error alert & Pay CTA must fit above 900px fold
      const alertBox = await alertBanner.boundingBox();
      const payBoxAfterError = await payBtn.boundingBox();
      expect(alertBox).not.toBeNull();
      expect(payBoxAfterError).not.toBeNull();
      expect(payBoxAfterError!.y + payBoxAfterError!.height).toBeLessThanOrEqual(900);
      expect(rzpStub.getInvocations().length).toBe(1);
    } finally {
      await deskCtx.close();
    }
  });

  test('AUD-M2-03: Standardized 2-decimal INR formatting on /bookings and confirmation receipt', async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();

    try {
      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await page.goto('/bookings');
      await page.waitForLoadState('networkidle');

      // Check existing booking cards or confirm zero 1-decimal or bare ₹ amounts on price elements
      const bookingPrices = await page.evaluate(() =>
        Array.from(document.querySelectorAll('span')).map((s) => s.textContent?.trim() || '').filter((t) => /^₹/.test(t))
      );
      if (bookingPrices.length > 0) {
        for (const p of bookingPrices) {
          expect(p, `Non-standard INR formatting on /bookings: ${p}`).toMatch(/^₹[\d,]+\.\d{2}$/);
        }
      }

      const detailLink = page.locator('a[href^="/bookings/"][href$="/confirmation"]').first();
      if ((await detailLink.count()) > 0) {
        await detailLink.click();
        await page.waitForLoadState('networkidle');
        const receiptPrices = await page.evaluate(() =>
          Array.from(document.querySelectorAll('div, span'))
            .map((el) => el.textContent?.trim() || '')
            .filter((t) => /^-?₹[\d,.]+$/.test(t))
        );
        expect(receiptPrices.length).toBeGreaterThan(0);
        for (const p of receiptPrices) {
          expect(p, `Non-standard INR formatting on confirmation page: ${p}`).toMatch(
            /^-?₹[\d,]+\.\d{2}$/
          );
        }
      }
    } finally {
      await ctx.close();
    }
  });

  test('AUD-M3-01 & AUD-M4-02: Partner Cinema untruncated inputs/showtimes & Admin Refund Ledger full audit reason modal', async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();

    try {
      // 1. Cinema Partner Listings check
      await signInViaLoginPage(page, 'cinema.partner@gobeyond.com', 'Partner@123', /\/partner/);
      await page.locator('aside button:has-text("Listings & Catalog")').click();
      await expect(page.locator('text=Cinema Multiplex Configuration')).toBeVisible({ timeout: 10000 });
      // Address & Amenities now use multi-line <textarea>
      expect(await page.locator('textarea').count()).toBeGreaterThanOrEqual(2);
      // Showtimes display untruncated HH:MM without ellipsis truncation
      const showsSection = page.locator('div.rounded-2xl:has(h3:has-text("Active Scheduled Shows"))').first();
      await expect(showsSection).toBeVisible();
      await expect(showsSection).toContainText(/\d{4}-\d{2}-\d{2}\s*·\s*\d{2}:\d{2}/);
      await signOutViaNavbar(page);

      // 2. Super Admin Refund Ledger Audit Reason visibility & detail modal
      await signInViaLoginPage(page, 'admin@gobeyond.com', 'Admin@123', /\/admin/);
      await page.locator('aside button:has-text("Financials & Payments")').click();
      const refundTabBtn = page.locator('button:has-text("Refund Ledger")');
      await expect(refundTabBtn).toBeVisible({ timeout: 10000 });
      await refundTabBtn.click();

      const viewAuditBtn = page.locator('button:has-text("View Audit Note")').first();
      if ((await viewAuditBtn.count()) > 0) {
        await viewAuditBtn.click();
        const modal = page.locator('[role="dialog"]:has-text("Refund Audit Record")');
        await expect(modal).toBeVisible({ timeout: 5000 });
        await expect(modal).toContainText('Full Audit Reason');
        await modal.locator('button:has-text("Close")').click();
      }
      await signOutViaNavbar(page);
    } finally {
      await ctx.close();
    }
  });

  test('AUD-M5-01: Authenticated 375px navbar displays full Hyderabad pill & zero horizontal overflow across 1440/1280/768/390/375', async ({
    browser,
  }) => {
    const viewports = [
      { width: 1440, height: 900 },
      { width: 1280, height: 800 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
      { width: 375, height: 812 },
    ];

    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage();

    try {
      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);

      for (const vp of viewports) {
        await page.setViewportSize(vp);
        for (const route of ['/', '/movies', '/sports', '/activities', '/profile', '/bookings']) {
          await page.goto(route);
          await page.waitForLoadState('networkidle');
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth
          );
          expect(overflow, `Overflow on ${route} at ${vp.width}x${vp.height}`).toBeLessThanOrEqual(1);

          if (vp.width === 375) {
            const locPill = page.locator('header button[aria-label^="Change location"]');
            await expect(locPill).toBeVisible();
            const isClipped = await locPill.evaluate((btn) => {
              const visibleSpan = Array.from(btn.querySelectorAll('span')).find(
                (s) => window.getComputedStyle(s).display !== 'none'
              );
              if (!visibleSpan) return true;
              return visibleSpan.scrollWidth > visibleSpan.clientWidth + 1;
            });
            expect(isClipped, `Navbar location pill clipped at 375px on ${route}`).toBe(false);
          }
        }
      }
    } finally {
      await ctx.close();
    }
  });

  test('PAY-BLOCKER-01: Silent Razorpay iframe init stall clears loading spinner, cleans overlay, releases seat & allows dismiss/fail retry', async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    const rzpStub: RazorpayStubController = await installRazorpayTestStub(page, 'stall');
    const reportFailureStatuses: number[] = [];

    page.on('response', (res) => {
      if (res.url().endsWith('/api/v1/payments/report-failure')) {
        reportFailureStatuses.push(res.status());
      }
    });

    try {
      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await page.goto('/movies/devara-part-1');
      await page.waitForLoadState('networkidle');

      await page.locator('button:has-text(":")').first().click();
      const seatBtn = page.locator('[role="dialog"] button[title^="Seat D"]:not([disabled])').last();
      await expect(seatBtn).toBeVisible({ timeout: 10000 });
      const seatTitle = (await seatBtn.getAttribute('title')) || '';
      await seatBtn.click();

      const payBtn = page.locator('[role="dialog"] button:has-text("Pay ₹")');
      await expect(payBtn).toBeVisible({ timeout: 5000 });

      // 1. Stall mode: open() injects hidden 0x0 .razorpay-container with no callbacks -> watchdog recovers (~8s)
      await payBtn.click();
      await expect(page.locator('[role="dialog"] [role="alert"]')).toContainText(
        /did not open in time|closed unexpectedly|could not initialize/i,
        { timeout: 15000 }
      );
      await expect(payBtn).toBeEnabled();
      expect(await payBtn.locator('svg.animate-spin').count()).toBe(0);
      expect(await page.locator('.razorpay-container').count()).toBe(0);
      expect(reportFailureStatuses).toContain(200);

      // Verify seat lock was released on backend (exact seat still selectable on retry)
      await expect(page.locator(`[role="dialog"] button[title="${seatTitle}"]:not([disabled])`)).toBeVisible();

      // 2. Retry same seat -> dismissal resets loading state & releases seat cleanly
      rzpStub.setMode('dismiss');
      await payBtn.click();
      await expect(page.locator('[role="dialog"] [role="alert"]')).toContainText(
        /cancelled before completion/i,
        { timeout: 10000 }
      );
      await expect(payBtn).toBeEnabled();
      expect(await payBtn.locator('svg.animate-spin').count()).toBe(0);

      // 3. Retry same seat -> payment.failed resets loading state & releases seat cleanly
      rzpStub.setMode('fail');
      await payBtn.click();
      await expect(page.locator('[role="dialog"] [role="alert"]')).toContainText(
        /E2E simulated payment authorization decline/i,
        { timeout: 10000 }
      );
      await expect(payBtn).toBeEnabled();
      expect(await payBtn.locator('svg.animate-spin').count()).toBe(0);

      expect(rzpStub.getInvocations().length).toBe(3);
    } finally {
      await ctx.close();
    }
  });

  test('PAY-BLOCKER-02: Un-stubbed Checkout.js loads, backend /create-order issues order_id, sandbox 401/fault recovers cleanly for retry without infinite spinner', async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();

    let checkoutJsStatus: number | null = null;
    const createOrderPayloads: Array<Record<string, any>> = [];
    const reportFailurePayloads: Array<Record<string, any>> = [];

    page.on('response', async (res) => {
      const url = res.url();
      if (url === 'https://checkout.razorpay.com/v1/checkout.js') {
        checkoutJsStatus = res.status();
      } else if (url.endsWith('/api/v1/payments/create-order')) {
        try {
          createOrderPayloads.push(await res.json());
        } catch {}
      } else if (url.endsWith('/api/v1/payments/report-failure')) {
        try {
          reportFailurePayloads.push(await res.json());
        } catch {}
      }
    });

    try {
      await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);
      await page.goto('/movies/devara-part-1');
      await page.waitForLoadState('networkidle');

      await page.locator('button:has-text(":")').first().click();
      const seatBtn = page.locator('[role="dialog"] button[title^="Seat D"]:not([disabled])').last();
      await expect(seatBtn).toBeVisible({ timeout: 10000 });
      await seatBtn.click();

      const payBtn = page.locator('[role="dialog"] button:has-text("Pay ₹")');
      await expect(payBtn).toBeVisible({ timeout: 5000 });

      // Attempt 1 (un-stubbed real Razorpay SDK)
      await payBtn.click();
      const alertBanner = page.locator('[role="dialog"] [role="alert"]');
      await expect(alertBanner).toBeVisible({ timeout: 15000 });
      await expect(payBtn).toBeEnabled();
      expect(await payBtn.locator('svg.animate-spin').count()).toBe(0);
      expect(await page.locator('.razorpay-container').count()).toBe(0);

      expect(checkoutJsStatus).toBe(200);
      expect(createOrderPayloads.length).toBeGreaterThanOrEqual(1);
      expect(createOrderPayloads[0].order_id).toMatch(/^order_/);
      expect(createOrderPayloads[0].amount).toBeGreaterThan(0);
      expect(reportFailurePayloads.length).toBeGreaterThanOrEqual(1);
      expect(reportFailurePayloads[0].inventory_released).toBe(true);

      // Attempt 2: Retry immediately on same still-selected seat without reload
      await payBtn.click();
      await expect(alertBanner).toBeVisible({ timeout: 15000 });
      await expect(payBtn).toBeEnabled();
      expect(await payBtn.locator('svg.animate-spin').count()).toBe(0);
      expect(createOrderPayloads.length).toBeGreaterThanOrEqual(2);
      expect(createOrderPayloads[1].order_id).not.toBe(createOrderPayloads[0].order_id);
    } finally {
      await ctx.close();
    }
  });
});