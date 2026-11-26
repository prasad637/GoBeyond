import asyncio
import datetime
import json
import logging
import os
from typing import Any, Dict, Optional
from decimal import Decimal
from urllib.parse import urlparse
from sqlalchemy import update
from sqlalchemy.orm import Session
from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.locks import lock_service
from app.core.redis import get_redis
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.event import Event, EventTicketType
from app.models.sports import ActivitySlot
from app.models.movie import MovieShow
from app.models.dining import DiningReservation
from app.models.payment import Payment, Refund
from app.models.audit import Notification, AuditLog
from app.models.notification import NotificationOutbox
from app.services.reconciliation import ReconciliationEngine
from app.services.revenue import quantize_currency
from app.services.notifications.service import NotificationService

logger = logging.getLogger("gobeyond.worker")

WORKER_HEARTBEAT_KEY = "gobeyond:worker:heartbeat"
WORKER_HEARTBEAT_TTL_SECONDS = 90


def _record_worker_heartbeat() -> None:
    """Writes a liveness heartbeat into Redis so /worker/status reflects live worker health."""
    try:
        r = get_redis()
        if r:
            payload = json.dumps({
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "pid": os.getpid(),
            })
            r.set(WORKER_HEARTBEAT_KEY, payload, ex=WORKER_HEARTBEAT_TTL_SECONDS)
    except Exception:
        pass


async def worker_heartbeat(ctx: Dict[str, Any]) -> bool:
    """Periodic liveness ping stored in Redis."""
    _record_worker_heartbeat()
    return True


async def expire_stale_bookings(ctx: Dict[str, Any]) -> int:
    """
    Idempotent background job to expire bookings whose payment hold window has elapsed.
    Releases temporary seat locks strictly verified by ownership lock_token (via atomic Lua),
    cancels transient dining holds, and restores available capacity for events and activities.
    """
    _record_worker_heartbeat()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    db: Session = SessionLocal()
    expired_count = 0

    try:
        # Find all unpaid/held bookings where expiration window has passed
        stale_bookings = db.query(Booking).filter(
            Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING"]),
            Booking.expires_at != None,
            Booking.expires_at < now_utc
        ).all()

        for b in stale_bookings:
            b.status = "EXPIRED"
            expired_count += 1

            # Restore inventory for items under this booking
            for item in b.items:
                if b.booking_type == "EVENT" and item.item_type == "TICKET":
                    db.execute(
                        update(EventTicketType)
                        .where(EventTicketType.id == item.item_id)
                        .values(available_quantity=EventTicketType.available_quantity + item.quantity)
                    )
                elif b.booking_type in ["SPORTS", "ACTIVITY"] and item.item_type == "SLOT":
                    db.execute(
                        update(ActivitySlot)
                        .where(ActivitySlot.id == item.item_id)
                        .values(booked_count=ActivitySlot.booked_count - item.quantity)
                    )
                elif b.booking_type == "DINING" and item.item_type == "TABLE":
                    db.query(DiningReservation).filter(
                        DiningReservation.booking_id == b.id
                    ).update({"status": "CANCELLED"}, synchronize_session=False)
                elif b.booking_type == "MOVIE" and item.item_type == "SEAT":
                    # Locate and release seat lock using owner's lock_token
                    show_id = (item.details or {}).get("show_id")
                    lock_query = db.query(SeatLock).filter(
                        SeatLock.resource_type == "MOVIE_SHOW",
                        SeatLock.identifier == f"seat_{item.item_id}",
                        SeatLock.user_id == b.user_id,
                        SeatLock.is_released == False
                    )
                    if show_id:
                        lock_query = lock_query.filter(SeatLock.resource_id == int(show_id))
                    for sl in lock_query.all():
                        redis_key = f"show_{sl.resource_id}:{sl.identifier}"
                        lock_service.release_lock(redis_key, sl.lock_token)
                        sl.is_released = True

            # Release any other lingering locks belonging to this user
            user_locks = db.query(SeatLock).filter(
                SeatLock.user_id == b.user_id,
                SeatLock.expires_at <= now_utc,
                SeatLock.is_released == False
            ).all()
            for ul in user_locks:
                if ul.resource_type == "MOVIE_SHOW":
                    redis_key = f"show_{ul.resource_id}:{ul.identifier}"
                elif ul.resource_type == "DINING_TABLE":
                    redis_key = f"dining_table_{ul.resource_id}:{ul.identifier}"
                else:
                    redis_key = f"{ul.resource_type.lower()}_{ul.resource_id}:{ul.identifier}"
                lock_service.release_lock(redis_key, ul.lock_token)
                ul.is_released = True

            db.add(AuditLog(
                user_id=b.user_id,
                action="BOOKING_EXPIRED_BY_WORKER",
                resource_type="BOOKING",
                resource_id=b.booking_reference,
                details={"expired_at": now_utc.isoformat()}
            ))

        db.commit()
        if expired_count > 0:
            logger.info(f"Worker expired {expired_count} stale bookings.")
        return expired_count

    except Exception as exc:
        db.rollback()
        logger.error(f"Error in expire_stale_bookings: {exc}")
        raise
    finally:
        db.close()


