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

async function maybeScreenshot(page: Page, filename: string) {
  const dir = process.env.E2E_SCREENSHOT_DIR;
  if (dir) {
    await page.screenshot({ path: `${dir}/${filename}`, fullPage: true });
  }
}

test.describe.serial('GO BEYOND - Production End-to-End Platform Workflows (All 5 Verticals + 3 Roles)', () => {
  let contextPage: Page;
  let rzpStub: RazorpayStubController;
  let capturedMovieQrToken = '';
  let capturedMovieBookingRef = '';

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    contextPage = await context.newPage();
    rzpStub = await installRazorpayTestStub(contextPage, 'paid');
  });

  test.afterAll(async () => {
    if (contextPage) {
      await contextPage.context().close();
    }
  });

  test('1. Public discovery pages render across all 5 verticals and protected portals gate unauthenticated access', async () => {
    const page = contextPage;
    await page.goto('/');
    await expect(page.locator('header')).toContainText('BEYOND');
    await expect(page.locator('button:has-text("Hyderabad")').first()).toBeVisible();

    await page.goto('/movies');
    await expect(page.locator('h1')).toContainText('Movies in Hyderabad');
    await expect(page.locator('a[href^="/movies/"]').first()).toBeVisible();

    await page.goto('/dining');
    await expect(page.locator('h1')).toContainText('Dining & Culinary Experiences');
    await expect(page.locator('a[href^="/dining/"]').first()).toBeVisible();

    await page.goto('/events');
    await expect(page.locator('h1')).toContainText('Live Events & Concerts');
    await expect(page.locator('a[href^="/events/"]').first()).toBeVisible();

    await page.goto('/sports');
    await expect(page.locator('h1')).toContainText('Sports Venues & Turfs');
    await expect(page.locator('a[href^="/activities/"]').first()).toBeVisible();

    await page.goto('/activities');
    await expect(page.locator('h1')).toContainText('Activities & Recreation');
    await expect(page.locator('a[href^="/activities/"]').first()).toBeVisible();

    await page.goto('/partner');
    await expect(page.locator('h2:has-text("Partner Portal")')).toBeVisible();
    await expect(page.locator('button:has-text("Sign In to Business Console")')).toBeVisible();

    await page.goto('/admin');
    await expect(page.locator('h1:has-text("Restricted Area")')).toBeVisible();
    await expect(page.locator('button:has-text("Authenticate with Admin Credentials")')).toBeVisible();
  });

  test('2. Customer Sign-In & Vertical 1 (Movies): Seat selection, Razorpay sandbox verification & QR pass confirmation', async () => {
    const page = contextPage;
    await signInViaLoginPage(page, 'customer@gobeyond.com', 'Customer@123', /\/profile/);

    await page.goto('/movies');
    await page.locator('a[href^="/movies/"]').first().click();
    await expect(page.locator('h2:has-text("Cinema Shows & Timings")')).toBeVisible();

    // Open first active showtime
    await page.locator('button:has-text(":")').first().click();
    const availableSeat = page.locator('button[title^="Seat "]:not([disabled])').first();
    await expect(availableSeat).toBeVisible({ timeout: 10000 });
    await availableSeat.click();

    await expect(page.locator('text=Final Payable:')).toBeVisible();
    await page.locator('button:has-text("Pay ₹")').click();

    await expect(page.locator('h3:has-text("Booking Confirmed!")')).toBeVisible({ timeout: 15000 });
    await page.locator('button:has-text("View Confirmation & Pass")').click();

    await expect(page).toHaveURL(/\/bookings\/GB-.*\/confirmation/);
    await expect(page.locator('text=Official Gate Pass')).toBeVisible();

    const qrLocator = page.locator('span.font-mono.text-gray-600').first();
    await expect(qrLocator).toBeVisible();
    capturedMovieQrToken = (await qrLocator.innerText()).trim();
    expect(capturedMovieQrToken).toMatch(/^GB-PASS-/);

    const urlMatch = page.url().match(/\/bookings\/([^/]+)\/confirmation/);
    capturedMovieBookingRef = urlMatch ? urlMatch[1] : '';
    expect(capturedMovieBookingRef).toMatch(/^GB-/);

    await maybeScreenshot(page, 'e2e_1_customer_movie_pass.png');
  });

  test('3. Customer Vertical 2 (Dining): Table reservation flow on future date', async () => {
    const page = contextPage;
    await page.goto('/dining');
    await page.waitForLoadState('networkidle');

    // Switch location filter to All Hyderabad so restaurants with seeded tables render reliably
    await page.locator('header button:has-text("Hyderabad")').first().click();
    const allCityOption = page.locator('text=All Hyderabad').first();
    await expect(allCityOption).toBeVisible({ timeout: 5000 });
    await allCityOption.click();

    // Pick a seeded restaurant with dining tables (Farzi or Paradise)
    const bookableRestaurant = page.locator('a[href^="/dining/farzi"], a[href^="/dining/paradise"]').first();
    await expect(bookableRestaurant).toBeVisible({ timeout: 10000 });
    await bookableRestaurant.click();
    await expect(page.locator('h3:has-text("Reserve a Dining Table")')).toBeVisible();

    // Dynamic future date (+12 to +29 days) so repeated test runs stay conflict-free
    const futureOffset = 12 + (Math.floor(Date.now() / 10000) % 18);
    const futureDate = new Date(Date.now() + futureOffset * 86400000).toISOString().split('T')[0];
    await page.locator('input[type="date"]').fill(futureDate);
    await page.getByRole('button', { name: '2', exact: true }).click();
    await page.locator('button:has-text("20:30")').click();
    await page.locator('button:has-text("Confirm Reservation")').click();

    await expect(page.locator('h4:has-text("Table Reserved!")')).toBeVisible({ timeout: 15000 });
  });

  test('4. Customer Vertical 3 (Events): Tiered ticket selection & confirmation', async () => {
    const page = contextPage;
    await page.goto('/events');
    // Click seeded event with ticket tiers
    await page.locator('a[href="/events/sunburn-arena-alan-walker-hyderabad"], a[href="/events/zakir-khan-live-hyderabad"]').first().click();
    await expect(page.locator('h3:has-text("Select Ticket Passes")')).toBeVisible();

    const plusBtn = page.locator('button:has(svg.lucide-plus):not([disabled])').first();
    await expect(plusBtn).toBeVisible();
    await plusBtn.click();

    await page.locator('button:has-text("Pay ₹")').click();
    await expect(page.locator('h4:has-text("Tickets Confirmed!")')).toBeVisible({ timeout: 15000 });
  });

  test('5. Customer Vertical 4 (Sports): Turf/court slot booking with canonical 1x + 18% GST pricing verification', async () => {
    const page = contextPage;
    await page.goto('/sports');
    await page.locator('a[href^="/activities/"]:has-text("Book Slot")').first().click();
    await expect(page.locator('h3:has-text("Select Time Slot")')).toBeVisible();

    const firstSlotBtn = page.locator('button:not([disabled]):has-text("left")').first();
    await expect(firstSlotBtn).toBeVisible();
    const slotText = await firstSlotBtn.innerText();
    const slotPriceMatch = slotText.match(/₹(\d+)/);
    const slotPrice = slotPriceMatch ? Number(slotPriceMatch[1]) : 0;
    expect(slotPrice).toBeGreaterThan(0);

    await firstSlotBtn.click();

    // Verify canonical 1x slot price + 18% GST (never doubled)
    const payBtn = page.locator('button:has-text("Pay ₹")');
    await expect(payBtn).toBeVisible();
    const payBtnText = await payBtn.innerText();
    const payMatch = payBtnText.match(/Pay ₹([\d.]+)/);
    const actualPayable = payMatch ? Number(payMatch[1]) : 0;
    const expectedPayable = Number((slotPrice * 1.18).toFixed(2));
    expect(Math.abs(actualPayable - expectedPayable)).toBeLessThanOrEqual(0.02);

    await payBtn.click();
    await expect(page.locator('h4:has-text("Booking Confirmed!")')).toBeVisible({ timeout: 15000 });
  });

  test('6. Customer Vertical 5 (Activities) & Session Persistence across reloads + Sign Out', async () => {
    const page = contextPage;
    await page.goto('/activities');
    await page.getByRole('button', { name: 'Adventure', exact: true }).click();
    const adventureCard = page.locator('a[href^="/activities/"]').first();
    await expect(adventureCard).toBeVisible();
    await adventureCard.click();

    const slotBtn = page.locator('button:not([disabled]):has-text("left")').first();
    await expect(slotBtn).toBeVisible();
    await slotBtn.click();
    await page.locator('button:has-text("Pay ₹")').click();
    await expect(page.locator('h4:has-text("Booking Confirmed!")')).toBeVisible({ timeout: 15000 });

    // Verify My Bookings & Notification Centre survive hard browser reload via HttpOnly refresh + Path=/ CSRF
    await page.goto('/bookings');
    await expect(page.locator('h1:has-text("My Bookings & Passes")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${capturedMovieBookingRef}`)).toBeVisible({ timeout: 10000 });
    await page.waitForLoadState('networkidle');

    await page.reload();
    await expect(page.locator('h1:has-text("My Bookings & Passes")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${capturedMovieBookingRef}`)).toBeVisible({ timeout: 10000 });

    await page.goto('/notifications');
    await expect(page.locator('h1:has-text("Notification Centre")')).toBeVisible({ timeout: 10000 });

    await signOutViaNavbar(page);
  });

  test('7. Cinema Partner Console: Financials ledger & Gate QR Scanner admission audit for Movie pass', async () => {
    const page = contextPage;
    await signInViaLoginPage(page, 'cinema.partner@gobeyond.com', 'Partner@123', /\/partner/);

    await expect(page.locator('text=AMB Cinemas').first()).toBeVisible({ timeout: 10000 });

    // Switch to Financials & Payouts tab
    await page.locator('aside button:has-text("Financials & Payouts")').click();
    await expect(page.locator('text=Transaction Settlement Ledger')).toBeVisible();
    await expect(page.locator('text=CONSERVED')).toBeVisible();

    // Switch to Gate QR Scanner & admit captured movie pass
    await page.locator('aside button:has-text("Gate QR Scanner")').click();
    await expect(page.locator('h3:has-text("Gate Admission QR Pass Scanner")')).toBeVisible();

    const qrInput = page.locator('input[placeholder*="Enter QR token"]');
    await qrInput.fill(capturedMovieQrToken);
    await page.locator('button[type="submit"]:has-text("Validate")').click();

    await expect(page.locator('text=Admitted & logged to append-only audit trail')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${capturedMovieBookingRef}`).first()).toBeVisible();

    await maybeScreenshot(page, 'e2e_2_partner_qr_scanner.png');
    await signOutViaNavbar(page);
  });

  test('8. Super Admin Console: Executive KPIs, Partner Management, Financials, Worker/Outbox & Audit Logs', async () => {
    const page = contextPage;
    await signInViaLoginPage(page, 'admin@gobeyond.com', 'Admin@123', /\/admin/);

    await expect(page.locator('h1:has-text("System Executive Overview")')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Captured Revenue')).toBeVisible();
    await expect(page.locator('text=Platform Commission')).toBeVisible();
    await expect(page.locator('text=Partner Payouts Payable')).toBeVisible();

    await page.locator('aside button:has-text("Partner Management")').click();
    await expect(page.locator('h1:has-text("Partner Management")')).toBeVisible();

    await page.locator('aside button:has-text("Customer Directory")').click();
    await page.locator('input[placeholder="Search customer name, email, phone..."]').fill('customer@gobeyond.com');
    await expect(page.locator('text=customer@gobeyond.com').first()).toBeVisible({ timeout: 10000 });

    await page.locator('aside button:has-text("Booking Operations")').click();
    await expect(page.locator(`text=${capturedMovieBookingRef}`).first()).toBeVisible({ timeout: 10000 });

    await page.locator('aside button:has-text("Financials & Payments")').click();
    await expect(page.locator('text=RAZORPAY').first()).toBeVisible({ timeout: 10000 });

    await page.locator('aside button:has-text("Worker & Outbox")').click();
    await expect(page.locator('text=HEALTHY').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=MOCK_').first()).toBeVisible({ timeout: 10000 });

    await page.locator('aside button:has-text("Immutable Audit Logs")').click();
    await expect(page.locator('text=QR_PASS_SCANNED').first()).toBeVisible({ timeout: 10000 });

    await maybeScreenshot(page, 'e2e_3_admin_audit_logs.png');
    expect(rzpStub.getInvocations().length).toBeGreaterThanOrEqual(4);
    await signOutViaNavbar(page);
  });
});
