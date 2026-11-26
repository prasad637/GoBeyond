import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.redis import get_redis
from app.models.audit import Notification, AuditLog
from app.models.notification import NotificationPreference, NotificationOutbox
from app.models.user import User
from app.api.deps import get_current_user, require_roles
from app.services.notifications.service import NotificationService
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationOutboxResponse,
    NotificationOutboxListResponse,
    WorkerStatusResponse
)

router = APIRouter()


# ==============================================================================
# 1. IN-APP NOTIFICATION INBOX (CUSTOMER & PARTNER)
# ==============================================================================

@router.get("/", response_model=NotificationListResponse)
def get_user_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_read: Optional[bool] = Query(None, description="Filter by read/unread status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns paginated notifications for the authenticated user (Customer, Partner, or Admin).
    Enforces strict tenant isolation — users can only view their own notifications.
    """
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()

    offset = (page - 1) * page_size
    notifs = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size).all()

    items = [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            created_at=n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
            data=n.data or {}
        )
        for n in notifs
    ]

    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the unread notifications count for the active user badge."""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read")
@router.put("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks a specific notification as read.
    Enforces strict ownership check — returns 404/403 if not owned by the caller.
    """
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification record not found."
        )

    # Ownership check
    if notif.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You cannot access or modify another user's notification."
        )

    notif.is_read = True
    db.commit()
    return {"success": True, "notification_id": notification_id, "is_read": True}


@router.post("/mark-all-read")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks all unread notifications as read for the authenticated user."""
    updated_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({Notification.is_read: True}, synchronize_session=False)

    db.commit()
    return {"success": True, "marked_count": updated_count}


# ==============================================================================
# 2. CUSTOMER NOTIFICATION PREFERENCES
# ==============================================================================

@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves current notification preferences for the authenticated customer."""
    pref = NotificationService.get_or_create_preferences(db, current_user.id)
    return NotificationPreferenceResponse(
        email_enabled=pref.email_enabled,
        sms_enabled=pref.sms_enabled,
        push_enabled=pref.push_enabled,
        in_app_enabled=pref.in_app_enabled,
        booking_alerts=pref.booking_alerts,
        payment_alerts=pref.payment_alerts,
        marketing_enabled=pref.marketing_enabled
    )


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    req: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates customer notification preferences with opt-in/opt-out control."""
    pref = NotificationService.get_or_create_preferences(db, current_user.id)

    if req.email_enabled is not None:
        pref.email_enabled = req.email_enabled
    if req.sms_enabled is not None:
        pref.sms_enabled = req.sms_enabled
    if req.push_enabled is not None:
        pref.push_enabled = req.push_enabled
    if req.in_app_enabled is not None:
        pref.in_app_enabled = req.in_app_enabled
    if req.booking_alerts is not None:
        pref.booking_alerts = req.booking_alerts
    if req.payment_alerts is not None:
        pref.payment_alerts = req.payment_alerts
    if req.marketing_enabled is not None:
        pref.marketing_enabled = req.marketing_enabled

    db.commit()
    db.refresh(pref)

    db.add(AuditLog(
        user_id=current_user.id,
        action="NOTIFICATION_PREFERENCES_UPDATED",
        resource_type="NOTIFICATION_PREFERENCE",
        resource_id=str(pref.id),
        details={"marketing_enabled": pref.marketing_enabled, "email_enabled": pref.email_enabled}
    ))
    db.commit()

    return NotificationPreferenceResponse(
        email_enabled=pref.email_enabled,
        sms_enabled=pref.sms_enabled,
        push_enabled=pref.push_enabled,
        in_app_enabled=pref.in_app_enabled,
        booking_alerts=pref.booking_alerts,
        payment_alerts=pref.payment_alerts,
        marketing_enabled=pref.marketing_enabled
    )


# ==============================================================================
# 3. SUPER ADMIN — OUTBOX INSPECTION, WORKER MONITORING & CONTROLLED RETRY
# ==============================================================================

@router.get("/outbox", response_model=NotificationOutboxListResponse)
def list_outbox_notifications(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (PENDING, PROCESSING, DELIVERED, FAILED, DEAD_LETTER, SKIPPED)"),
    channel_filter: Optional[str] = Query(None, alias="channel", description="Filter by channel (EMAIL, SMS, PUSH, IN_APP)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["super_admin"])),
    db: Session = Depends(get_db)
):
    """
    Super Admin operational audit: Lists all durable outbox notification records
    with full delivery attempt timestamps, provider names, and error traces.
    """
    query = db.query(NotificationOutbox)
    if status_filter:
        query = query.filter(NotificationOutbox.status == status_filter.upper())
    if channel_filter:
        query = query.filter(NotificationOutbox.channel == channel_filter.upper())
    if event_type:
        query = query.filter(NotificationOutbox.event_type == event_type.upper())

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(NotificationOutbox.id.desc()).offset(offset).limit(page_size).all()

    items = [
        NotificationOutboxResponse(
            id=r.id,
            event_type=r.event_type,
            user_id=r.user_id,
            channel=r.channel,
            recipient=r.recipient,
            title=r.title,
            content=r.content,
            status=r.status,
            retry_count=r.retry_count,
            max_retries=r.max_retries,
            last_attempt_at=r.last_attempt_at.isoformat() if r.last_attempt_at else None,
            next_retry_at=r.next_retry_at.isoformat() if r.next_retry_at else None,
            error_message=r.error_message,
            provider_name=r.provider_name,
            provider_metadata=r.provider_metadata or {},
            idempotency_key=r.idempotency_key,
            is_marketing=r.is_marketing,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        )
        for r in records
    ]

    return NotificationOutboxListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/outbox/{outbox_id}/retry")
def retry_outbox_notification(
    outbox_id: int,
    current_user: User = Depends(require_roles(["super_admin"])),
    db: Session = Depends(get_db)
):
    """
    Super Admin manual intervention: Re-triggers dispatch for a FAILED or DEAD_LETTER outbox entry.
    """
    outbox = db.query(NotificationOutbox).filter(NotificationOutbox.id == outbox_id).first()
    if not outbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbox record #{outbox_id} not found."
        )

    # Reset retry counters and status
    outbox.status = "PENDING"
    outbox.retry_count = 0
    outbox.error_message = None
    outbox.next_retry_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    # Immediate dispatch attempt
    success = NotificationService.dispatch_outbox_entry(db, outbox.id)

    db.add(AuditLog(
        user_id=current_user.id,
        action="NOTIFICATION_MANUAL_RETRY",
        resource_type="NOTIFICATION_OUTBOX",
        resource_id=str(outbox.id),
        details={"success": success, "event_type": outbox.event_type}
    ))
    db.commit()

    return {
        "success": True,
        "outbox_id": outbox.id,
        "dispatched": success,
        "new_status": outbox.status,
        "message": f"Outbox notification #{outbox.id} retry completed with status: {outbox.status}"
    }


@router.get("/worker/status", response_model=WorkerStatusResponse)
def get_worker_status(
    current_user: User = Depends(require_roles(["super_admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns background worker health, Redis queue metrics, and outbox lifecycle counts.
    """
    redis_connected = False
    worker_alive = False
    try:
        r = get_redis()
        if r:
            redis_connected = bool(r.ping())
            if redis_connected:
                worker_alive = bool(r.get("gobeyond:worker:heartbeat"))
    except Exception:
        redis_connected = False
        worker_alive = False

    # Outbox lifecycle aggregations
    status_counts = dict(
        db.query(NotificationOutbox.status, func.count(NotificationOutbox.id))
        .group_by(NotificationOutbox.status)
        .all()
    )

    pending_count = status_counts.get("PENDING", 0)
    processing_count = status_counts.get("PROCESSING", 0)
    delivered_count = status_counts.get("DELIVERED", 0)
    failed_count = status_counts.get("FAILED", 0)
    dead_letter_count = status_counts.get("DEAD_LETTER", 0)

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return WorkerStatusResponse(
        is_healthy=bool(redis_connected and worker_alive),
        redis_connected=redis_connected,
        queue_name="gobeyond:notification_queue",
        pending_jobs_count=pending_count,
        processing_jobs_count=processing_count,
        delivered_jobs_count=delivered_count,
        failed_jobs_count=failed_count,
        dead_letter_jobs_count=dead_letter_count,
        active_workers_count=1 if (redis_connected and worker_alive) else 0,
        checked_at=now_str
    )
