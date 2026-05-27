"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from cve_monitor.db.base import get_session


def db_dep() -> Iterator[Session]:
    yield from get_session()


SessionDep = Annotated[Session, Depends(db_dep)]
