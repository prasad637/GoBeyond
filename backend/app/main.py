import datetime
import time
import uuid
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from sqlalchemy import func, text

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.redis import get_redis
from app.core.logging import setup_structured_logging, mask_sensitive_data
import app.models  # register models
from app.models.booking import SeatLock
from app.models.notification import NotificationOutbox
from app.api.v1.api import api_router

# Initialize structured application logger
logger = setup_structured_logging(log_level="INFO", json_format=(settings.ENVIRONMENT == "production"))

# Prometheus metrics
REQUEST_COUNT = Counter("gobeyond_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"])
REQUEST_LATENCY = Histogram("gobeyond_http_request_duration_seconds", "HTTP request latency in seconds", ["endpoint"])
ACTIVE_INVENTORY_LOCKS = Gauge("gobeyond_active_inventory_locks", "Active unreleased temporary inventory locks")
DB_UP = Gauge("gobeyond_db_up", "PostgreSQL connectivity status (1=up, 0=down)")
DB_POOL_SIZE = Gauge("gobeyond_db_pool_size", "Configured SQLAlchemy pool size")
DB_POOL_CHECKED_OUT = Gauge("gobeyond_db_pool_checked_out", "Currently checked out SQLAlchemy DB connections")
DB_POOL_CHECKED_IN = Gauge("gobeyond_db_pool_checked_in", "Currently idle SQLAlchemy DB connections")
DB_POOL_OVERFLOW = Gauge("gobeyond_db_pool_overflow", "Current SQLAlchemy pool overflow count")
REDIS_UP = Gauge("gobeyond_redis_up", "Redis connectivity status (1=up, 0=down)")
WORKER_HEARTBEAT_UP = Gauge("gobeyond_worker_heartbeat_up", "ARQ worker heartbeat status in Redis (1=alive, 0=missing)")
NOTIFICATION_OUTBOX_JOBS = Gauge(
    "gobeyond_notification_outbox_jobs",
    "Durable notification outbox job count by status",
    ["status"],
)

app = FastAPI(
    title="GO BEYOND API",
    description="Production-grade RESTful API for GO BEYOND - Discovery, Ticketing, and Reservation Ecosystem",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
)

# CORS Middleware with explicit configuration
origins = settings.BACKEND_CORS_ORIGINS if isinstance(settings.BACKEND_CORS_ORIGINS, list) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After"],
)


@app.middleware("http")
async def security_and_correlation_middleware(request: Request, call_next):
    """
    Production security middleware:
    1. Extracts or assigns request correlation ID (X-Correlation-ID).
    2. Measures request execution duration and logs structured operational telemetry.
    3. Injects defensive HTTP security headers into every response.
    """
    start_time = time.time()

    # 1. Resolve or assign Correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    endpoint = request.url.path
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # 2. Add Defensive HTTP Security Headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = "default-src 'self' http: https: data: blob: 'unsafe-inline'; frame-ancestors 'none';"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Record Prometheus metrics
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start_time)

        # Log structured request completion (filtering health/metrics from noise)
        if not endpoint.startswith(("/health", "/metrics", "/ready")):
            client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
            logger.info(
                f"HTTP {request.method} {endpoint} -> {status_code} ({duration_ms}ms) | IP: {client_ip} | CID: {correlation_id}"
            )

        return response
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status_code=500).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start_time)
        logger.error(f"Unhandled exception during HTTP {request.method} {endpoint}: {mask_sensitive_data(str(exc))} | CID: {correlation_id}")
        raise exc


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches unhandled exceptions and prevents internal stack traces or database errors
    from leaking to external API clients.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.exception(f"Internal Server Error on {request.method} {request.url.path} [CID: {correlation_id}]")

    # In development mode, detail can be given; in production, keep detail strictly opaque
    error_detail = "An internal server error occurred. Please contact support with the correlation ID."
    if settings.DEBUG and settings.ENVIRONMENT != "production":
        error_detail = f"Debug Error: {mask_sensitive_data(str(exc))}"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": error_detail,
            "correlation_id": correlation_id,
            "status_code": 500
        },
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY"
        }
    )


@app.on_event("startup")
def on_startup():
    """Startup verification: validates environment, schemas, and backing datastores."""
    # Production security checks (fail fast on insecure secrets)
    if settings.ENVIRONMENT == "production":
        if settings.DEBUG:
            logger.warning("SECURITY WARNING: DEBUG=True is active in production environment! Forcing DEBUG=False.")
            settings.DEBUG = False
        insecure_markers = ("change-in-production", "replace-with", "gobeyond-super-secret", "changeme", "default-secret")
        if (
            not settings.SECRET_KEY
            or len(settings.SECRET_KEY.strip()) < 32
            or any(m in settings.SECRET_KEY.lower() for m in insecure_markers)
        ):
            logger.critical("SECURITY CRITICAL: Insecure or missing SECRET_KEY detected in production environment!")
            raise RuntimeError("SECURITY CRITICAL: Insecure or missing SECRET_KEY in production environment!")

    # Ensure tables exist in local/dev/test only; production relies on Alembic migrations
    if (settings.ENVIRONMENT or "").strip().lower() != "production":
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.warning(f"Metadata create_all notice: {e}")
    else:
        logger.info("Production startup: skipping metadata.create_all (Alembic migrations required).")

    logger.info(
        f"FastAPI API started in [{settings.ENVIRONMENT}] mode. "
        f"Database pool_size={settings.DB_POOL_SIZE}, max_overflow={settings.DB_MAX_OVERFLOW} "
        f"(Max API DB connections: {settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW}). Version: {settings.VERSION}"
    )


