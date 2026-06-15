from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]