async def reconcile_unconfirmed_payments(ctx: Dict[str, Any]) -> int:
    """
    Idempotent task to reconcile pending payments older than 30 minutes.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)
    db: Session = SessionLocal()
    reconciled_count = 0

    try:
        orphaned_payments = db.query(Payment).filter(
            Payment.status == "INITIATED",
            Payment.created_at < cutoff
        ).all()

        for p in orphaned_payments:
            p.status = "EXPIRED"
            reconciled_count += 1

        db.commit()
        return reconciled_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error in reconcile_unconfirmed_payments: {exc}")
        raise
    finally:
        db.close()


async def sync_refund_statuses(ctx: Dict[str, Any]) -> int:
    """
    Idempotent background job to synchronize pending refunds.
    Ensures that refunds initiated on the gateway transition to PROCESSED
    once confirmed, and atomically synchronizes parent Payment and Booking
    statuses so financial ledgers remain strictly balanced.
    """
    db: Session = SessionLocal()
    synced_count = 0
    try:
        pending_refunds = db.query(Refund).filter(Refund.status == "INITIATED").all()
        affected_booking_ids = set()
        affected_payment_ids = set()

        for r in pending_refunds:
            # In sandbox / test environment, initiated refunds settle to PROCESSED
            if settings.RAZORPAY_SANDBOX_MODE or (r.gateway_refund_id or "").startswith("rfn_"):
                r.status = "PROCESSED"
                synced_count += 1
                if r.payment_id:
                    affected_payment_ids.add(r.payment_id)
                if r.booking_id:
                    affected_booking_ids.add(r.booking_id)
                db.add(AuditLog(
                    action="REFUND_STATUS_SYNCED",
                    resource_type="REFUND",
                    resource_id=r.gateway_refund_id,
                    details={"status": "PROCESSED", "refund_id": r.id}
                ))

        # Also heal any previously settled refunds whose parent Payment/Booking is still REFUND_PENDING
        unsynced_processed = (
            db.query(Refund)
            .join(Payment, Payment.id == Refund.payment_id)
            .filter(
                Refund.status.in_(["PROCESSED", "SUCCESS"]),
                Payment.status == "REFUND_PENDING"
            )
            .all()
        )
        for r in unsynced_processed:
            if r.payment_id:
                affected_payment_ids.add(r.payment_id)
            if r.booking_id:
                affected_booking_ids.add(r.booking_id)

        db.flush()

        for pid in affected_payment_ids:
            payment = db.query(Payment).filter(Payment.id == pid).first()
            if not payment:
                continue
            settled_for_payment = sum(
                (
                    quantize_currency(ref.amount)
                    for ref in db.query(Refund).filter(
                        Refund.payment_id == payment.id,
                        Refund.status.in_(["PROCESSED", "SUCCESS"])
                    ).all()
                ),
                Decimal("0.00")
            )
            payment_amt = quantize_currency(payment.amount)
            if payment_amt > Decimal("0.00") and settled_for_payment >= payment_amt:
                payment.status = "REFUNDED"
            elif settled_for_payment > Decimal("0.00") and payment.status != "REFUNDED":
                payment.status = "PARTIALLY_REFUNDED"

        for bid in affected_booking_ids:
            booking = db.query(Booking).filter(Booking.id == bid).first()
            if not booking:
                continue
            paid_rows = db.query(Payment).filter(
                Payment.booking_id == booking.id,
                Payment.status.in_(["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED", "REFUNDED", "REFUND_PENDING"])
            ).all()
            total_paid = sum((quantize_currency(p.amount) for p in paid_rows), Decimal("0.00"))
            total_settled_refunds = sum(
                (
                    quantize_currency(ref.amount)
                    for ref in db.query(Refund).filter(
                        Refund.booking_id == booking.id,
                        Refund.status.in_(["PROCESSED", "SUCCESS"])
                    ).all()
                ),
                Decimal("0.00")
            )
            if (
                total_paid > Decimal("0.00")
                and total_settled_refunds >= total_paid
                and booking.status in ("REFUND_PENDING", "CANCELLED", "CONFIRMED")
            ):
                booking.status = "REFUNDED"

        db.commit()
        return synced_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error in sync_refund_statuses: {exc}")
        raise
    finally:
        db.close()


async def periodic_financial_reconciliation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scheduled background task to run the ReconciliationEngine across all
    payments, bookings, refunds, and partner ledger accounts.
    """
    db: Session = SessionLocal()
    try:
        report = ReconciliationEngine.run_reconciliation_audit(db)
        logger.info(f"Periodic reconciliation completed: {report.discrepancies_count} discrepancies found.")
        return {
            "is_healthy": report.is_healthy,
            "discrepancies_count": report.discrepancies_count,
            "audited_at": report.audited_at
        }
    except Exception as exc:
        logger.error(f"Error in periodic_financial_reconciliation: {exc}")
        raise
    finally:
        db.close()


