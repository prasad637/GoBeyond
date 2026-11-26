#!/usr/bin/env python3
"""
GO BEYOND — Environment Configuration Validator

Validates `.env`, `.env.example`, `.env.staging.example`, or `.env.production.example`
against local, staging, or production security & connectivity rules WITHOUT printing
secret values to stdout or logs.

Exit codes:
  0 = All required checks passed for the requested mode
  1 = Validation failed (missing/placeholder/insecure settings)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PLACEHOLDER_PATTERNS = (
    r"replace[-_]with",
    r"change[-_]in[-_]production",
    r"generate[-_]with",
    r"changeme",
    r"default[-_]secret",
    r"gobeyond-super-secret",
    r"your_secret_key",
    r"<[^>]+>",
    r"\.\.\.",
)

REQUIRED_COMPOSE_VARS = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "SECRET_KEY",
    "RAZORPAY_KEY_SECRET",
    "GRAFANA_ADMIN_USER",
    "GRAFANA_ADMIN_PASSWORD",
)


def parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        values[key] = val
    return values


def has_placeholder(val: str) -> bool:
    if not val:
        return True
    lowered = val.lower()
    return any(re.search(pat, lowered) for pat in PLACEHOLDER_PATTERNS)


def parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def parse_int(val: str | None, default: int) -> int:
    try:
        return int((val or "").strip())
    except ValueError:
        return default


def parse_cors(raw: str | None) -> Tuple[List[str], bool]:
    if not raw:
        return [], True
    s = raw.strip()
    try:
        if s.startswith("["):
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed], True
        return [x.strip() for x in s.split(",") if x.strip()], True
    except Exception:
        return [], False


def validate_env(env: Dict[str, str], mode: str, template_check: bool = False) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Required keys present
    for key in REQUIRED_COMPOSE_VARS:
        val = env.get(key, "")
        if not val:
            errors.append(f"{key}: missing or empty")
        elif not template_check and has_placeholder(val):
            errors.append(f"{key}: still contains placeholder/insecure marker")

    # 2. SECRET_KEY strength
    secret = env.get("SECRET_KEY", "")
    if not template_check:
        if len(secret) < 32:
            errors.append(f"SECRET_KEY: length {len(secret)} < 32 characters minimum")
    elif not secret:
        errors.append("SECRET_KEY: template key missing")

    # 3. POSTGRES_PASSWORD check against weak defaults
    pg_pass = env.get("POSTGRES_PASSWORD", "")
    if not template_check and pg_pass.lower() in {"postgres", "password", "123456", "admin", "gobeyond"}:
        errors.append("POSTGRES_PASSWORD: weak dictionary password rejected")

    # 4. Connection pool math against default PostgreSQL max_connections=100 (97 usable)
    workers = max(1, parse_int(env.get("UVICORN_WORKERS"), 1))
    api_pool = parse_int(env.get("DB_POOL_SIZE"), 30)
    api_overflow = parse_int(env.get("DB_MAX_OVERFLOW"), 20)
    worker_pool = parse_int(env.get("WORKER_DB_POOL_SIZE"), 10)
    worker_overflow = parse_int(env.get("WORKER_DB_MAX_OVERFLOW"), 5)
    total_pg_conns = (workers * (api_pool + api_overflow)) + (worker_pool + worker_overflow)
    if total_pg_conns > 97:
        errors.append(
            f"Database pool total ({workers} workers * ({api_pool}+{api_overflow}) + ({worker_pool}+{worker_overflow}) = {total_pg_conns}) "
            f"exceeds default PostgreSQL usable connections (97)."
        )

    # 5. Same-origin NEXT_PUBLIC_API_URL check (NGINX routes /api/v1 on same origin)
    next_api = env.get("NEXT_PUBLIC_API_URL", "")
    if next_api.endswith("/api") or next_api.endswith("/api/"):
        errors.append("NEXT_PUBLIC_API_URL ends with '/api' which causes double '/api/api/v1' prefixing")

    # 6. Redis & Lock settings
    use_mem_fallback = parse_bool(env.get("USE_MEMORY_LOCK_FALLBACK"), False)
    redis_req = parse_bool(env.get("REDIS_REQUIRED_IN_PRODUCTION"), True)
    redis_url = env.get("REDIS_URL", "")
    if not redis_url.startswith("redis://") and not redis_url.startswith("rediss://"):
        errors.append("REDIS_URL: must use redis:// or rediss:// scheme")

    if mode in ("staging", "production"):
        if use_mem_fallback:
            errors.append("USE_MEMORY_LOCK_FALLBACK must be false in staging/production")
        if not redis_req:
            errors.append("REDIS_REQUIRED_IN_PRODUCTION must be true in staging/production")
        if parse_bool(env.get("DEBUG"), False):
            errors.append("DEBUG must be false in staging/production")

    # 7. CORS & Cookie posture
    cors_list, cors_ok = parse_cors(env.get("BACKEND_CORS_ORIGINS"))
    if not cors_ok:
        errors.append("BACKEND_CORS_ORIGINS: invalid JSON array or comma-separated origin list")
    elif "*" in cors_list:
        errors.append("BACKEND_CORS_ORIGINS: wildcard '*' is insecure with credentialed cookies")

    cookie_secure = parse_bool(env.get("COOKIE_SECURE"), False)
    rzp_sandbox = parse_bool(env.get("RAZORPAY_SANDBOX_MODE"), True)
    otp_sandbox = parse_bool(env.get("OTP_SANDBOX_MODE"), True)
    sms_provider = (env.get("SMS_PROVIDER") or "mock").strip().lower()
    email_provider = (env.get("EMAIL_PROVIDER") or "mock").strip().lower()
    push_provider = (env.get("PUSH_PROVIDER") or "mock").strip().lower()

    if sms_provider not in ("mock", "twilio", "msg91"):
        errors.append(f"SMS_PROVIDER must be mock|twilio|msg91 (got '{sms_provider}')")
    if email_provider not in ("mock", "sendgrid", "ses"):
        errors.append(f"EMAIL_PROVIDER must be mock|sendgrid|ses (got '{email_provider}')")
    if push_provider not in ("mock", "fcm"):
        errors.append(f"PUSH_PROVIDER must be mock|fcm (got '{push_provider}')")

    if mode == "local":
        if not cookie_secure:
            warnings.append("COOKIE_SECURE=false is acceptable only on plain HTTP http://localhost without TLS.")
        if rzp_sandbox:
            warnings.append("RAZORPAY_SANDBOX_MODE=true active (sandbox mode; no real charges).")
        if otp_sandbox:
            warnings.append("OTP_SANDBOX_MODE=true active (local dev OTP code).")
        if sms_provider == "mock" or email_provider == "mock" or push_provider == "mock":
            warnings.append("Mock notification adapters active (SMS/Email/Push); no external messages dispatched.")

    elif mode == "staging":
        if not cookie_secure:
            errors.append("COOKIE_SECURE must be true in staging (behind staging TLS)")
        if not rzp_sandbox:
            errors.append("RAZORPAY_SANDBOX_MODE must remain true in staging")
        if not otp_sandbox:
            warnings.append("OTP_SANDBOX_MODE=false in staging: ensure test SMS/email sink is configured.")
        if any(o.startswith("http://localhost") or o.startswith("http://127.0.0.1") for o in cors_list):
            errors.append("BACKEND_CORS_ORIGINS: remove localhost origins in staging")

    elif mode == "production":
        env_name = (env.get("ENVIRONMENT") or "").strip().lower()
        if env_name != "production":
            errors.append(f"ENVIRONMENT must be 'production' (got '{env_name or '<unset>'}')")
        if not cookie_secure:
            errors.append("COOKIE_SECURE must be true in live HTTPS production")
        if rzp_sandbox:
            errors.append("RAZORPAY_SANDBOX_MODE must be false in live production")
        if otp_sandbox:
            errors.append("OTP_SANDBOX_MODE must be false in live production")
        rzp_id = env.get("RAZORPAY_KEY_ID", "")
        if not rzp_id.startswith("rzp_live_"):
            errors.append("RAZORPAY_KEY_ID must use a live key ('rzp_live_...') in production")
        if not template_check and (has_placeholder(rzp_id) or has_placeholder(env.get("RAZORPAY_KEY_SECRET", ""))):
            errors.append("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET contain placeholders")
        if not cors_list or any(not o.startswith("https://") for o in cors_list):
            errors.append("BACKEND_CORS_ORIGINS: production origins must all use https://")
        if any("example.com" in o for o in cors_list) and not template_check:
            errors.append("BACKEND_CORS_ORIGINS still uses placeholder domain example.com")
        if "sqlite" in (env.get("DATABASE_URL") or "").lower():
            errors.append("DATABASE_URL: SQLite is unsupported in production; use PostgreSQL")

        if sms_provider == "mock" and not template_check:
            errors.append("SMS_PROVIDER must be 'twilio' or 'msg91' (not 'mock') in live production")
        elif sms_provider == "twilio":
            for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"):
                v = env.get(k, "")
                if not v or (not template_check and has_placeholder(v)):
                    errors.append(f"{k}: missing or placeholder while SMS_PROVIDER=twilio")
        elif sms_provider == "msg91":
            for k in ("MSG91_AUTH_KEY", "MSG91_SENDER_ID"):
                v = env.get(k, "")
                if not v or (not template_check and has_placeholder(v)):
                    errors.append(f"{k}: missing or placeholder while SMS_PROVIDER=msg91")

        if email_provider == "mock" and not template_check:
            errors.append("EMAIL_PROVIDER must be 'sendgrid' or 'ses' (not 'mock') in live production")
        elif email_provider == "sendgrid":
            for k in ("SENDGRID_API_KEY", "EMAIL_FROM_ADDRESS"):
                v = env.get(k, "")
                if not v or (not template_check and has_placeholder(v)):
                    errors.append(f"{k}: missing or placeholder while EMAIL_PROVIDER=sendgrid")
        elif email_provider == "ses":
            for k in ("AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "EMAIL_FROM_ADDRESS"):
                v = env.get(k, "")
                if not v or (not template_check and has_placeholder(v)):
                    errors.append(f"{k}: missing or placeholder while EMAIL_PROVIDER=ses")

        if push_provider == "fcm":
            has_v1 = bool(env.get("FCM_PROJECT_ID")) and bool(env.get("FCM_ACCESS_TOKEN"))
            has_legacy = bool(env.get("FCM_SERVER_KEY"))
            if not (has_v1 or has_legacy):
                errors.append("PUSH_PROVIDER=fcm requires FCM_PROJECT_ID + FCM_ACCESS_TOKEN (or FCM_SERVER_KEY)")
            elif not template_check:
                for k in ("FCM_PROJECT_ID", "FCM_ACCESS_TOKEN", "FCM_SERVER_KEY"):
                    if env.get(k) and has_placeholder(env[k]):
                        errors.append(f"{k}: contains placeholder while PUSH_PROVIDER=fcm")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GO BEYOND environment file safely without exposing secrets.")
    parser.add_argument("--env-file", default=".env", help="Path to environment file (default: .env)")
    parser.add_argument(
        "--mode",
        choices=("local", "staging", "production"),
        default="local",
        help="Validation profile strictness (default: local)",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="Validate structure/policy of a *.example template while allowing placeholder markers",
    )
    args = parser.parse_args()

    path = Path(args.env_file)
    if not path.is_file():
        print(f"[ERROR] Environment file not found: {path}", file=sys.stderr)
        return 1

    env_map = parse_env_file(path)
    errors, warnings = validate_env(env_map, mode=args.mode, template_check=args.template)

    print(f"ENV_VALIDATION_FILE={path} MODE={args.mode} TEMPLATE={args.template} KEYS={len(env_map)}")
    for w in warnings:
        print(f"[WARN]  {w}")
    for e in errors:
        print(f"[FAIL]  {e}", file=sys.stderr)

    if errors:
        print(f"ENV_VALIDATION_RESULT=FAILED ({len(errors)} error(s))", file=sys.stderr)
        return 1

    print("ENV_VALIDATION_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

