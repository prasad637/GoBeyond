import { ApiError, getAccessToken, singleFlightRefreshToken } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PartnerTabId =
  | "overview"
  | "listings"
  | "schedules"
  | "bookings"
  | "scanner"
  | "financials"
  | "notifications"
  | "settings";

export interface PartnerProfile {
  id: number;
  user_id: number;
  business_name: string;
  partner_type: string;
  contact_email: string;
  contact_phone: string;
  gstin?: string | null;
  pan_number?: string | null;
  commission_rate: number;
  status: string;
  verified_at?: string | null;
}

export interface PartnerDocument {
  id: number;
  partner_id: number;
  document_type: string;
  document_url: string;
  status: string;
  uploaded_at: string;
}

export interface PartnerDailyStat {
  date: string;
  bookings: number;
  revenue: number;
}

export interface PartnerRecentBooking {
  id: number;
  reference: string;
  type: string;
  status: string;
  amount: number;
  customer_name: string;
  created_at: string;
  items_count: number;
}

export interface PartnerAnalytics {
  partner_type: string;
  business_name: string;
  status: string;
  commission_rate: number;
  total_listings: number;
  total_bookings: number;
  confirmed_bookings: number;
  pending_bookings: number;
  cancelled_bookings: number;
  refunded_bookings: number;
  total_revenue: number;
  gross_revenue: number;
  platform_fee: number;
  partner_payout: number;
  daily_stats: PartnerDailyStat[];
  recent_bookings: PartnerRecentBooking[];
}

export interface PartnerBookingItem {
  id: number;
  booking_reference: string;
  booking_type: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  status: string;
  amount: number;
  created_at: string;
  qr_code_token?: string | null;
  items: {
    id: number;
    item_type: string;
    name: string;
    quantity: number;
    unit_price: number;
    subtotal: number;
    details?: Record<string, any>;
  }[];
}

export interface PartnerFinancialTransaction {
  booking_id: number;
  booking_reference: string;
  booking_type: string;
  status: string;
  created_at: string;
  gross_amount: number;
  captured_amount: number;
  refund_amount: number;
  net_collected: number;
  commission_rate: number;
  platform_fee: number;
  partner_payout: number;
}

export interface PartnerFinancials {
  partner_id: number;
  business_name: string;
  partner_type: string;
  commission_rate: number;
  gross_confirmed_booking_value: number;
  total_captured_payments: number;
  total_refunded_amount: number;
  net_collected_amount: number;
  actual_platform_revenue: number;
  partner_settlements_payable: number;
  total_over_refunded_amount?: number;
  requires_financial_reconciliation?: boolean;
  transactions: PartnerFinancialTransaction[];
}

export interface QRVerificationResult {
  valid: boolean;
  booking_reference: string;
  booking_type: string;
  customer_name: string;
  status: string;
  items: { name: string; quantity: number; details?: Record<string, any> }[];
  message: string;
  scanned_at?: string;
}

export interface RestaurantProfile {
  id: number;
  name: string;
  slug: string;
  cuisines: string[];
  cost_for_two: number;
  address: string;
  phone?: string | null;
  timings?: string | null;
  images?: string[];
  rating?: number;
  review_count?: number;
  has_buffet: boolean;
  has_alcohol: boolean;
  is_pure_veg: boolean;
  is_active: boolean;
}

export interface MenuItemRecord {
  id: number;
  restaurant_id: number;
  category: string;
  item_name: string;
  description?: string | null;
  price: number;
  is_veg: boolean;
  is_bestseller: boolean;
  image_url?: string | null;
  is_available: boolean;
}

export interface DiningTableRecord {
  id: number;
  restaurant_id: number;
  table_number: string;
  capacity: number;
  zone: string;
  is_active: boolean;
}

export interface ReservationRecord {
  id: number;
  table_id?: number | null;
  table_number: string;
  table_zone: string;
  guest_count: number;
  customer_name: string;
  customer_phone: string;
  reservation_date: string;
  reservation_time: string;
  duration_minutes?: number;
  special_requests?: string | null;
  status: string;
  booking_reference?: string | null;
}

export interface CinemaProfile {
  id: number;
  name: string;
  address: string;
  city?: string | null;
  amenities: string[];
  is_active: boolean;
}

export interface ScreenRecord {
  id: number;
  cinema_id: number;
  name: string;
  screen_type: string;
  total_seats: number;
}

export interface SeatRecord {
  id: number;
  screen_id: number;
  row_code: string;
  seat_number: number;
  tier: string;
  base_price: number;
  is_accessible: boolean;
}

