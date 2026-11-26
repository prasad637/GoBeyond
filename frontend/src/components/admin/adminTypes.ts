export type AdminTabId =
  | "overview"
  | "partners"
  | "users"
  | "bookings"
  | "financials"
  | "coupons"
  | "broadcasts"
  | "worker"
  | "audit";

export interface AdminStats {
  total_users: number;
  total_customers: number;
  total_partners: number;
  approved_partners: number;
  pending_partner_verifications: number;
  suspended_partners: number;
  total_bookings: number;
  confirmed_bookings: number;
  vertical_bookings: Record<string, number>;
  total_revenue: number;
  gross_confirmed_booking_value: number;
  total_captured_payments: number;
  total_refunded_amount: number;
  net_collected_amount: number;
  actual_platform_revenue: number;
  partner_settlements_payable: number;
  total_over_refunded_amount: number;
  over_refunded_bookings_count: number;
  requires_financial_reconciliation: boolean;
  total_movies: number;
  total_restaurants: number;
  total_events: number;
  total_sports_activities: number;
  daily_trends: { date: string; bookings: number; gross_revenue: number }[];
  monthly_trends: { month: string; bookings: number; gross_revenue: number }[];
}

export interface AdminPartnerItem {
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
  created_at?: string | null;
  documents_count: number;
}

export interface AdminPartnerDocument {
  id: number;
  document_type: string;
  document_url: string;
  status: string;
  uploaded_at: string;
}

export interface AdminPartnerDetail extends AdminPartnerItem {
  total_listings: number;
  total_bookings: number;
  gross_booking_value: number;
  platform_fee: number;
  partner_payout: number;
  documents: AdminPartnerDocument[];
}

export interface AdminUserItem {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  roles: string[];
  is_active: boolean;
  is_verified: boolean;
  account_status: string;
  created_at?: string;
  total_bookings: number;
  city_name?: string | null;
  locality_name?: string | null;
}

export interface AdminUserBookingSummary {
  id: number;
  booking_reference: string;
  booking_type: string;
  status: string;
  final_payable: number;
  created_at: string;
  items_count: number;
}

export interface AdminBookingItem {
  id: number;
  booking_reference: string;
  booking_type: string;
  status: string;
  final_payable: number;
  customer_name: string;
  customer_email: string;
  items_summary: string;
  created_at: string;
}

export interface AdminBookingDetail {
  id: number;
  booking_reference: string;
  booking_type: string;
  status: string;
  total_amount: number;
  tax_amount: number;
  discount_amount: number;
  final_payable: number;
  created_at?: string;
  customer: {
    id?: number;
    name: string;
    email: string;
    phone: string;
  };
  items: {
    id: number;
    item_type: string;
    item_id: number;
    name: string;
    quantity: number;
    unit_price: number;
    subtotal: number;
    details: Record<string, any>;
  }[];
  payments: {
    id: number;
    gateway_payment_id?: string | null;
    gateway_order_id?: string | null;
    amount: number;
    currency: string;
    status: string;
    payment_gateway: string;
    created_at?: string;
  }[];
  refunds: {
    id: number;
    gateway_refund_id?: string | null;
    amount: number;
    reason?: string | null;
    status: string;
    created_at?: string;
  }[];
  cancellation_reason?: string | null;
}

export interface AdminPaymentItem {
  id: number;
  booking_id: number;
  booking_reference: string;
  customer_name: string;
  customer_email: string;
  gateway_payment_id?: string | null;
  gateway_order_id?: string | null;
  amount: number;
  currency: string;
  status: string;
  payment_gateway: string;
  created_at: string;
}

export interface AdminRefundItem {
  id: number;
  booking_id: number;
  booking_reference: string;
  customer_name: string;
  gateway_refund_id?: string | null;
  amount: number;
  status: string;
  reason?: string | null;
  created_at: string;
}

export interface ReconciliationReport {
  is_healthy: boolean;
  total_bookings_audited: number;
  total_payments_audited: number;
  total_refunds_audited: number;
  total_captured_amount: number;
  total_refunded_amount: number;
  net_collected_amount: number;
  platform_revenue: number;
  partner_settlements: number;
  discrepancies_count: number;
  discrepancies: {
    code: string;
    severity: string;
    booking_reference?: string | null;
    payment_id?: number | null;
    gateway_id?: string | null;
    description: string;
    suggested_action: string;
    details: Record<string, any>;
  }[];
  audited_at: string;
}

export interface AdminCouponItem {
  id: number;
  code: string;
  description?: string | null;
  discount_type: string;
  discount_value: number;
  min_order_value: number;
  max_discount: number;
  usage_limit: number;
  used_count: number;
  valid_until?: string | null;
  is_active: boolean;
}

export interface AdminNotificationItem {
  id: number;
  user_id: number;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export interface WorkerStatus {
  is_healthy: boolean;
  redis_connected: boolean;
  queue_name: string;
  pending_jobs_count: number;
  processing_jobs_count: number;
  delivered_jobs_count: number;
  failed_jobs_count: number;
  dead_letter_jobs_count: number;
  active_workers_count: number;
  checked_at: string;
}

export interface NotificationOutboxItem {
  id: number;
  event_type: string;
  user_id: number;
  channel: string;
  recipient: string;
  title: string;
  content: string;
  status: string;
  retry_count: number;
  max_retries: number;
  last_attempt_at?: string | null;
  next_retry_at?: string | null;
  error_message?: string | null;
  provider_name?: string | null;
  provider_metadata?: Record<string, any>;
  idempotency_key?: string | null;
  is_marketing: boolean;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  user_id?: number | null;
  user_email?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, any>;
  created_at: string;
}

