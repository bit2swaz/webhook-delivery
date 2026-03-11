"""application settings loaded from environment variables via pydantic-settings.

all configuration is centralised here. import `settings` (the singleton) or
`Settings` (the class) for dependency-injection-friendly usage.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """application-wide configuration.

    values are read from environment variables in this priority order:
    1. explicit keyword args (useful in tests)
    2. environment variables
    3. .env file
    4. field defaults defined below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # server
    PORT: int = 8000

    # database - async driver used by fastapi
    DATABASE_URL: str

    # database - sync driver used by celery workers
    SYNC_DATABASE_URL: str

    # test database for pytest fixtures
    TEST_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks_test"

    # redis - broker and result backend
    REDIS_URL: str = "redis://localhost:6379/0"

    # jwt
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # delivery retry configuration
    MAX_DELIVERY_ATTEMPTS: int = 6

    # set to true to run alembic upgrade head on app startup (dev convenience only)
    RUN_MIGRATIONS_ON_START: bool = False

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_use_asyncpg(cls, v: str) -> str:
        """ensure the async database url uses the asyncpg driver.

        Args:
            v: the raw DATABASE_URL string value.

        Returns:
            the validated url string.

        Raises:
            ValueError: if the url does not start with postgresql+asyncpg.
        """
        if not v.startswith("postgresql+asyncpg"):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql+asyncpg' "
                f"(got: {v!r}). "
                "use SYNC_DATABASE_URL for the psycopg2 / celery connection."
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """return a cached Settings singleton.

    uses lru_cache so the .env file is only read once per process lifetime.
    override in tests via app.dependency_overrides[get_settings] = lambda: Settings(...).

    Returns:
        the cached Settings instance.
    """
    return Settings()


# module-level singleton for non-fastapi code (celery tasks, alembic env.py)
settings: Settings = get_settings()
