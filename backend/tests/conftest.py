import os
import pytest
from app.core.config import settings
from app.core.database import engine
from app.core.locks import lock_service


def pytest_runtest_setup(item):
    """
    Enforces that tests marked with @pytest.mark.integration or executed under
    ENVIRONMENT=integration_test strictly connect to live PostgreSQL 16 and Redis 7 instances.
    Guarantees that test configuration CANNOT silently replace PostgreSQL with SQLite
    or fall back to in-memory locking.
    """
    is_integration = "integration" in item.keywords or settings.ENVIRONMENT == "integration_test"
    if is_integration:
        # 1. Enforce PostgreSQL
        db_url = str(engine.url)
        driver = engine.url.drivername.lower()
        if not ("postgres" in driver or "psycopg" in driver or "asyncpg" in driver):
            pytest.fail(
                f"\n[INTEGRATION TEST CONFIGURATION ERROR]\n"
                f"Integration tests require real PostgreSQL, but detected database driver: '{driver}' ({db_url}).\n"
                f"Silent fallback to SQLite is strictly forbidden for integration tests.\n"
                f"Please ensure DATABASE_URL points to a running PostgreSQL 16 instance.\n"
            )

        # 2. Enforce Redis
        if not lock_service.redis_client:
            pytest.fail(
                f"\n[INTEGRATION TEST CONFIGURATION ERROR]\n"
                f"Integration tests require a live Redis 7 instance, but lock_service.redis_client is None.\n"
                f"Silent fallback to InMemoryLockManager is strictly forbidden for integration tests.\n"
                f"Please ensure REDIS_URL points to a running Redis 7 instance.\n"
            )

        try:
            lock_service.redis_client.ping()
        except Exception as e:
            pytest.fail(
                f"\n[INTEGRATION TEST CONFIGURATION ERROR]\n"
                f"Failed to connect to Redis at {settings.REDIS_URL}: {e}\n"
                f"Live Redis 7 is required for integration tests.\n"
            )

        # 3. Disable in-memory lock fallback completely
        settings.USE_MEMORY_LOCK_FALLBACK = False
        settings.REDIS_REQUIRED_IN_PRODUCTION = True


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def db_session():
    test_engine = create_engine(settings.DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        test_engine.dispose()


