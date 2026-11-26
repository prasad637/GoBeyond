import json
import os
import secrets
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB_PATH = (_BASE_DIR / "gobeyond.db").as_posix()
_INSECURE_SECRET_MARKERS = (
    "change-in-production",
    "replace-with",
    "gobeyond-super-secret",
    "your_secret_key",
    "changeme",
    "default-secret",
    "<replace",
    "<generate",
    "generate_with",
)


def _contains_placeholder_marker(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return any(marker in lowered for marker in _INSECURE_SECRET_MARKERS) or ("<" in lowered and ">" in lowered)


class Settings(BaseSettings):
    PROJECT_NAME: str = "GO BEYOND"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security (No hardcoded production fallback secret; ephemeral random key generated only in dev/test if unset)
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access token (15 mins)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # Refresh token lifetime (7 days)
    COOKIE_SECURE: Optional[bool] = None   # Defaults to True in production when None; set False only on local HTTP without TLS

    # Database
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_DB_PATH}"
    DB_POOL_SIZE: int = 30
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Redis & Locks
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_REQUIRED_IN_PRODUCTION: bool = True
    USE_MEMORY_LOCK_FALLBACK: bool = False  # Disabled by default in production
    LOCK_EXPIRY_SECONDS: int = 600  # 10 minutes temporary seat/slot lock

    # Razorpay Payment Gateway (Empty defaults; populated via env or ephemeral local test values when sandbox mode is active)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_SANDBOX_MODE: bool = True

    # OTP Provider
    OTP_SANDBOX_MODE: bool = True
    OTP_DEFAULT_DEV_CODE: str = "123456"

    # External Notification Providers (keep "mock" for local/staging testing)
    SMS_PROVIDER: str = "mock"      # mock | twilio | msg91
    EMAIL_PROVIDER: str = "mock"    # mock | sendgrid | ses
    PUSH_PROVIDER: str = "mock"     # mock | fcm

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    MSG91_AUTH_KEY: str = ""
    MSG91_SENDER_ID: str = ""
    MSG91_OTP_TEMPLATE_ID: str = ""

    SENDGRID_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@gobeyond.example.com"
    EMAIL_FROM_NAME: str = "GO BEYOND"

    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    FCM_PROJECT_ID: str = ""
    FCM_SERVER_KEY: str = ""
    FCM_ACCESS_TOKEN: str = ""

    # Initial Launch Location
    DEFAULT_CITY: str = "Hyderabad"
    DEFAULT_STATE: str = "Telangana"
    DEFAULT_COUNTRY: str = "India"

    # Partner Commercials
    DEFAULT_COMMISSION_RATE: float = 0.1000  # Default 10.00% if unconfigured on partner

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str) -> str:
        if v and v.startswith("sqlite:///./"):
            rel_path = v.replace("sqlite:///./", "")
            return f"sqlite:///{(_BASE_DIR / rel_path).as_posix()}"
        return v

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode="after")
    def validate_and_finalize_security(self) -> "Settings":
        env = (self.ENVIRONMENT or "development").strip().lower()
        secret = (self.SECRET_KEY or "").strip()

        if env == "production":
            if not secret or len(secret) < 32 or _contains_placeholder_marker(secret):
                raise ValueError(
                    "PRODUCTION SECURITY ERROR: SECRET_KEY must be set via environment variable to a "
                    "cryptographically strong value (>= 32 characters) without placeholder text."
                )
            if not self.RAZORPAY_SANDBOX_MODE:
                if (
                    not self.RAZORPAY_KEY_ID
                    or not self.RAZORPAY_KEY_SECRET
                    or _contains_placeholder_marker(self.RAZORPAY_KEY_ID)
                    or _contains_placeholder_marker(self.RAZORPAY_KEY_SECRET)
                ):
                    raise ValueError(
                        "PRODUCTION SECURITY ERROR: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set "
                        "to real credentials (without placeholders) when RAZORPAY_SANDBOX_MODE=False."
                    )
        else:
            if not secret:
                self.SECRET_KEY = secrets.token_urlsafe(48)
            if self.RAZORPAY_SANDBOX_MODE:
                if not self.RAZORPAY_KEY_ID:
                    self.RAZORPAY_KEY_ID = "rzp_test_local_sandbox"
                if not self.RAZORPAY_KEY_SECRET:
                    self.RAZORPAY_KEY_SECRET = secrets.token_urlsafe(32)

        return self

    model_config = SettingsConfigDict(
        env_file=str(_BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
