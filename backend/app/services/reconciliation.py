"""GO BEYOND — Financial & Payment Reconciliation Engine

Integrity & Audit Specification:
- Compares local payment records with gateway records, booking contracts, and refund histories.
- Detects amount mismatches, duplicate transactions, over-refunds, missing payments, and settlement drift.
- Never silently modifies records to mask discrepancies; generates structured, actionable audit reports.
- Enforces Decimal ROUND_HALF_UP precision across all metric aggregations.
"""
from typing import Dict, Any, List, Optional
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.partner import Partner
from app.models.audit import AuditLog
from app.services.revenue import calculate_revenue_metrics, quantize_currency
from app.schemas.payment import ReconciliationReportResponse, ReconciliationDiscrepancyItem


class ReconciliationEngine:
    @staticmethod
    def run_reconciliation_audit(db: Session, actor_id: Optional[int] = None) -> ReconciliationReportResponse:
        """
        Executes an exhaustive financial audit across all platform payments, refunds,
        booking contracts, and multi-partner commission settlements.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        discrepancies: List[ReconciliationDiscrepancyItem] = []

        all_bookings = db.query(Booking).all()
        all_payments = db.query(Payment).all()
        all_refunds = db.query(Refund).all()

        total_bookings_count = len(all_bookings)
        total_payments_count = len(all_payments)
        total_refunds_count = len(all_refunds)

        # 1. AMOUNT MISMATCH AUDIT:
        # Check whether captured payment amount matches the booking's final_payable
        for p in all_payments:
            if p.status in ["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED", "REFUNDED"] and p.booking:
                expected_amount = quantize_currency(p.booking.final_payable)
                actual_amount = quantize_currency(p.amount)
                if expected_amount != actual_amount:
                    discrepancies.append(ReconciliationDiscrepancyItem(
                        code="AMOUNT_MISMATCH",
                        severity="HIGH",
                        booking_reference=p.booking.booking_reference,
                        payment_id=p.id,
                        gateway_id=p.gateway_payment_id,
                        description=f"Captured amount ₹{actual_amount} differs from booking contract payable ₹{expected_amount}.",
                        suggested_action="Review gateway transaction details and verify order pricing integrity.",
                        details={
                            "captured_amount": float(actual_amount),
                            "expected_payable": float(expected_amount),
                            "difference": float(actual_amount - expected_amount)
                        }
                    ))

        # 2. DUPLICATE GATEWAY TRANSACTION AUDIT:
        # Check if the same gateway_payment_id was recorded multiple times
        gateway_seen: Dict[str, List[int]] = {}
        for p in all_payments:
            if p.gateway_payment_id:
                gateway_seen.setdefault(p.gateway_payment_id, []).append(p.id)

        for gw_id, payment_ids in gateway_seen.items():
            if len(payment_ids) > 1:
                discrepancies.append(ReconciliationDiscrepancyItem(
                    code="DUPLICATE_GATEWAY_TXN",
                    severity="HIGH",
                    gateway_id=gw_id,
                    description=f"Gateway payment ID '{gw_id}' is linked to multiple local payment records ({payment_ids}).",
                    suggested_action="Investigate gateway callback logs for duplicate transaction deduplication failure.",
                    details={"payment_ids": payment_ids}
                ))

        # 3. OVER-REFUND DETECTION:
        # Check for every booking whether total refunds exceed total captured payments
        payments_by_booking: Dict[int, Decimal] = {}
        for p in all_payments:
            if p.status in ["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED", "REFUNDED"]:
                payments_by_booking[p.booking_id] = payments_by_booking.get(p.booking_id, Decimal("0.00")) + quantize_currency(p.amount)

        refunds_by_booking: Dict[int, Decimal] = {}
        for r in all_refunds:
            if r.status in ["PROCESSED", "SUCCESS"]:
                refunds_by_booking[r.booking_id] = refunds_by_booking.get(r.booking_id, Decimal("0.00")) + quantize_currency(r.amount)

        for b_id, total_ref in refunds_by_booking.items():
            total_cap = payments_by_booking.get(b_id, Decimal("0.00"))
            if total_ref > total_cap:
                booking = db.query(Booking).filter(Booking.id == b_id).first()
                b_ref = booking.booking_reference if booking else f"BID-{b_id}"
                discrepancies.append(ReconciliationDiscrepancyItem(
                    code="OVER_REFUND_DETECTED",
                    severity="HIGH",
                    booking_reference=b_ref,
                    description=f"Total refunded amount ₹{total_ref} exceeds captured amount ₹{total_cap} for booking {b_ref}.",
                    suggested_action="Immediate accounting dispute review required. Freeze partner payout for this booking.",
                    details={
                        "captured_amount": float(total_cap),
                        "refunded_amount": float(total_ref),
                        "excess_refund": float(total_ref - total_cap)
                    }
                ))

        # 4. FAILED REFUNDS ALERT:
        for r in all_refunds:
            if r.status == "FAILED":
                booking = db.query(Booking).filter(Booking.id == r.booking_id).first()
                discrepancies.append(ReconciliationDiscrepancyItem(
                    code="FAILED_REFUND_ALERT",
                    severity="MEDIUM",
                    booking_reference=booking.booking_reference if booking else None,
                    gateway_id=r.gateway_refund_id,
                    description=f"Refund record #{r.id} for ₹{quantize_currency(r.amount)} is in FAILED state.",
                    suggested_action="Check gateway bank rails and retry refund dispatch.",
                    details={"refund_id": r.id, "reason": r.reason}
                ))

        # 5. PENDING LATE PAYMENT REFUNDS:
        # Detect payments marked REFUND_PENDING without a processed refund
        for p in all_payments:
            if p.status == "REFUND_PENDING":
                rfn = db.query(Refund).filter(Refund.payment_id == p.id, Refund.status.in_(["PROCESSED", "SUCCESS"])).first()
                if not rfn:
                    booking = p.booking
                    discrepancies.append(ReconciliationDiscrepancyItem(
                        code="UNRESOLVED_LATE_PAYMENT",
                        severity="MEDIUM",
                        booking_reference=booking.booking_reference if booking else None,
                        payment_id=p.id,
                        gateway_id=p.gateway_payment_id,
                        description=f"Payment #{p.id} is marked REFUND_PENDING but automated refund has not settled.",
                        suggested_action="Execute automated refund settlement for late payment callback.",
                        details={"amount": float(p.amount)}
                    ))

        # 6. EXPIRED UNPAID HOLDS:
        # Detect bookings stuck in PAYMENT_PENDING older than 30 minutes
        cutoff = now_utc - datetime.timedelta(minutes=30)
        stale_pending = db.query(Booking).filter(
            Booking.status == "PAYMENT_PENDING",
            Booking.created_at < cutoff
        ).all()
        for b in stale_pending:
            discrepancies.append(ReconciliationDiscrepancyItem(
                code="STALE_UNPAID_HOLD",
                severity="LOW",
                booking_reference=b.booking_reference,
                description=f"Booking {b.booking_reference} has remained in PAYMENT_PENDING for >30 minutes without captured payment.",
                suggested_action="Trigger background hold expiration to restore locked inventory capacity.",
                details={"created_at": b.created_at.isoformat() if b.created_at else None}
            ))

        # 7. SYSTEM REVENUE METRICS CALCULATION:
        rev_metrics = calculate_revenue_metrics(db)

        # 8. FINANCIAL CONSERVATION VERIFICATION:
        # In regular non-over-refunded state:
        # Net Collected = Total Captured - Total Refunded
        # Net Collected = Platform Revenue + Partner Settlements
        net_collected = Decimal(str(rev_metrics["net_collected_amount"]))
        captured = Decimal(str(rev_metrics["total_captured_payments"]))
        refunded = Decimal(str(rev_metrics["total_refunded_amount"]))
        platform_rev = Decimal(str(rev_metrics["actual_platform_revenue"]))
        partner_pay = Decimal(str(rev_metrics["partner_settlements_payable"]))

        calculated_net = captured - refunded
        if abs(calculated_net - net_collected) > Decimal("0.05"):
            discrepancies.append(ReconciliationDiscrepancyItem(
                code="LEDGER_ARITHMETIC_MISMATCH",
                severity="HIGH",
                description=f"Net collected ₹{net_collected} does not match (Captured ₹{captured} - Refunded ₹{refunded}).",
                suggested_action="Review revenue service calculation pipeline.",
                details={"calculated_net": float(calculated_net), "reported_net": float(net_collected)}
            ))

        if not rev_metrics["requires_financial_reconciliation"] and net_collected > 0:
            sum_components = platform_rev + partner_pay
            if abs(sum_components - net_collected) > Decimal("0.05"):
                discrepancies.append(ReconciliationDiscrepancyItem(
                    code="FINANCIAL_CONSERVATION_DRIFT",
                    severity="HIGH",
                    description=f"Sum of (Platform Fee ₹{platform_rev} + Partner Payout ₹{partner_pay}) differs from Net Collected ₹{net_collected}.",
                    suggested_action="Verify multi-partner line-item commission attribution weights.",
                    details={"sum_components": float(sum_components), "net_collected": float(net_collected)}
                ))

        high_or_medium_count = len([d for d in discrepancies if d.severity in ["HIGH", "MEDIUM"]])
        is_healthy = high_or_medium_count == 0

        # Record Audit Log for the reconciliation run
        db.add(AuditLog(
            user_id=actor_id,
            action="RECONCILIATION_AUDIT_EXECUTED",
            resource_type="FINANCIAL_RECONCILIATION",
            resource_id=now_utc.strftime("%Y%m%d%H%M%S"),
            details={
                "audited_at": now_utc.isoformat(),
                "total_bookings_audited": total_bookings_count,
                "discrepancies_count": len(discrepancies),
                "high_or_medium_discrepancies": high_or_medium_count,
                "is_healthy": is_healthy,
            }
        ))

        # Alert admin if high/medium discrepancies detected
        if not is_healthy:
            try:
                from app.services.notifications.service import NotificationService
                NotificationService.notify_admin_alert(
                    db=db,
                    alert_type="ADMIN_RECONCILIATION_ALERT",
                    title="Financial Reconciliation Alert: Discrepancies Detected",
                    description=f"Reconciliation audit identified {high_or_medium_count} actionable financial discrepancies.",
                    details={"discrepancies_count": len(discrepancies), "high_or_medium": high_or_medium_count}
                )
            except Exception:
                pass

        db.commit()

        return ReconciliationReportResponse(
            is_healthy=is_healthy,
            total_bookings_audited=total_bookings_count,
            total_payments_audited=total_payments_count,
            total_refunds_audited=total_refunds_count,
            total_captured_amount=float(captured),
            total_refunded_amount=float(refunded),
            net_collected_amount=float(net_collected),
            platform_revenue=float(platform_rev),
            partner_settlements=float(partner_pay),
            discrepancies_count=len(discrepancies),
            discrepancies=discrepancies,
            audited_at=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        )