async def send_booking_notification(
    ctx: Dict[str, Any],
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "SYSTEM",
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Asynchronously creates a notification record in the database.
    """
    db: Session = SessionLocal()
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            data=data or {}
        )
        db.add(notif)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.error(f"Error in send_booking_notification: {exc}")
        raise
    finally:
        db.close()


async def dispatch_single_outbox_task(ctx: Dict[str, Any], outbox_id: int) -> bool:
    """Asynchronously dispatches a single notification outbox record."""
    db: Session = SessionLocal()
    try:
        return NotificationService.dispatch_outbox_entry(db, outbox_id)
    except Exception as exc:
        logger.error(f"Error dispatching outbox #{outbox_id}: {exc}")
        raise
    finally:
        db.close()


async def dispatch_pending_outbox_notifications(ctx: Dict[str, Any]) -> int:
    """
    Periodic job: Processes PENDING notification outbox records from PostgreSQL.
    Ensures zero message loss if Redis or worker was temporarily unavailable.
    """
    db: Session = SessionLocal()
    dispatched_count = 0
    try:
        pending_records = db.query(NotificationOutbox).filter(
            NotificationOutbox.status == "PENDING"
        ).order_by(NotificationOutbox.id.asc()).limit(100).all()

        for record in pending_records:
            success = NotificationService.dispatch_outbox_entry(db, record.id)
            if success:
                dispatched_count += 1

        if dispatched_count > 0:
            logger.info(f"Worker dispatched {dispatched_count} pending outbox notifications.")
        return dispatched_count
    except Exception as exc:
        logger.error(f"Error in dispatch_pending_outbox_notifications: {exc}")
        raise
    finally:
        db.close()


async def retry_failed_outbox_notifications(ctx: Dict[str, Any]) -> int:
    """
    Periodic job: Retries FAILED notification outbox records whose next_retry_at has elapsed.
    Uses exponential backoff and moves to DEAD_LETTER after max_retries.
    """
    db: Session = SessionLocal()
    retried_count = 0
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        failed_records = db.query(NotificationOutbox).filter(
            NotificationOutbox.status == "FAILED",
            NotificationOutbox.next_retry_at != None,
            NotificationOutbox.next_retry_at <= now_utc
        ).order_by(NotificationOutbox.id.asc()).limit(50).all()

        for record in failed_records:
            success = NotificationService.dispatch_outbox_entry(db, record.id)
            if success:
                retried_count += 1

        if retried_count > 0:
            logger.info(f"Worker retried {retried_count} failed outbox notifications.")
        return retried_count
    except Exception as exc:
        logger.error(f"Error in retry_failed_outbox_notifications: {exc}")
        raise
    finally:
        db.close()


async def send_upcoming_booking_reminders(ctx: Dict[str, Any]) -> int:
    """
    Periodic job: Scans for CONFIRMED bookings starting in the next 24 hours (24h window)
    and next 2 hours (2h window), and enqueues reminder notifications.
    Uses deterministic idempotency keys to guarantee reminders are sent at most once.
    """
    db: Session = SessionLocal()
    reminders_sent = 0
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # 24-hour reminder window: bookings starting between 22h and 26h from now
    window_24h_start = now_utc + datetime.timedelta(hours=22)
    window_24h_end = now_utc + datetime.timedelta(hours=26)

    # 2-hour reminder window: bookings starting between 1h and 3h from now
    window_2h_start = now_utc + datetime.timedelta(hours=1)
    window_2h_end = now_utc + datetime.timedelta(hours=3)

    try:
        confirmed_bookings = db.query(Booking).filter(Booking.status == "CONFIRMED").all()

        for b in confirmed_bookings:
            booking_start_time: Optional[datetime.datetime] = None

            # Determine start time based on vertical
            if b.booking_type == "MOVIE":
                show_item = next((item for item in b.items if item.item_type == "SEAT"), None)
                if show_item:
                    show_time_str = (show_item.details or {}).get("show_time")
                    if show_time_str:
                        try:
                            parsed = datetime.datetime.fromisoformat(str(show_time_str))
                            if isinstance(parsed, datetime.datetime):
                                booking_start_time = parsed
                        except Exception:
                            pass
                    if not isinstance(booking_start_time, datetime.datetime) and (show_item.details or {}).get("show_id"):
                        show = db.query(MovieShow).filter(MovieShow.id == int(show_item.details["show_id"])).first()
                        if show and show.show_date and show.start_time:
                            booking_start_time = datetime.datetime.combine(show.show_date, show.start_time)
            elif b.booking_type == "DINING":
                res = db.query(DiningReservation).filter(DiningReservation.booking_id == b.id).first()
                if res:
                    if isinstance(getattr(res, "start_datetime", None), datetime.datetime):
                        booking_start_time = res.start_datetime
                    elif res.reservation_date and res.reservation_time:
                        try:
                            res_time = (
                                res.reservation_time
                                if isinstance(res.reservation_time, datetime.time)
                                else datetime.time.fromisoformat(str(res.reservation_time))
                            )
                            booking_start_time = datetime.datetime.combine(res.reservation_date, res_time)
                        except Exception:
                            pass
            elif b.booking_type == "EVENT":
                event_item = next((item for item in b.items if item.item_type == "TICKET"), None)
                if event_item and (event_item.details or {}).get("event_id"):
                    ev = db.query(Event).filter(Event.id == event_item.details["event_id"]).first()
                    dt = getattr(ev, "start_datetime", None) or getattr(ev, "start_date", None)
                    if isinstance(dt, datetime.datetime):
                        booking_start_time = dt
                    elif isinstance(dt, datetime.date):
                        booking_start_time = datetime.datetime.combine(dt, datetime.time.min)
            elif b.booking_type in ["SPORTS", "ACTIVITY"]:
                slot_item = next((item for item in b.items if item.item_type == "SLOT"), None)
                if slot_item:
                    slot = db.query(ActivitySlot).filter(ActivitySlot.id == slot_item.item_id).first()
                    if slot and slot.start_time:
                        if isinstance(slot.start_time, datetime.datetime):
                            booking_start_time = slot.start_time
                        elif isinstance(slot.start_time, datetime.time) and slot.slot_date:
                            booking_start_time = datetime.datetime.combine(slot.slot_date, slot.start_time)

            # Fallback to booking expiration / schedule timestamp if not populated from item tables
            if not isinstance(booking_start_time, datetime.datetime) and b.expires_at:
                booking_start_time = b.expires_at

            if not isinstance(booking_start_time, datetime.datetime):
                continue

            # Ensure UTC comparison
            if booking_start_time.tzinfo is None:
                booking_start_time = booking_start_time.replace(tzinfo=datetime.timezone.utc)

            # 24H Reminder
            if window_24h_start <= booking_start_time <= window_24h_end:
                idemp_24h = f"remind_24h_{b.id}"
                already_queued = db.query(NotificationOutbox).filter(
                    NotificationOutbox.idempotency_key == idemp_24h
                ).first()
                if not already_queued:
                    outbox = NotificationService.create_outbox_notification(
                        db=db,
                        event_type="BOOKING_REMINDER_24H",
                        channel="IN_APP",
                        recipient=str(b.user_id),
                        title=f"Upcoming Booking in 24 Hours: {b.booking_reference} ⏰",
                        content=f"Your {b.booking_type.capitalize()} booking ({b.booking_reference}) is scheduled for tomorrow at {booking_start_time.strftime('%I:%M %p')}.",
                        user_id=b.user_id,
                        payload={"booking_id": b.id, "booking_reference": b.booking_reference},
                        idempotency_key=idemp_24h,
                        commit=False
                    )
                    if outbox and outbox.status != "SKIPPED":
                        reminders_sent += 1

            # 2H Reminder
            elif window_2h_start <= booking_start_time <= window_2h_end:
                idemp_2h = f"remind_2h_{b.id}"
                already_queued = db.query(NotificationOutbox).filter(
                    NotificationOutbox.idempotency_key == idemp_2h
                ).first()
                if not already_queued:
                    outbox = NotificationService.create_outbox_notification(
                        db=db,
                        event_type="BOOKING_REMINDER_2H",
                        channel="IN_APP",
                        recipient=str(b.user_id),
                        title=f"Booking Reminder: Starting in 2 Hours! 🎟️",
                        content=f"Your {b.booking_type.capitalize()} booking ({b.booking_reference}) starts soon! Have your entry pass QR code ready.",
                        user_id=b.user_id,
                        payload={"booking_id": b.id, "booking_reference": b.booking_reference},
                        idempotency_key=idemp_2h,
                        commit=False
                    )
                    if outbox and outbox.status != "SKIPPED":
                        reminders_sent += 1

        db.commit()
        if reminders_sent > 0:
            logger.info(f"Worker generated {reminders_sent} booking reminders.")
        return reminders_sent

    except Exception as exc:
        db.rollback()
        logger.error(f"Error in send_upcoming_booking_reminders: {exc}")
        raise
    finally:
        db.close()


async def cleanup_expired_temporary_records(ctx: Dict[str, Any]) -> int:
    """
    Periodic job: Cleans up released seat locks and delivered outbox notifications older than retention window.
    """
    db: Session = SessionLocal()
    cleaned_count = 0
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    lock_cutoff = now_utc - datetime.timedelta(days=1)
    notif_cutoff = now_utc - datetime.timedelta(days=90)

    try:
        # 1. Clean up released seat locks older than 24 hours
        deleted_locks = db.query(SeatLock).filter(
            SeatLock.is_released == True,
            SeatLock.created_at < lock_cutoff
        ).delete(synchronize_session=False)
        cleaned_count += deleted_locks

        # 2. Clean up delivered outbox entries older than 90 days
        deleted_notifs = db.query(NotificationOutbox).filter(
            NotificationOutbox.status == "DELIVERED",
            NotificationOutbox.created_at < notif_cutoff
        ).delete(synchronize_session=False)
        cleaned_count += deleted_notifs

        db.commit()
        if cleaned_count > 0:
            logger.info(f"Worker cleaned up {cleaned_count} expired records.")
        return cleaned_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error in cleanup_expired_temporary_records: {exc}")
        raise
    finally:
        db.close()


def get_redis_settings() -> RedisSettings:
    """Parses REDIS_URL into ARQ RedisSettings."""
    try:
        parsed = urlparse(settings.REDIS_URL)
        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password,
            database=int(parsed.path.lstrip("/") or 0)
        )
    except Exception:
        return RedisSettings(host="localhost", port=6379)


async def on_worker_startup(ctx: Dict[str, Any]) -> None:
    """Logs worker startup, writes initial heartbeat, and logs pool parameters."""
    _record_worker_heartbeat()
    logger.info(
        f"ARQ Worker started with database pool_size={settings.DB_POOL_SIZE}, "
        f"max_overflow={settings.DB_MAX_OVERFLOW} (Max worker DB connections: "
        f"{settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW})"
    )


class WorkerSettings:
    """ARQ Worker configuration class."""
    on_startup = on_worker_startup
    functions = [
        worker_heartbeat,
        expire_stale_bookings,
        reconcile_unconfirmed_payments,
        sync_refund_statuses,
        periodic_financial_reconciliation,
        send_booking_notification,
        dispatch_single_outbox_task,
        dispatch_pending_outbox_notifications,
        retry_failed_outbox_notifications,
        send_upcoming_booking_reminders,
        cleanup_expired_temporary_records
    ]
    cron_jobs = [
        cron(worker_heartbeat, minute=None, second={0, 30}),  # Heartbeat every 30s (TTL 90s)
        cron(expire_stale_bookings, minute=None, second=0),  # Runs every minute
        cron(dispatch_pending_outbox_notifications, minute=None, second=15),  # Runs every minute at :15
        cron(retry_failed_outbox_notifications, minute=None, second=45),  # Runs every minute at :45
        cron(send_upcoming_booking_reminders, minute={5, 20, 35, 50}),  # Every 15 minutes
        cron(sync_refund_statuses, minute={0, 15, 30, 45}),   # Every 15 minutes
        cron(periodic_financial_reconciliation, hour=2, minute=0),  # Daily at 2 AM
        cron(cleanup_expired_temporary_records, hour=3, minute=0)   # Daily at 3 AM
    ]
    redis_settings = get_redis_settings()
    max_retries = 3
    retry_delay = 5
