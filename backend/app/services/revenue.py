"""GO BEYOND — Financial & Revenue Computation Service

Financial Integrity, Accounting Policies & Precision Standards:
================================================================
1. Currency & Precision:
   - Operating currency: INR (₹, Indian Rupee).
   - Base monetary precision: Exactly 2 decimal places (paise precision, 0.01 INR).
   - Database column type: PostgreSQL NUMERIC(12, 2) (Python decimal.Decimal).
   - Commission rate precision: PostgreSQL NUMERIC(5, 4) (e.g. 0.1000 = 10.00%, 0.1250 = 12.50%).

2. Rounding Policy:
   - Rounding mode: decimal.ROUND_HALF_UP (standard commercial and financial rounding).
   - Fractional paise (half a paisa or greater, >= 0.005) round up to the nearest whole paisa.
   - Float arithmetic is strictly prohibited in financial paths to prevent binary representation drift.

3. Tax, Discount, and Net Collected Treatment:
   - Gross Confirmed Booking Value = SUM(booking.final_payable) for status = 'CONFIRMED'.
   - Discounts (coupons / promotions) reduce merchandise value before payment capture.
   - Taxes (GST) are included in the customer's final payable amount.
   - Total Successfully Captured Payments = SUM(unique gateway_payment_id payments with status IN ('CAPTURED', 'SUCCESS')).
   - Total Successfully Refunded Amount = SUM(unique gateway_refund_id refunds with status IN ('PROCESSED', 'SUCCESS')).
   - Net Collected Amount = Total Captured Payments - Total Refunded Amount.

4. Over-Refunds & Financial Reconciliation:
   - Over-refunds occur when refunded amounts exceed captured payments for a given booking.
   - Over-refunds are NEVER silently hidden using GREATEST(0, ...).
   - The actual net collected amount is computed algebraically.
   - If excess refunds occur, total_over_refunded_amount is tracked, affected bookings are counted,
     and requires_financial_reconciliation is flagged as True.
   - Over-refunded bookings have 0 platform revenue and 0 partner settlements (pending dispute resolution).

5. Partner Commission & Multi-Partner Attribution:
   - Commission rates are configurable per partner in the partners table (Numeric(5, 4)).
   - Booking items are mapped to partners across all 5 verticals:
     * MOVIE: seats -> screen -> cinema -> partner
     * DINING: dining_tables -> restaurant -> partner
     * EVENT: event_ticket_types -> event -> partner
     * SPORTS: activity_slots -> activity -> sports_venues -> partner
     * ACTIVITY: activity_slots -> activity -> partner
   - Multi-Partner Bookings: If a booking contains items from multiple partners, each partner
     receives settlement proportional to their item subtotals:
     item_net = booking_net * (item.subtotal / booking_items_total)
     partner_settlement = item_net * (1 - partner.commission_rate)
     platform_revenue = item_net * partner.commission_rate
   - Go Beyond does NOT treat all collected customer money as platform revenue. Only the contractual
     commission take-rate constitutes platform revenue; the remainder is partner settlement payable.
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.partner import Partner
from app.models.event import EventTicketType
from app.models.sports import ActivitySlot
from app.models.dining import DiningTable
from app.models.movie import Seat

TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


def quantize_currency(val: Any) -> Decimal:
    """Rounds a monetary value to exactly 2 decimal places using ROUND_HALF_UP."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_revenue_metrics(
    db: Session,
    booking_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Computes all financial metrics with exact Decimal precision, item-level partner attribution,
    and refund integrity auditing.
    """
    is_postgres = db.bind.dialect.name == "postgresql"

    if booking_ids is not None and len(booking_ids) == 0:
        return {
            "gross_confirmed_booking_value": 0.0,
            "total_captured_payments": 0.0,
            "total_refunded_amount": 0.0,
            "net_collected_amount": 0.0,
            "partner_settlements_payable": 0.0,
            "actual_platform_revenue": 0.0,
            "total_revenue": 0.0,
            "total_over_refunded_amount": 0.0,
            "over_refunded_bookings_count": 0,
            "requires_financial_reconciliation": False,
        }

    where_booking_scope = ""
    where_refund_scope = ""
    params: Dict[str, Any] = {
        "default_commission_rate": Decimal(str(getattr(settings, "DEFAULT_COMMISSION_RATE", 0.1000))).quantize(FOURPLACES)
    }

    if booking_ids is not None:
        where_booking_scope = "AND b.id IN :booking_ids"
        where_refund_scope = "AND r.booking_id IN :booking_ids"
        params["booking_ids"] = tuple(booking_ids)

    if is_postgres:
        sql_metrics = f"""
            WITH booking_captured AS (
                SELECT 
                    p.booking_id,
                    COALESCE(SUM(p.amount), 0.00)::numeric(12, 2) AS captured_amount
                FROM (
                    SELECT 
                        p_inner.booking_id,
                        COALESCE(p_inner.gateway_payment_id, p_inner.id::text) AS gateway_tx_id,
                        MAX(p_inner.amount) AS amount
                    FROM payments p_inner
                    WHERE p_inner.status IN ('CAPTURED', 'SUCCESS', 'PARTIALLY_REFUNDED', 'REFUNDED')
                      AND p_inner.amount > 0
                    GROUP BY p_inner.booking_id, COALESCE(p_inner.gateway_payment_id, p_inner.id::text)
                ) p
                GROUP BY p.booking_id
            ),
            booking_refunded AS (
                SELECT 
                    r.booking_id,
                    COALESCE(SUM(r.amount), 0.00)::numeric(12, 2) AS refund_amount
                FROM (
                    SELECT 
                        r_inner.booking_id,
                        COALESCE(r_inner.gateway_refund_id, r_inner.id::text) AS refund_tx_id,
                        MAX(r_inner.amount) AS amount
                    FROM refunds r_inner
                    WHERE r_inner.status IN ('PROCESSED', 'SUCCESS')
                      AND r_inner.amount > 0
                    GROUP BY r_inner.booking_id, COALESCE(r_inner.gateway_refund_id, r_inner.id::text)
                ) r
                GROUP BY r.booking_id
            ),
            booking_balances AS (
                SELECT 
                    b.id AS booking_id,
                    b.status AS booking_status,
                    COALESCE(bc.captured_amount, 0.00)::numeric(12, 2) AS captured_amount,
                    COALESCE(br.refund_amount, 0.00)::numeric(12, 2) AS refund_amount,
                    (COALESCE(bc.captured_amount, 0.00) - COALESCE(br.refund_amount, 0.00))::numeric(12, 2) AS net_booking_amount,
                    CASE 
                        WHEN COALESCE(br.refund_amount, 0.00) > COALESCE(bc.captured_amount, 0.00) 
                        THEN (COALESCE(br.refund_amount, 0.00) - COALESCE(bc.captured_amount, 0.00))::numeric(12, 2)
                        ELSE 0.00 
                    END AS over_refund_amount
                FROM bookings b
                LEFT JOIN booking_captured bc ON bc.booking_id = b.id
                LEFT JOIN booking_refunded br ON br.booking_id = b.id
                WHERE 1=1 {where_booking_scope}
            ),
            item_level AS (
                SELECT 
                    bi.booking_id,
                    bi.id AS item_id,
                    bi.subtotal AS item_subtotal,
                    COALESCE(pt.commission_rate, :default_commission_rate)::numeric(5, 4) AS commission_rate,
                    SUM(bi.subtotal) OVER (PARTITION BY bi.booking_id) AS booking_items_total
                FROM booking_items bi
                LEFT JOIN partners pt ON pt.id = COALESCE(
                    (SELECT c.partner_id FROM seats st JOIN screens scr ON scr.id = st.screen_id JOIN cinemas c ON c.id = scr.cinema_id WHERE st.id = bi.item_id AND bi.item_type = 'SEAT' LIMIT 1),
                    (SELECT c.partner_id FROM movie_shows ms JOIN screens scr ON scr.id = ms.screen_id JOIN cinemas c ON c.id = scr.cinema_id WHERE bi.details->>'show_id' IS NOT NULL AND (bi.details->>'show_id')::int = ms.id LIMIT 1),
                    (SELECT r.partner_id FROM dining_tables dt JOIN restaurants r ON r.id = dt.restaurant_id WHERE dt.id = bi.item_id AND bi.item_type = 'TABLE' LIMIT 1),
                    (SELECT ev.partner_id FROM event_ticket_types ett JOIN events ev ON ev.id = ett.event_id WHERE ett.id = bi.item_id AND bi.item_type = 'TICKET' LIMIT 1),
                    (SELECT act.partner_id FROM activity_slots acs JOIN activities act ON act.id = acs.activity_id WHERE acs.id = bi.item_id AND bi.item_type = 'SLOT' AND act.partner_id IS NOT NULL LIMIT 1),
                    (SELECT sv.partner_id FROM activity_slots acs JOIN activities act ON act.id = acs.activity_id JOIN sports_venues sv ON sv.id = act.venue_id WHERE acs.id = bi.item_id AND bi.item_type = 'SLOT' AND act.venue_id IS NOT NULL LIMIT 1)
                )
            )
            SELECT 
                (SELECT COALESCE(SUM(b.final_payable), 0.00)::numeric(12, 2) FROM bookings b WHERE b.status = 'CONFIRMED' {where_booking_scope}) AS gross_confirmed,
                (SELECT COALESCE(SUM(tx.amount), 0.00)::numeric(12, 2) FROM (
                    SELECT MAX(p.amount) as amount FROM payments p JOIN bookings b ON b.id = p.booking_id WHERE p.status IN ('CAPTURED', 'SUCCESS', 'PARTIALLY_REFUNDED', 'REFUNDED') AND p.amount > 0 {where_booking_scope} GROUP BY COALESCE(p.gateway_payment_id, p.id::text)
                ) tx) AS total_captured,
                (SELECT COALESCE(SUM(rf.amount), 0.00)::numeric(12, 2) FROM (
                    SELECT MAX(r.amount) as amount FROM refunds r WHERE r.status IN ('PROCESSED', 'SUCCESS') AND r.amount > 0 {where_refund_scope} GROUP BY COALESCE(r.gateway_refund_id, r.id::text)
                ) rf) AS total_refunded,
                (SELECT COALESCE(SUM(over_refund_amount), 0.00)::numeric(12, 2) FROM booking_balances) AS total_over_refunded,
                (SELECT COUNT(*) FROM booking_balances WHERE over_refund_amount > 0) AS over_refunded_count,
                COALESCE(SUM(
                    CASE 
                        WHEN il.item_id IS NOT NULL AND il.booking_items_total > 0 THEN 
                            (bb.net_booking_amount * (il.item_subtotal / il.booking_items_total) * COALESCE(il.commission_rate, :default_commission_rate))
                        WHEN il.item_id IS NOT NULL THEN 
                            (bb.net_booking_amount * COALESCE(il.commission_rate, :default_commission_rate))
                        ELSE 
                            (bb.net_booking_amount * :default_commission_rate)
                    END
                ), 0.00)::numeric(12, 2) AS platform_revenue,
                COALESCE(SUM(
                    CASE 
                        WHEN il.item_id IS NOT NULL AND il.booking_items_total > 0 THEN 
                            (bb.net_booking_amount * (il.item_subtotal / il.booking_items_total) * (1.0000 - COALESCE(il.commission_rate, :default_commission_rate)))
                        WHEN il.item_id IS NOT NULL THEN 
                            (bb.net_booking_amount * (1.0000 - COALESCE(il.commission_rate, :default_commission_rate)))
                        ELSE 
                            (bb.net_booking_amount * (1.0000 - :default_commission_rate))
                    END
                ), 0.00)::numeric(12, 2) AS partner_settlements
            FROM booking_balances bb
            LEFT JOIN item_level il ON il.booking_id = bb.booking_id
            WHERE bb.booking_status = 'CONFIRMED'
              AND bb.net_booking_amount > 0;
        """
        row = db.execute(text(sql_metrics), params).first()
        gross_booking_value = quantize_currency(row[0] if row else 0.00)
        total_captured = quantize_currency(row[1] if row else 0.00)
        total_refunded = quantize_currency(row[2] if row else 0.00)
        total_over_refunded = quantize_currency(row[3] if row else 0.00)
        over_refunded_count = int(row[4] if row else 0)
        platform_revenue = quantize_currency(row[5] if row else 0.00)
        partner_settlements = quantize_currency(row[6] if row else 0.00)

        # Net collected amount is actual cash received minus cash returned (not hidden by GREATEST(0))
        net_collected = quantize_currency(total_captured - total_refunded)

    else:
        # SQLite-compatible fallback using exact Python Decimal
        default_comm_rate = params["default_commission_rate"]
        b_query = db.query(Booking).filter(Booking.status == "CONFIRMED")
        if booking_ids is not None:
            b_query = b_query.filter(Booking.id.in_(booking_ids))
        gross_booking_value = quantize_currency(sum((quantize_currency(b.final_payable) for b in b_query.all()), Decimal("0.00")))

        # Payments query
        p_query = db.query(Payment).filter(Payment.status.in_(["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED", "REFUNDED"]), Payment.amount > 0)
        if booking_ids is not None:
            p_query = p_query.filter(Payment.booking_id.in_(booking_ids))
        
        seen_tx = set()
        booking_captured_map: Dict[int, Decimal] = {}
        for p in p_query.all():
            tx_key = p.gateway_payment_id or str(p.id)
            if tx_key not in seen_tx:
                seen_tx.add(tx_key)
                amt = quantize_currency(p.amount)
                booking_captured_map[p.booking_id] = booking_captured_map.get(p.booking_id, Decimal("0.00")) + amt

        total_captured = quantize_currency(sum(booking_captured_map.values(), Decimal("0.00")))

        # Refunds query
        r_query = db.query(Refund).filter(Refund.status.in_(["PROCESSED", "SUCCESS"]), Refund.amount > 0)
        if booking_ids is not None:
            r_query = r_query.filter(Refund.booking_id.in_(booking_ids))
        
        seen_rf = set()
        booking_refunded_map: Dict[int, Decimal] = {}
        for r in r_query.all():
            rf_key = r.gateway_refund_id or str(r.id)
            if rf_key not in seen_rf:
                seen_rf.add(rf_key)
                amt = quantize_currency(r.amount)
                booking_refunded_map[r.booking_id] = booking_refunded_map.get(r.booking_id, Decimal("0.00")) + amt

        total_refunded = quantize_currency(sum(booking_refunded_map.values(), Decimal("0.00")))
        net_collected = quantize_currency(total_captured - total_refunded)

        # Over-refund audit
        all_booking_ids = set(booking_captured_map.keys()).union(set(booking_refunded_map.keys()))
        if booking_ids is not None:
            all_booking_ids = all_booking_ids.intersection(set(booking_ids))

        total_over_refunded = Decimal("0.00")
        over_refunded_count = 0
        platform_revenue = Decimal("0.00")
        partner_settlements = Decimal("0.00")

        for bid in all_booking_ids:
            b_captured = booking_captured_map.get(bid, Decimal("0.00"))
            b_refunded = booking_refunded_map.get(bid, Decimal("0.00"))
            if b_refunded > b_captured:
                total_over_refunded += (b_refunded - b_captured)
                over_refunded_count += 1
            else:
                b_net = b_captured - b_refunded
                b_obj = db.query(Booking).filter(Booking.id == bid).first()
                if b_obj and b_obj.status == "CONFIRMED" and b_net > Decimal("0.00"):
                    # Check items for partner rates
                    items = db.query(BookingItem).filter(BookingItem.booking_id == bid).all()
                    if items:
                        items_total = sum((quantize_currency(it.subtotal) for it in items), Decimal("0.00"))
                        for it in items:
                            rate = default_comm_rate
                            partner_id = None
                            if it.item_type == "TICKET":
                                ett = db.query(EventTicketType).filter(EventTicketType.id == it.item_id).first()
                                if ett and ett.event:
                                    partner_id = ett.event.partner_id
                            elif it.item_type == "SLOT":
                                acs = db.query(ActivitySlot).filter(ActivitySlot.id == it.item_id).first()
                                if acs and acs.activity:
                                    partner_id = acs.activity.partner_id or (acs.activity.venue.partner_id if acs.activity.venue else None)
                            elif it.item_type == "TABLE":
                                dt = db.query(DiningTable).filter(DiningTable.id == it.item_id).first()
                                if dt and dt.restaurant:
                                    partner_id = dt.restaurant.partner_id
                            elif it.item_type == "SEAT":
                                st = db.query(Seat).filter(Seat.id == it.item_id).first()
                                if st and st.screen and st.screen.cinema:
                                    partner_id = st.screen.cinema.partner_id

                            if partner_id:
                                p_rec = db.query(Partner).filter(Partner.id == partner_id).first()
                                if p_rec and p_rec.commission_rate is not None:
                                    rate = Decimal(str(p_rec.commission_rate)).quantize(FOURPLACES)

                            it_sub = quantize_currency(it.subtotal)
                            it_share = (it_sub / items_total) if items_total > 0 else Decimal("1.0")
                            it_net = b_net * it_share
                            platform_revenue += quantize_currency(it_net * rate)
                            partner_settlements += quantize_currency(it_net * (Decimal("1.0000") - rate))
                    else:
                        rate = default_comm_rate
                        platform_revenue += quantize_currency(b_net * rate)
                        partner_settlements += quantize_currency(b_net * (Decimal("1.0000") - rate))

    requires_recon = over_refunded_count > 0

    return {
        "gross_confirmed_booking_value": float(gross_booking_value),
        "total_captured_payments": float(total_captured),
        "total_refunded_amount": float(total_refunded),
        "net_collected_amount": float(net_collected),
        "partner_settlements_payable": float(partner_settlements),
        "actual_platform_revenue": float(platform_revenue),
        "total_revenue": float(platform_revenue),
        "total_over_refunded_amount": float(total_over_refunded),
        "over_refunded_bookings_count": over_refunded_count,
        "requires_financial_reconciliation": requires_recon,
    }