# ==============================================================================
# OPERATIONAL HEALTH & DIAGNOSTIC ENDPOINTS
# ==============================================================================

@app.get("/health", tags=["Health & Diagnostics"])
def health_check():
    """Liveness probe: verifies the API process is running and responsive."""
    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "default_city": settings.DEFAULT_CITY
    }


@app.get("/health/live", tags=["Health & Diagnostics"])
def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "UP", "timestamp": time.time()}


@app.get("/health/ready", tags=["Health & Diagnostics"])
@app.get("/ready", tags=["Health & Diagnostics"])
def readiness_check():
    """
    Readiness probe: validates that database and cache services are connected and ready.
    Returns HTTP 200 if ready, HTTP 503 if backing stores are degraded.
    """
    db_ready = False
    redis_ready = False
    details: Dict[str, Any] = {}

    # Check Database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        db_ready = True
        details["database"] = "CONNECTED"
    except Exception as e:
        details["database"] = f"DEGRADED: {str(e)}"

    # Check Redis
    redis_client = get_redis()
    if redis_client is not None:
        try:
            redis_client.ping()
            redis_ready = True
            details["redis"] = "CONNECTED"
        except Exception as e:
            details["redis"] = f"DEGRADED: {str(e)}"
    else:
        details["redis"] = "UNAVAILABLE"

    is_ready = db_ready and (redis_ready or not settings.REDIS_REQUIRED_IN_PRODUCTION)
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "READY" if is_ready else "NOT_READY",
            "ready": is_ready,
            "components": details,
            "timestamp": time.time()
        }
    )


@app.get("/health/detailed", tags=["Health & Diagnostics"])
def detailed_diagnostics(request: Request):
    """Diagnostic overview for operators: connection pools, cache stats, and runtime info."""
    pool = engine.pool
    pool_stats = {
        "size": pool.size(),
        "checkedin": pool.checkedin(),
        "checkedout": pool.checkedout(),
        "overflow": pool.overflow(),
    } if hasattr(pool, "size") else {"type": type(pool).__name__}

    redis_client = get_redis()
    redis_info = {"status": "CONNECTED" if redis_client else "DISCONNECTED"}
    if redis_client:
        try:
            info = redis_client.info()
            redis_info["used_memory_human"] = info.get("used_memory_human", "N/A")
            redis_info["connected_clients"] = info.get("connected_clients", "N/A")
        except Exception:
            pass

    return {
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "database_pool": pool_stats,
        "redis": redis_info,
        "timestamp": time.time()
    }


@app.get("/metrics", tags=["Monitoring"])
def metrics():
    """Prometheus telemetry scrape endpoint (restricted internally via NGINX)."""
    # 1. SQLAlchemy connection pool gauges
    pool = engine.pool
    if hasattr(pool, "size"):
        try:
            DB_POOL_SIZE.set(pool.size())
            DB_POOL_CHECKED_OUT.set(pool.checkedout())
            DB_POOL_CHECKED_IN.set(pool.checkedin())
            DB_POOL_OVERFLOW.set(max(0, pool.overflow()))
        except Exception:
            pass

    # 2. PostgreSQL health, active locks, and notification outbox backlog
    outbox_statuses = ("PENDING", "PROCESSING", "FAILED", "DEAD_LETTER")
    try:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1;"))
            DB_UP.set(1)

            active_locks = (
                db.query(SeatLock)
                .filter(SeatLock.is_released == False, SeatLock.expires_at > now_utc)
                .count()
            )
            ACTIVE_INVENTORY_LOCKS.set(active_locks)

            counts = dict(
                db.query(NotificationOutbox.status, func.count(NotificationOutbox.id))
                .group_by(NotificationOutbox.status)
                .all()
            )
            for outbox_status in outbox_statuses:
                NOTIFICATION_OUTBOX_JOBS.labels(status=outbox_status).set(counts.get(outbox_status, 0))
        finally:
            db.close()
    except Exception:
        DB_UP.set(0)

    # 3. Redis health & ARQ worker heartbeat gauge
    try:
        redis_client = get_redis()
        if redis_client and redis_client.ping():
            REDIS_UP.set(1)
            WORKER_HEARTBEAT_UP.set(1 if redis_client.get("gobeyond:worker:heartbeat") else 0)
        else:
            REDIS_UP.set(0)
            WORKER_HEARTBEAT_UP.set(0)
    except Exception:
        REDIS_UP.set(0)
        WORKER_HEARTBEAT_UP.set(0)

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)