export interface MovieSummary {
  id: number;
  title: string;
  language?: string;
  duration_minutes?: number;
  certification?: string;
}

export interface MovieShowRecord {
  id: number;
  movie_id: number;
  movie_title: string;
  screen_id: number;
  screen_name: string;
  screen_type: string;
  show_date: string;
  start_time: string;
  end_time: string;
  price_multiplier: number;
  status: string;
}

export interface EventRecord {
  id: number;
  title: string;
  slug: string;
  category: string;
  venue_name: string;
  venue_address: string;
  start_datetime: string;
  end_datetime: string;
  description?: string | null;
  artist_names?: string | null;
  banner_url?: string | null;
  is_featured: boolean;
  is_active: boolean;
}

export interface EventTicketTypeRecord {
  id: number;
  event_id?: number;
  name: string;
  description?: string | null;
  price: number;
  total_quantity: number;
  available_quantity: number;
  sold_quantity?: number;
  max_per_booking: number;
}

export interface EventDetailRecord extends EventRecord {
  ticket_types: EventTicketTypeRecord[];
}

export interface EventAttendeeRecord {
  booking_reference: string;
  attendee_name: string;
  attendee_phone: string;
  attendee_email: string;
  ticket_type: string;
  quantity: number;
  booked_at: string;
  qr_token?: string | null;
}

export interface SportsVenueRecord {
  id: number;
  name: string;
  sport_types: string[];
  address: string;
  amenities: string[];
  images: string[];
  rating?: number;
  is_active: boolean;
}

export interface ActivityRecord {
  id: number;
  venue_id?: number | null;
  title: string;
  slug: string;
  category: string;
  base_price: number;
  duration_minutes: number;
  min_age: number;
  description?: string | null;
  image_url?: string | null;
  is_active: boolean;
}

export interface ActivitySlotRecord {
  id: number;
  activity_id: number;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
  booked_count: number;
  available_count?: number;
  price_override?: number | null;
  effective_price?: number;
  is_available: boolean;
}

export interface PartnerNotificationRecord {
  id: number;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  data?: Record<string, any>;
  created_at: string;
}

export function getVerticalLabels(partnerType: string): {
  badge: string;
  catalogTitle: string;
  scheduleTitle: string;
} {
  switch (partnerType) {
    case "RESTAURANT":
      return {
        badge: "Dining & Culinary",
        catalogTitle: "Menu, Tables & Venue",
        scheduleTitle: "Table Reservations",
      };
    case "CINEMA":
      return {
        badge: "Cinema & Multiplex",
        catalogTitle: "Screens, Seats & Shows",
        scheduleTitle: "Showtime Matrix",
      };
    case "EVENT":
      return {
        badge: "Live Events & Concerts",
        catalogTitle: "Events & Ticket Tiers",
        scheduleTitle: "Attendee Manifest",
      };
    case "SPORTS":
    case "ACTIVITIES":
      return {
        badge: partnerType === "SPORTS" ? "Sports & Turfs" : "Activities & Recreation",
        catalogTitle: "Venues & Activities",
        scheduleTitle: "Court & Batch Slots",
      };
    default:
      return {
        badge: partnerType || "Partner",
        catalogTitle: "Catalog & Inventory",
        scheduleTitle: "Schedules & Operations",
      };
  }
}

export function exportRowsToCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const escape = (val: string | number) => {
    const str = String(val ?? "");
    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };
  const csv = [headers.map(escape).join(","), ...rows.map((r) => r.map(escape).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

/**
 * Direct multipart file upload for `/api/v1/partners/documents/upload-file`.
 * Intentionally omits Content-Type so the browser writes the multipart boundary.
 */
export async function uploadPartnerKycFile(
  file: File,
  documentType: string,
  isRetry = false
): Promise<{ success: boolean; message: string; document_url: string; document_id: number }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType.toUpperCase());

  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const csrf = getCookie("gobeyond_csrf_token");
  if (csrf) headers["X-CSRF-Token"] = csrf;

  const res = await fetch(`${API_BASE_URL}/api/v1/partners/documents/upload-file`, {
    method: "POST",
    headers,
    body: formData,
    credentials: "include",
  });

  if (res.status === 401 && !isRetry) {
    const nextToken = await singleFlightRefreshToken();
    if (nextToken) {
      return uploadPartnerKycFile(file, documentType, true);
    }
  }

  if (!res.ok) {
    let message = `Upload failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) {
        message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore non-json
    }
    throw new ApiError(res.status, message);
  }

  return res.json();
}

