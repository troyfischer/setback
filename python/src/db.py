from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, event
from sqlalchemy.engine import Connection
from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.request import RequestContext


def create_db_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url,
        connect_args={},
        pool_pre_ping=True,
    )

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(conn: Connection, _: object) -> None:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_schema(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session(ctx: RequestContext) -> Generator[Session, None, None]:
    with Session(ctx.db) as session:
        yield session


DBSession = Annotated[Session, Depends(get_session)]
