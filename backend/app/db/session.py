from typing import AsyncGenerator, Optional

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Alias for backward compatibility
async_session_maker = AsyncSessionLocal


class Base(DeclarativeBase):
    pass


async def get_db(request: Request = None) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[assignment]
    """
    Yield an async DB session.

    If a tenant_id is available on request.state (set by TenantMiddleware),
    the PostgreSQL session variable `app.current_tenant_id` is set so that
    Row-Level Security policies can enforce multi-tenant isolation.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Set RLS session variable when tenant context is available
            tenant_id: Optional[str] = None
            if request is not None:
                tenant_id = getattr(request.state, "tenant_id", None)

            if tenant_id:
                # Start a transaction and set the local variable
                # Note: SET LOCAL only works within a transaction
                await session.execute(text("BEGIN"))
                # Use string formatting with UUID validation to prevent SQL injection
                from uuid import UUID
                validated_id = str(UUID(str(tenant_id)))  # Validates UUID format
                await session.execute(text(f"SET LOCAL app.current_tenant_id = '{validated_id}'"))

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
