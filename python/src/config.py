from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///database.db"
    redis_url: str = "redis://localhost:6379"
    session_secret: str = "your-super-secret-key"
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:19006",
    ]
    client_origin: str = "http://localhost:8081"
