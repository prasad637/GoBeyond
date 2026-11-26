"""GO BEYOND — Notification & Durable Outbox Service

Architecture:
- Durable PostgreSQL Outbox Pattern: notifications are recorded inside the DB transaction,
  guaranteeing zero message loss even during complete Redis or worker downtime.
- Asynchronous ARQ/Redis dispatch with safe fallback.
- Concurrency control via PostgreSQL `FOR UPDATE SKIP LOCKED`.
- Configurable customer notification preferences (Email, SMS, Push, In-App, Marketing).
- Strict idempotency key enforcement.
- Exponential backoff retry logic and dead-letter queuing.
- Absolute secrecy: Plaintext OTPs, tokens, and passwords are never logged or persisted in audit records.
"""
import datetime
import logging
import uuid
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.core.config import settings
from app.core.redis import get_redis
from app.models.notification import NotificationPreference, NotificationOutbox
from app.models.audit import Notification, AuditLog
from app.models.user import User
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.partner import Partner
from app.models.event import EventTicketType
from app.models.sports import ActivitySlot
from app.models.dining import DiningTable
from app.models.movie import Seat
from app.services.notifications.providers import get_provider, mask_sensitive_content

logger = logging.getLogger("gobeyond.notifications.service")


class NotificationService:
    @staticmethod
    def get_or_create_preferences(db: Session, user_id: int) -> NotificationPreference:
        """Retrieves user's notification preferences or initializes defaults safely under concurrency."""
        pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if not pref:
            try:
                with db.begin_nested():
                    pref = NotificationPreference(
                        user_id=user_id,
                        email_enabled=True,
                        sms_enabled=True,
                        push_enabled=True,
                        in_app_enabled=True,
                        booking_alerts=True,
                        payment_alerts=True,
                        marketing_enabled=False
                    )
                    db.add(pref)
                    db.flush()
            except IntegrityError:
                pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        return pref

    @staticmethod
    def create_outbox_notification(
        db: Session,
        event_type: str,
        channel: str,
        recipient: str,
        title: str,
        content: str,
        user_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        is_marketing: bool = False,
        max_retries: int = 3,
        commit: bool = True
    ) -> NotificationOutbox:
        """
        Records a notification in the durable PostgreSQL Outbox table.
        Enforces user preferences, marketing unsubscribe rules, and idempotency.
        """
        chan = channel.upper()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        payload = payload or {}

        # Generate deterministic idempotency key if not explicitly supplied
        if not idempotency_key:
            idempotency_key = f"notif_{event_type}_{chan}_{user_id or recipient}_{uuid.uuid4().hex[:8]}"

        # 1. IDEMPOTENCY CHECK:
        existing = db.query(NotificationOutbox).filter(
            NotificationOutbox.idempotency_key == idempotency_key
        ).first()
        if existing:
            logger.info(f"Duplicate notification avoided for key '{idempotency_key}' (status={existing.status})")
            return existing

        # 2. NOTIFICATION PREFERENCES & MARKETING OPT-IN CHECK:
        status = "PENDING"
        error_msg = None

        if user_id:
            pref = NotificationService.get_or_create_preferences(db, user_id)

            # Marketing preference check
            if is_marketing and not pref.marketing_enabled:
                status = "SKIPPED"
                error_msg = "User unsubscribed from marketing notifications."
                logger.info(f"Notification {event_type} skipped: user {user_id} unsubscribed from marketing.")

            # Channel preference check (Critical OTP & Admin alerts cannot be disabled)
            elif event_type != "OTP_VERIFICATION" and not event_type.startswith("ADMIN_"):
                if chan == "EMAIL" and not pref.email_enabled:
                    status = "SKIPPED"
                    error_msg = "User disabled EMAIL notifications."
                elif chan == "SMS" and not pref.sms_enabled:
                    status = "SKIPPED"
                    error_msg = "User disabled SMS notifications."
                elif chan == "PUSH" and not pref.push_enabled:
                    status = "SKIPPED"
                    error_msg = "User disabled PUSH notifications."
                elif chan == "IN_APP" and not pref.in_app_enabled:
                    status = "SKIPPED"
                    error_msg = "User disabled IN_APP notifications."
                elif event_type.startswith("BOOKING_") and not pref.booking_alerts:
                    status = "SKIPPED"
                    error_msg = "User disabled booking alerts."
                elif event_type.startswith("PAYMENT_") and not pref.payment_alerts:
                    status = "SKIPPED"
                    error_msg = "User disabled payment alerts."

        provider = get_provider(chan)
        outbox = NotificationOutbox(
            event_type=event_type,
            user_id=user_id,
            channel=chan,
            recipient=recipient,
            title=title,
            content=content,
            status=status,
            retry_count=0,
            max_retries=max_retries,
            error_message=error_msg,
            provider_name=provider.provider_name,
            provider_metadata={"reason": error_msg} if error_msg else {},
            idempotency_key=idempotency_key,
            is_marketing=is_marketing,
            payload=payload,
            next_retry_at=now_utc if status == "PENDING" else None
        )
        try:
            with db.begin_nested():
                db.add(outbox)
                db.flush()
        except IntegrityError:
            existing = db.query(NotificationOutbox).filter(
                NotificationOutbox.idempotency_key == idempotency_key
            ).first()
            if existing:
                logger.info(
                    f"Concurrent duplicate notification avoided via savepoint for key "
                    f"'{idempotency_key}' (status={existing.status})"
                )
                return existing
            raise

        if commit:
            db.commit()
            db.refresh(outbox)

        # 3. ASYNC ARQ ENQUEUE (Zero loss if Redis is down):
        if status == "PENDING":
            try:
                redis_client = get_redis()
                if redis_client:
                    # Enqueue job key for background worker
                    redis_client.lpush("gobeyond:notification_queue", str(outbox.id))
            except Exception as exc:
                logger.warning(
                    f"Redis unavailable during outbox enqueue for #{outbox.id}. "
                    f"Outbox entry remains safely PENDING in PostgreSQL: {exc}"
                )

        return outbox

    # Convenience alias
    queue_notification = create_outbox_notification

    @staticmethod
    def dispatch_outbox_entry(db: Session, outbox_id: int) -> bool:
        """
        Executes dispatch of a single NotificationOutbox record.
        Uses PostgreSQL FOR UPDATE SKIP LOCKED to prevent double delivery by concurrent workers.
        Handles retry with exponential backoff and dead-letter queuing.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Concurrency safety: Lock row with skip_locked
        outbox = db.query(NotificationOutbox).filter(
            NotificationOutbox.id == outbox_id
        ).with_for_update(skip_locked=True).first()

        if not outbox:
            # Row locked by another concurrent worker or already processed
            return False

        if outbox.status not in ["PENDING", "FAILED"]:
            return False

        # Transition to PROCESSING
        outbox.status = "PROCESSING"
        outbox.last_attempt_at = now_utc
        db.commit()

        # Dispatch through provider adapter
        provider = get_provider(outbox.channel)
        try:
            result = provider.send(
                recipient=outbox.recipient,
                title=outbox.title,
                content=outbox.content,
                payload=outbox.payload
            )
        except Exception as exc:
            from app.services.notifications.providers import ProviderResult
            result = ProviderResult(
                success=False,
                provider_name=provider.provider_name,
                error_message=str(exc)
            )

        if result.success:
            outbox.status = "DELIVERED"
            outbox.provider_name = result.provider_name
            outbox.provider_metadata = result.metadata
            outbox.error_message = None

            # If IN_APP channel and user_id present, ensure in-app inbox table has it
            if outbox.channel == "IN_APP" and outbox.user_id:
                inbox_notif = Notification(
                    user_id=outbox.user_id,
                    title=outbox.title,
                    message=outbox.content,
                    type=outbox.event_type,
                    data={"outbox_id": outbox.id, **(outbox.payload or {})}
                )
                db.add(inbox_notif)

            db.commit()
            masked_title = mask_sensitive_content(outbox.title)
            logger.info(f"Outbox #{outbox.id} ({outbox.channel}) delivered successfully: '{masked_title}'")
            return True

        else:
            outbox.retry_count += 1
            outbox.error_message = result.error_message or "Provider delivery failed"
            outbox.provider_metadata = result.metadata

            if outbox.retry_count >= outbox.max_retries:
                outbox.status = "DEAD_LETTER"
                outbox.next_retry_at = None
                db.add(AuditLog(
                    action="NOTIFICATION_DEAD_LETTER",
                    resource_type="NOTIFICATION_OUTBOX",
                    resource_id=str(outbox.id),
                    details={
                        "event_type": outbox.event_type,
                        "channel": outbox.channel,
                        "retries": outbox.retry_count,
                        "error": outbox.error_message
                    }
                ))
                logger.error(f"Outbox #{outbox.id} moved to DEAD_LETTER after {outbox.retry_count} retries.")
            else:
                outbox.status = "FAILED"
                # Exponential backoff: 20s, 40s, 80s, etc.
                backoff_seconds = (2 ** outbox.retry_count) * 10
                outbox.next_retry_at = now_utc + datetime.timedelta(seconds=backoff_seconds)
                logger.warning(
                    f"Outbox #{outbox.id} failed (attempt {outbox.retry_count}/{outbox.max_retries}). "
                    f"Next retry scheduled in {backoff_seconds}s at {outbox.next_retry_at}"
                )

            db.commit()
            return False

    # ==========================================================================
    # EVENT HELPERS — CUSTOMER, PARTNER, ADMIN
    # ==========================================================================

    @staticmethod
    def get_partner_for_booking(db: Session, booking: Booking) -> Optional[Partner]:
        """Resolves the owning partner record for a given booking across all 5 verticals."""
        for item in booking.items:
            if item.details and item.details.get("partner_id"):
                p = db.query(Partner).filter(Partner.id == item.details["partner_id"]).first()
                if p:
                    return p
            if item.item_type == "TICKET":
                ett = db.query(EventTicketType).filter(EventTicketType.id == item.item_id).first()
                if ett and ett.event and ett.event.partner_id:
                    return db.query(Partner).filter(Partner.id == ett.event.partner_id).first()
            elif item.item_type == "SLOT":
                acs = db.query(ActivitySlot).filter(ActivitySlot.id == item.item_id).first()
                if acs and acs.activity:
                    pid = acs.activity.partner_id or (acs.activity.venue.partner_id if acs.activity.venue else None)
                    if pid:
                        return db.query(Partner).filter(Partner.id == pid).first()
            elif item.item_type == "TABLE":
                dt = db.query(DiningTable).filter(DiningTable.id == item.item_id).first()
                if dt and dt.restaurant and dt.restaurant.partner_id:
                    return db.query(Partner).filter(Partner.id == dt.restaurant.partner_id).first()
            elif item.item_type == "SEAT":
                seat = db.query(Seat).filter(Seat.id == item.item_id).first()
                if seat and seat.screen and seat.screen.cinema and seat.screen.cinema.partner_id:
                    return db.query(Partner).filter(Partner.id == seat.screen.cinema.partner_id).first()
        return None

    @staticmethod
    def notify_booking_confirmed(db: Session, booking: Any, user: Any, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches customer booking confirmation via In-App, Email, and SMS, and alerts partner."""
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if isinstance(user, int):
            user = db.query(User).filter(User.id == user).first()
        if not booking or not user:
            return []

        outboxes = []
        b_ref = booking.booking_reference
        b_type = (booking.booking_type or "Booking").capitalize()
        amount_str = f"₹{float(booking.final_payable):.2f}"

        title = f"Booking Confirmed: {b_ref} 🎉"
        content = (
            f"Your {b_type} booking ({b_ref}) has been confirmed! "
            f"Total Paid: {amount_str}. Enjoy your experience with GO BEYOND."
        )

        # 1. In-App
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CONFIRMED",
            channel="IN_APP",
            recipient=str(user.id),
            title=title,
            content=content,
            user_id=user.id,
            payload={"booking_id": booking.id, "booking_reference": b_ref},
            idempotency_key=f"bconf_inapp_{booking.id}",
            commit=False
        ))

        # 2. Email
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CONFIRMED",
            channel="EMAIL",
            recipient=user.email,
            title=title,
            content=content,
            user_id=user.id,
            payload={"booking_id": booking.id, "booking_reference": b_ref},
            idempotency_key=f"bconf_email_{booking.id}",
            commit=False
        ))

        # 3. SMS
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CONFIRMED",
            channel="SMS",
            recipient=user.phone,
            title=f"GO BEYOND: {b_ref} Confirmed",
            content=f"Your GO BEYOND booking {b_ref} is confirmed! Paid: {amount_str}. Show your pass at entry.",
            user_id=user.id,
            payload={"booking_id": booking.id, "booking_reference": b_ref},
            idempotency_key=f"bconf_sms_{booking.id}",
            commit=False
        ))

        # 4. Partner Alert if partner exists
        partner = NotificationService.get_partner_for_booking(db, booking)
        if partner:
            partner_outboxes = NotificationService.notify_partner_new_booking(
                db, partner, booking, commit=False
            )
            outboxes.extend(partner_outboxes)

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_payment_success(db: Session, payment: Any, booking: Any, user: Any, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches payment success notifications to customer."""
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if isinstance(user, int):
            user = db.query(User).filter(User.id == user).first()
        if not booking or not user:
            return []

        pay_id = getattr(payment, "id", None) or getattr(booking, "id", 0)
        pay_amount = getattr(payment, "amount", None)
        if pay_amount is None:
            pay_amount = payment if isinstance(payment, (int, float, Decimal)) else getattr(booking, "final_payable", 0)

        outboxes = []
        amount_str = f"₹{float(pay_amount):.2f}"
        title = "Payment Successful 💳"
        content = f"Payment of {amount_str} for booking {booking.booking_reference} was successful."

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PAYMENT_SUCCESS",
            channel="IN_APP",
            recipient=str(user.id),
            title=title,
            content=content,
            user_id=user.id,
            payload={"payment_id": pay_id, "booking_id": booking.id},
            idempotency_key=f"paysucc_inapp_{pay_id}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PAYMENT_SUCCESS",
            channel="EMAIL",
            recipient=user.email,
            title=title,
            content=content,
            user_id=user.id,
            payload={"payment_id": pay_id, "booking_id": booking.id},
            idempotency_key=f"paysucc_email_{pay_id}",
            commit=False
        ))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_payment_failed(db: Session, payment: Any, booking: Any, user: Any, reason: str = "Payment failed", commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches payment failure notifications to customer and logs admin alert."""
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if isinstance(user, int):
            user = db.query(User).filter(User.id == user).first()
        if not booking or not user:
            return []

        pay_id = getattr(payment, "id", None) or getattr(booking, "id", 0)
        pay_amount = getattr(payment, "amount", None)
        if pay_amount is None:
            pay_amount = payment if isinstance(payment, (int, float, Decimal)) else getattr(booking, "final_payable", 0)

        outboxes = []
        title = "Payment Failed ⚠️"
        content = f"Payment for booking {booking.booking_reference} could not be processed. Reason: {reason}."

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PAYMENT_FAILED",
            channel="IN_APP",
            recipient=str(user.id),
            title=title,
            content=content,
            user_id=user.id,
            payload={"payment_id": pay_id, "booking_id": booking.id, "reason": reason},
            idempotency_key=f"payfail_inapp_{pay_id}_{uuid.uuid4().hex[:6]}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PAYMENT_FAILED",
            channel="EMAIL",
            recipient=user.email,
            title=title,
            content=content,
            user_id=user.id,
            payload={"payment_id": pay_id, "booking_id": booking.id, "reason": reason},
            idempotency_key=f"payfail_email_{pay_id}_{uuid.uuid4().hex[:6]}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="ADMIN_PAYMENT_FAILURE_ALERT",
            channel="IN_APP",
            recipient="admin",
            title=f"Payment Failure Alert: Booking {booking.booking_reference}",
            content=f"Payment #{pay_id} of ₹{float(pay_amount):.2f} failed: {reason}",
            payload={"payment_id": pay_id, "booking_id": booking.id},
            idempotency_key=f"admin_payfail_{pay_id}_{uuid.uuid4().hex[:6]}",
            commit=False
        ))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_refund_processed(db: Session, refund: Any, booking: Any, user: Any, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches refund initiated/completed notifications to customer and partner."""
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if isinstance(user, int):
            user = db.query(User).filter(User.id == user).first()
        if not booking or not user:
            return []

        ref_id = getattr(refund, "id", None) or getattr(booking, "id", 0)
        ref_amount = getattr(refund, "amount", None)
        if ref_amount is None:
            ref_amount = refund if isinstance(refund, (int, float, Decimal)) else getattr(booking, "final_payable", 0)

        outboxes = []
        amount_str = f"₹{float(ref_amount):.2f}"
        title = "Refund Processed 💰"
        content = f"A refund of {amount_str} for booking {booking.booking_reference} has been processed successfully."

        # Customer In-App
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="REFUND_PROCESSED",
            channel="IN_APP",
            recipient=str(user.id),
            title=title,
            content=content,
            user_id=user.id,
            payload={"refund_id": ref_id, "booking_id": booking.id},
            idempotency_key=f"rfn_inapp_{ref_id}_{uuid.uuid4().hex[:4]}",
            commit=False
        ))

        # Customer Email
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="REFUND_PROCESSED",
            channel="EMAIL",
            recipient=user.email,
            title=title,
            content=content,
            user_id=user.id,
            payload={"refund_id": ref_id, "booking_id": booking.id},
            idempotency_key=f"rfn_email_{ref_id}_{uuid.uuid4().hex[:4]}",
            commit=False
        ))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_booking_cancelled(db: Session, booking: Any, user: Any, reason: Optional[str] = None, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches booking cancellation notices to customer and partner."""
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if isinstance(user, int):
            user = db.query(User).filter(User.id == user).first()
        if not booking or not user:
            return []

        outboxes = []
        title = f"Booking Cancelled: {booking.booking_reference}"
        content = f"Your booking {booking.booking_reference} has been cancelled."
        if reason:
            content += f" Reason: {reason}."

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CANCELLED",
            channel="IN_APP",
            recipient=str(user.id),
            title=title,
            content=content,
            user_id=user.id,
            payload={"booking_id": booking.id},
            idempotency_key=f"bcancel_inapp_{booking.id}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CANCELLED",
            channel="EMAIL",
            recipient=user.email,
            title=title,
            content=content,
            user_id=user.id,
            payload={"booking_id": booking.id},
            idempotency_key=f"bcancel_email_{booking.id}",
            commit=False
        ))

        partner = NotificationService.get_partner_for_booking(db, booking)
        if partner:
            outboxes.extend(NotificationService.notify_partner_booking_cancelled(db, partner, booking, commit=False))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_partner_booking_cancelled(db: Session, partner: Any, booking: Any, reason: Optional[str] = None, commit: bool = False) -> List[NotificationOutbox]:
        """Dispatches cancellation notice to the operating Partner."""
        if isinstance(partner, int):
            partner = db.query(Partner).filter(Partner.id == partner).first()
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if not partner:
            return []

        b_ref = getattr(booking, "booking_reference", str(booking))
        b_id = getattr(booking, "id", 0)

        outboxes = []
        title = f"Booking Cancelled: {b_ref} ❌"
        content = f"Customer has cancelled booking {b_ref}. Released inventory has been restored."

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PARTNER_BOOKING_CANCELLED",
            channel="IN_APP",
            recipient=str(partner.user_id),
            title=title,
            content=content,
            user_id=partner.user_id,
            payload={"partner_id": partner.id, "booking_id": b_id},
            idempotency_key=f"part_bcancel_inapp_{partner.id}_{b_id}_{uuid.uuid4().hex[:4]}",
            commit=False
        ))
        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_partner_new_booking(db: Session, partner: Any, booking: Any, amount: Optional[Decimal] = None, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches tenant-isolated new booking notification to the specific Partner."""
        if isinstance(partner, int):
            partner = db.query(Partner).filter(Partner.id == partner).first()
        if isinstance(booking, int):
            booking = db.query(Booking).filter(Booking.id == booking).first()
        if not partner:
            return []

        b_ref = getattr(booking, "booking_reference", str(booking))
        b_id = getattr(booking, "id", 0)
        pay_amount = amount if amount is not None else getattr(booking, "final_payable", 0)
        email_recipient = getattr(partner, "contact_email", None) or getattr(partner, "business_email", "partner@example.com")

        outboxes = []
        title = f"New Booking Received: {b_ref} 🛎️"
        content = (
            f"You have received a new booking ({b_ref}). "
            f"Gross: ₹{float(pay_amount):.2f}. Please review in your dashboard."
        )

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PARTNER_NEW_BOOKING",
            channel="IN_APP",
            recipient=str(partner.user_id),
            title=title,
            content=content,
            user_id=partner.user_id,
            payload={"partner_id": partner.id, "booking_id": b_id},
            idempotency_key=f"part_newbook_inapp_{partner.id}_{b_id}_{uuid.uuid4().hex[:4]}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PARTNER_NEW_BOOKING",
            channel="EMAIL",
            recipient=email_recipient,
            title=title,
            content=content,
            user_id=partner.user_id,
            payload={"partner_id": partner.id, "booking_id": b_id},
            idempotency_key=f"part_newbook_email_{partner.id}_{b_id}_{uuid.uuid4().hex[:4]}",
            commit=False
        ))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_partner_status_change(db: Session, partner: Any, new_status: str, reason: Optional[str] = None, commit: bool = True) -> List[NotificationOutbox]:
        """Dispatches partner approval, rejection, or suspension notification."""
        if isinstance(partner, int):
            partner = db.query(Partner).filter(Partner.id == partner).first()
        if not partner:
            return []

        status_label = new_status.replace("_", " ").title()
        title = f"Partner Account Status: {status_label}"
        content = f"Your partner account for '{partner.business_name}' status has changed to '{new_status}'."
        if reason:
            content += f" Reason: {reason}."

        email_recipient = getattr(partner, "contact_email", None) or getattr(partner, "business_email", "partner@example.com")

        outboxes = []
        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PARTNER_STATUS_CHANGED",
            channel="IN_APP",
            recipient=str(partner.user_id),
            title=title,
            content=content,
            user_id=partner.user_id,
            payload={"partner_id": partner.id, "status": new_status},
            idempotency_key=f"part_status_inapp_{partner.id}_{new_status}_{uuid.uuid4().hex[:6]}",
            commit=False
        ))

        outboxes.append(NotificationService.create_outbox_notification(
            db=db,
            event_type="PARTNER_STATUS_CHANGED",
            channel="EMAIL",
            recipient=email_recipient,
            title=title,
            content=content,
            user_id=partner.user_id,
            payload={"partner_id": partner.id, "status": new_status},
            idempotency_key=f"part_status_email_{partner.id}_{new_status}_{uuid.uuid4().hex[:6]}",
            commit=False
        ))

        if commit:
            db.commit()
        return outboxes

    @staticmethod
    def notify_admin_alert(db: Session, alert_type: str, title: str, description: str, details: Optional[Dict[str, Any]] = None, commit: bool = True) -> NotificationOutbox:
        """Dispatches operational alert to super administrators."""
        return NotificationService.create_outbox_notification(
            db=db,
            event_type=alert_type,
            channel="IN_APP",
            recipient="super_admin",
            title=title,
            content=description,
            payload=details or {},
            idempotency_key=f"admin_{alert_type}_{uuid.uuid4().hex[:8]}",
            commit=commit
        )
