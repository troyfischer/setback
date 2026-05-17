from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///database.db"
    redis_url: str = "redis://localhost:6379"
    session_secret: str = "your-super-secret-key"
    client_origin: str = "http://localhost:8081"
    cors_origin_regex: str = (
        r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?"
    )
