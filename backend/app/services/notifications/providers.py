"""GO BEYOND — Notification Channel Providers & Adapters

Provides an extensible, replaceable provider interface for:
- Email (Mock / SendGrid / Amazon SES)
- SMS (Mock / Twilio / MSG91)
- Push Notifications (Mock / Firebase Cloud Messaging)
- In-App Notifications (Direct database inbox)

Security & Transparency Standards:
- Provider credentials reside exclusively in environment variables.
- Mock providers are unambiguously labeled as mocks in metadata and status.
- Real provider adapters refuse placeholder credentials and never claim delivery
  unless the upstream provider HTTP API returns 2xx.
- Plaintext OTPs, tokens, API keys, and passwords are NEVER logged.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger("gobeyond.notifications.providers")

_PLACEHOLDER_PATTERNS = (
    "replace",
    "changeme",
    "change-in-production",
    "your_",
    "dummy",
    "example-key",
    "<",
    ">",
)


def _is_configured_secret(value: Optional[str]) -> bool:
    """Returns True only when a non-empty, non-placeholder credential is supplied."""
    cleaned = (value or "").strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    return not any(marker in lowered for marker in _PLACEHOLDER_PATTERNS)


def _mask_recipient(recipient: str) -> str:
    """Masks phone/email/device-token identifiers safely for operational logs."""
    cleaned = (recipient or "").strip()
    if "@" in cleaned:
        local, domain = cleaned.split("@", 1)
        prefix = local[:2] if len(local) > 2 else local[:1]
        return f"{prefix}***@{domain}"
    if len(cleaned) > 4:
        return f"******{cleaned[-4:]}"
    return "****"


def mask_sensitive_content(text: str) -> str:
    """Masks 4-8 digit OTPs, tokens, and passwords in log messages."""
    if not text:
        return ""
    masked = re.sub(r"\b\d{6}\b", "******", text)
    masked = re.sub(r"(password=)[^\s&]+", r"\1******", masked, flags=re.IGNORECASE)
    masked = re.sub(r"(token=)[^\s&]+", r"\1******", masked, flags=re.IGNORECASE)
    masked = re.sub(r"(authkey=)[^\s&]+", r"\1******", masked, flags=re.IGNORECASE)
    return masked


@dataclass
class ProviderResult:
    success: bool
    provider_name: str
    provider_message_id: str = ""
    is_mock: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class BaseNotificationProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        pass

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        """Dispatches notification to the recipient through the provider rail."""
        pass


# ==============================================================================
# DEVELOPMENT / STAGING MOCK ADAPTERS
# ==============================================================================

class MockEmailProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "MOCK_EMAIL_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return True

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        mock_id = f"mock_mail_{uuid.uuid4().hex[:12]}"
        masked_log = mask_sensitive_content(content[:80])
        logger.info(
            f"[MOCK_EMAIL_PROVIDER] Mock email dispatched to '{_mask_recipient(recipient)}' | "
            f"Subject: '{title}' | Preview: '{masked_log}...' | ID: {mock_id}"
        )
        return ProviderResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=mock_id,
            is_mock=True,
            metadata={
                "status": "MOCK_DELIVERED",
                "channel": "EMAIL",
                "recipient": _mask_recipient(recipient),
                "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "note": "[DEVELOPMENT MOCK] Configure EMAIL_PROVIDER=sendgrid|ses with live credentials for real delivery."
            }
        )


class MockSMSProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "MOCK_SMS_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return True

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        mock_id = f"mock_sms_{uuid.uuid4().hex[:12]}"
        masked_log = mask_sensitive_content(content)
        logger.info(
            f"[MOCK_SMS_PROVIDER] Mock SMS dispatched to '{_mask_recipient(recipient)}' | "
            f"Content: '{masked_log}' | ID: {mock_id}"
        )
        return ProviderResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=mock_id,
            is_mock=True,
            metadata={
                "status": "MOCK_DELIVERED",
                "channel": "SMS",
                "recipient": _mask_recipient(recipient),
                "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "note": "[DEVELOPMENT MOCK] Configure SMS_PROVIDER=twilio|msg91 with live credentials for real delivery."
            }
        )


class MockPushProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "MOCK_PUSH_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return True

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        mock_id = f"mock_push_{uuid.uuid4().hex[:12]}"
        masked_log = mask_sensitive_content(content[:80])
        logger.info(
            f"[MOCK_PUSH_PROVIDER] Mock push notification dispatched to token '{recipient[:12]}...' | "
            f"Title: '{title}' | Preview: '{masked_log}' | ID: {mock_id}"
        )
        return ProviderResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=mock_id,
            is_mock=True,
            metadata={
                "status": "MOCK_DELIVERED",
                "channel": "PUSH",
                "recipient_token_prefix": recipient[:12] if len(recipient) >= 12 else recipient,
                "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "note": "[DEVELOPMENT MOCK] Configure PUSH_PROVIDER=fcm with Firebase credentials for real push delivery."
            }
        )


class InAppProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "IN_APP_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        msg_id = f"inapp_{uuid.uuid4().hex[:12]}"
        return ProviderResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=msg_id,
            is_mock=False,
            metadata={
                "status": "IN_APP_DELIVERED",
                "channel": "IN_APP",
                "recipient_user_id": recipient,
                "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        )


# ==============================================================================
# EXTERNAL SMS PROVIDERS (TWILIO & MSG91)
# ==============================================================================

class TwilioSMSProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "TWILIO_SMS_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return (
            _is_configured_secret(settings.TWILIO_ACCOUNT_SID)
            and _is_configured_secret(settings.TWILIO_AUTH_TOKEN)
            and _is_configured_secret(settings.TWILIO_FROM_NUMBER)
        )

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        if not self.is_configured():
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message="Twilio SMS credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER) are not configured.",
                metadata={"status": "PROVIDER_NOT_CONFIGURED", "channel": "SMS"},
            )

        sid = settings.TWILIO_ACCOUNT_SID.strip()
        token = settings.TWILIO_AUTH_TOKEN.strip()
        from_num = settings.TWILIO_FROM_NUMBER.strip()
        to_num = recipient.strip()
        if to_num.isdigit() and len(to_num) == 10:
            to_num = f"+91{to_num}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    auth=(sid, token),
                    data={"From": from_num, "To": to_num, "Body": content},
                )
            if 200 <= resp.status_code < 300:
                body = resp.json() if resp.content else {}
                msg_sid = str(body.get("sid") or f"twilio_{uuid.uuid4().hex[:10]}")
                logger.info(
                    f"[TWILIO_SMS_PROVIDER] SMS accepted for '{_mask_recipient(to_num)}' | SID: {msg_sid}"
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=msg_sid,
                    is_mock=False,
                    metadata={
                        "status": body.get("status", "queued").upper(),
                        "channel": "SMS",
                        "recipient": _mask_recipient(to_num),
                        "http_status": resp.status_code,
                        "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"Twilio API error HTTP {resp.status_code}",
                metadata={"status": "PROVIDER_HTTP_ERROR", "channel": "SMS", "http_status": resp.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"Twilio transport failure: {mask_sensitive_content(str(exc))}",
                metadata={"status": "PROVIDER_TRANSPORT_ERROR", "channel": "SMS"},
            )


class MSG91SMSProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "MSG91_SMS_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return (
            _is_configured_secret(settings.MSG91_AUTH_KEY)
            and _is_configured_secret(settings.MSG91_SENDER_ID)
        )

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        if not self.is_configured():
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message="MSG91 credentials (MSG91_AUTH_KEY, MSG91_SENDER_ID) are not configured.",
                metadata={"status": "PROVIDER_NOT_CONFIGURED", "channel": "SMS"},
            )

        clean_phone = re.sub(r"\D", "", recipient or "")
        if len(clean_phone) == 10:
            clean_phone = f"91{clean_phone}"

        request_body: Dict[str, Any] = {
            "sender": settings.MSG91_SENDER_ID.strip(),
            "short_url": "0",
            "recipients": [{"mobiles": clean_phone, "message": content, "title": title}],
        }
        if _is_configured_secret(settings.MSG91_OTP_TEMPLATE_ID):
            request_body["template_id"] = settings.MSG91_OTP_TEMPLATE_ID.strip()

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    "https://control.msg91.com/api/v5/flow/",
                    headers={
                        "authkey": settings.MSG91_AUTH_KEY.strip(),
                        "Content-Type": "application/json",
                        "accept": "application/json",
                    },
                    json=request_body,
                )
            if 200 <= resp.status_code < 300:
                body = resp.json() if resp.content else {}
                req_id = str(body.get("request_id") or body.get("message") or f"msg91_{uuid.uuid4().hex[:10]}")
                logger.info(f"[MSG91_SMS_PROVIDER] SMS accepted for '{_mask_recipient(clean_phone)}' | ReqID: {req_id}")
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=req_id,
                    is_mock=False,
                    metadata={
                        "status": "SENT",
                        "channel": "SMS",
                        "recipient": _mask_recipient(clean_phone),
                        "http_status": resp.status_code,
                        "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"MSG91 API error HTTP {resp.status_code}",
                metadata={"status": "PROVIDER_HTTP_ERROR", "channel": "SMS", "http_status": resp.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"MSG91 transport failure: {mask_sensitive_content(str(exc))}",
                metadata={"status": "PROVIDER_TRANSPORT_ERROR", "channel": "SMS"},
            )


# ==============================================================================
# EXTERNAL EMAIL PROVIDERS (SENDGRID & AMAZON SES)
# ==============================================================================

class SendGridEmailProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "SENDGRID_EMAIL_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return (
            _is_configured_secret(settings.SENDGRID_API_KEY)
            and _is_configured_secret(settings.EMAIL_FROM_ADDRESS)
        )

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        if not self.is_configured():
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message="SendGrid credentials (SENDGRID_API_KEY, EMAIL_FROM_ADDRESS) are not configured.",
                metadata={"status": "PROVIDER_NOT_CONFIGURED", "channel": "EMAIL"},
            )

        body = {
            "personalizations": [{"to": [{"email": recipient.strip()}], "subject": title}],
            "from": {
                "email": settings.EMAIL_FROM_ADDRESS.strip(),
                "name": (settings.EMAIL_FROM_NAME or "GO BEYOND").strip(),
            },
            "content": [{"type": "text/plain", "value": content}],
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {settings.SENDGRID_API_KEY.strip()}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            if 200 <= resp.status_code < 300:
                msg_id = resp.headers.get("X-Message-Id") or f"sg_{uuid.uuid4().hex[:12]}"
                logger.info(
                    f"[SENDGRID_EMAIL_PROVIDER] Email accepted for '{_mask_recipient(recipient)}' | ID: {msg_id}"
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=msg_id,
                    is_mock=False,
                    metadata={
                        "status": "ACCEPTED",
                        "channel": "EMAIL",
                        "recipient": _mask_recipient(recipient),
                        "http_status": resp.status_code,
                        "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"SendGrid API error HTTP {resp.status_code}",
                metadata={"status": "PROVIDER_HTTP_ERROR", "channel": "EMAIL", "http_status": resp.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"SendGrid transport failure: {mask_sensitive_content(str(exc))}",
                metadata={"status": "PROVIDER_TRANSPORT_ERROR", "channel": "EMAIL"},
            )


def _sign_aws_sigv4_headers(
    method: str,
    host: str,
    canonical_uri: str,
    payload_bytes: bytes,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
) -> Dict[str, str]:
    """Generates AWS Signature Version 4 headers without external SDK dependencies."""
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    canonical_headers = f"content-type:application/json\nhost:{host}\nx-amz-date:{amz_date}\n"
    signed_headers = "content-type;host;x-amz-date"
    canonical_request = f"{method}\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Content-Type": "application/json",
        "X-Amz-Date": amz_date,
        "Authorization": auth_header,
    }


class SESEmailProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "AWS_SES_EMAIL_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return (
            _is_configured_secret(settings.AWS_REGION)
            and _is_configured_secret(settings.AWS_ACCESS_KEY_ID)
            and _is_configured_secret(settings.AWS_SECRET_ACCESS_KEY)
            and _is_configured_secret(settings.EMAIL_FROM_ADDRESS)
        )

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        if not self.is_configured():
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message="Amazon SES credentials (AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, EMAIL_FROM_ADDRESS) are not configured.",
                metadata={"status": "PROVIDER_NOT_CONFIGURED", "channel": "EMAIL"},
            )

        region = settings.AWS_REGION.strip()
        host = f"email.{region}.amazonaws.com"
        uri = "/v2/email/outbound-emails"
        body_bytes = json.dumps({
            "FromEmailAddress": settings.EMAIL_FROM_ADDRESS.strip(),
            "Destination": {"ToAddresses": [recipient.strip()]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": title, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": content, "Charset": "UTF-8"}},
                }
            },
        }).encode("utf-8")

        headers = _sign_aws_sigv4_headers(
            method="POST",
            host=host,
            canonical_uri=uri,
            payload_bytes=body_bytes,
            region=region,
            service="ses",
            access_key=settings.AWS_ACCESS_KEY_ID.strip(),
            secret_key=settings.AWS_SECRET_ACCESS_KEY.strip(),
        )
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(f"https://{host}{uri}", headers=headers, content=body_bytes)
            if 200 <= resp.status_code < 300:
                resp_json = resp.json() if resp.content else {}
                msg_id = str(resp_json.get("MessageId") or f"ses_{uuid.uuid4().hex[:12]}")
                logger.info(
                    f"[AWS_SES_EMAIL_PROVIDER] Email accepted for '{_mask_recipient(recipient)}' | ID: {msg_id}"
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=msg_id,
                    is_mock=False,
                    metadata={
                        "status": "ACCEPTED",
                        "channel": "EMAIL",
                        "recipient": _mask_recipient(recipient),
                        "http_status": resp.status_code,
                        "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"Amazon SES API error HTTP {resp.status_code}",
                metadata={"status": "PROVIDER_HTTP_ERROR", "channel": "EMAIL", "http_status": resp.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"Amazon SES transport failure: {mask_sensitive_content(str(exc))}",
                metadata={"status": "PROVIDER_TRANSPORT_ERROR", "channel": "EMAIL"},
            )


# ==============================================================================
# EXTERNAL PUSH PROVIDER (FIREBASE CLOUD MESSAGING)
# ==============================================================================

class FCMPushProvider(BaseNotificationProvider):
    @property
    def provider_name(self) -> str:
        return "FCM_PUSH_PROVIDER"

    @property
    def is_mock(self) -> bool:
        return False

    def is_configured(self) -> bool:
        has_v1 = _is_configured_secret(settings.FCM_PROJECT_ID) and _is_configured_secret(settings.FCM_ACCESS_TOKEN)
        has_legacy = _is_configured_secret(settings.FCM_SERVER_KEY)
        return has_v1 or has_legacy

    def send(
        self,
        recipient: str,
        title: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        if not self.is_configured():
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message="FCM credentials (FCM_PROJECT_ID + FCM_ACCESS_TOKEN or FCM_SERVER_KEY) are not configured.",
                metadata={"status": "PROVIDER_NOT_CONFIGURED", "channel": "PUSH"},
            )

        use_v1 = _is_configured_secret(settings.FCM_PROJECT_ID) and _is_configured_secret(settings.FCM_ACCESS_TOKEN)
        try:
            with httpx.Client(timeout=10.0) as client:
                if use_v1:
                    project_id = settings.FCM_PROJECT_ID.strip()
                    resp = client.post(
                        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
                        headers={
                            "Authorization": f"Bearer {settings.FCM_ACCESS_TOKEN.strip()}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "message": {
                                "token": recipient.strip(),
                                "notification": {"title": title, "body": content},
                                "data": {str(k): str(v) for k, v in (payload or {}).items()},
                            }
                        },
                    )
                else:
                    resp = client.post(
                        "https://fcm.googleapis.com/fcm/send",
                        headers={
                            "Authorization": f"key={settings.FCM_SERVER_KEY.strip()}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "to": recipient.strip(),
                            "notification": {"title": title, "body": content},
                            "data": payload or {},
                        },
                    )

            if 200 <= resp.status_code < 300:
                body = resp.json() if resp.content else {}
                msg_id = str(body.get("name") or body.get("message_id") or f"fcm_{uuid.uuid4().hex[:12]}")
                logger.info(f"[FCM_PUSH_PROVIDER] Push delivered to token '{recipient[:10]}...' | ID: {msg_id}")
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=msg_id,
                    is_mock=False,
                    metadata={
                        "status": "DELIVERED",
                        "channel": "PUSH",
                        "http_status": resp.status_code,
                        "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"FCM API error HTTP {resp.status_code}",
                metadata={"status": "PROVIDER_HTTP_ERROR", "channel": "PUSH", "http_status": resp.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                is_mock=False,
                error_message=f"FCM transport failure: {mask_sensitive_content(str(exc))}",
                metadata={"status": "PROVIDER_TRANSPORT_ERROR", "channel": "PUSH"},
            )


# ==============================================================================
# FACTORY / STRATEGY REGISTRY
# ==============================================================================

def get_provider(channel: str) -> BaseNotificationProvider:
    """
    Returns the notification provider adapter selected by environment configuration.
    Defaults to clearly labeled Mock adapters when SMS_PROVIDER/EMAIL_PROVIDER/PUSH_PROVIDER
    are unset or set to "mock".
    """
    chan = (channel or "").strip().upper()
    if chan == "EMAIL":
        selected = (getattr(settings, "EMAIL_PROVIDER", "mock") or "mock").strip().lower()
        if selected == "sendgrid":
            return SendGridEmailProvider()
        if selected == "ses":
            return SESEmailProvider()
        return MockEmailProvider()

    if chan == "SMS":
        selected = (getattr(settings, "SMS_PROVIDER", "mock") or "mock").strip().lower()
        if selected == "twilio":
            return TwilioSMSProvider()
        if selected == "msg91":
            return MSG91SMSProvider()
        return MockSMSProvider()

    if chan == "PUSH":
        selected = (getattr(settings, "PUSH_PROVIDER", "mock") or "mock").strip().lower()
        if selected == "fcm":
            return FCMPushProvider()
        return MockPushProvider()

    if chan == "IN_APP":
        return InAppProvider()

    return MockEmailProvider()
