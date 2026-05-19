import enum

from pydantic_settings import BaseSettings

DEFAULT_SESSION_SECRET = "your-super-secret-key"
DEFAULT_JWT_SECRET = "your-secret-key-change-this-in-production"
DEFAULT_JWT_ALGORITHM = "HS256"


class AppEnv(enum.StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    app_env: AppEnv = AppEnv.DEV
    enable_dev_auth: bool = False
    database_url: str = "sqlite:///database.db"
    redis_url: str = "redis://localhost:6379"
    session_secret: str = DEFAULT_SESSION_SECRET
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = DEFAULT_JWT_ALGORITHM
    client_origin: str = "http://localhost:8081"
    dev_cors_origin_regex: str = (
        r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?"
    )

    @property
    def dev_auth_enabled(self) -> bool:
        return self.app_env in {AppEnv.DEV, AppEnv.TEST} and self.enable_dev_auth

    @property
    def cors_allowed_origins(self) -> list[str]:
        if self.app_env == AppEnv.PROD:
            return [self.client_origin]
        return []

    @property
    def cors_origin_regex(self) -> str | None:
        if self.app_env == AppEnv.PROD:
            return None
        return self.dev_cors_origin_regex

    def validate_runtime(self) -> None:
        if self.app_env == AppEnv.PROD and self.enable_dev_auth:
            raise RuntimeError("ENABLE_DEV_AUTH cannot be enabled when APP_ENV=prod")
        if self.app_env == AppEnv.PROD and self.session_secret == DEFAULT_SESSION_SECRET:
            raise RuntimeError("SESSION_SECRET must be changed when APP_ENV=prod")
        if self.app_env == AppEnv.PROD and self.jwt_secret == DEFAULT_JWT_SECRET:
            raise RuntimeError("JWT_SECRET must be changed when APP_ENV=prod")
