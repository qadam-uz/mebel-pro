"""Reusable FastAPI dependencies.

Use the ``Session`` annotated alias in route signatures::

    @router.get("/things")
    async def list_things(db: Session) -> list[Thing]: ...
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session

Session = Annotated[AsyncSession, Depends(get_session)]
