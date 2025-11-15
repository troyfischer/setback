from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from src.request import RequestContext


def get_session(ctx: RequestContext) -> Generator[Session, None, None]:
    with Session(ctx.db) as session:
        yield session


DBSession = Annotated[Session, Depends(get_session)]
