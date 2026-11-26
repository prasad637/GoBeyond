from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: str
    data: Optional[Dict[str, Any]] = None


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPreferenceResponse(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    booking_alerts: bool
    payment_alerts: bool
    marketing_enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    booking_alerts: Optional[bool] = None
    payment_alerts: Optional[bool] = None
    marketing_enabled: Optional[bool] = None


class NotificationOutboxResponse(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int] = None
    channel: str
    recipient: str
    title: str
    content: str
    status: str
    retry_count: int
    max_retries: int
    last_attempt_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    error_message: Optional[str] = None
    provider_name: str
    provider_metadata: Dict[str, Any] = {}
    idempotency_key: str
    is_marketing: bool
    created_at: str


class NotificationOutboxListResponse(BaseModel):
    items: List[NotificationOutboxResponse]
    total: int
    page: int
    page_size: int


class WorkerStatusResponse(BaseModel):
    is_healthy: bool
    redis_connected: bool
    queue_name: str
    pending_jobs_count: int
    processing_jobs_count: int
    delivered_jobs_count: int
    failed_jobs_count: int
    dead_letter_jobs_count: int
    active_workers_count: int
    checked_at: str

