"""unit tests for app/core/config.py - settings loading and validation."""

import pytest

from app.core.config import Settings


class TestSettingsDefaults:
    """settings loads correctly with environment variable overrides."""

    def test_database_url_loaded(self) -> None:
        """settings.DATABASE_URL is set and starts with postgresql+asyncpg."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.DATABASE_URL.startswith("postgresql+asyncpg")

    def test_sync_database_url_loaded(self) -> None:
        """settings.SYNC_DATABASE_URL uses psycopg2 driver."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.SYNC_DATABASE_URL.startswith("postgresql+psycopg2")

    def test_redis_url_has_default(self) -> None:
        """settings.REDIS_URL defaults to localhost redis."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.REDIS_URL.startswith("redis://")

    def test_port_defaults_to_8000(self) -> None:
        """settings.PORT defaults to 8000."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.PORT == 8000

    def test_max_delivery_attempts_default(self) -> None:
        """settings.MAX_DELIVERY_ATTEMPTS defaults to 6."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.MAX_DELIVERY_ATTEMPTS == 6

    def test_access_token_expire_minutes_default(self) -> None:
        """settings.ACCESS_TOKEN_EXPIRE_MINUTES defaults to 60."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_jwt_secret_is_loaded(self) -> None:
        """settings.JWT_SECRET is populated from env/init arg."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="mysecret123",
        )
        assert s.JWT_SECRET == "mysecret123"

    def test_database_url_must_use_asyncpg_driver(self) -> None:
        """settings raises ValueError if DATABASE_URL uses wrong driver."""
        with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
            Settings(
                DATABASE_URL="postgresql://u:p@localhost:5432/db",
                SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
                JWT_SECRET="testsecret",
            )

    def test_run_migrations_on_start_defaults_false(self) -> None:
        """settings.RUN_MIGRATIONS_ON_START defaults to False."""
        s = Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
            SYNC_DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/db",
            JWT_SECRET="testsecret",
        )
        assert s.RUN_MIGRATIONS_ON_START is False
