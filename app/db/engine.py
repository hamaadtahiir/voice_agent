from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _build_engine():
    """Create the async SQLAlchemy engine based on DATABASE_URL."""
    settings = get_settings()
    url = settings.DATABASE_URL

    connect_args = {}
    pool_kwargs = {}

    if url.startswith("sqlite"):
        # SQLite-specific settings
        connect_args["check_same_thread"] = False
        pool_kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL-specific settings
        pool_kwargs.update(
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )

    return create_async_engine(
        url,
        echo=settings.DEBUG,
        connect_args=connect_args,
        **pool_kwargs,
    )


async_engine = _build_engine()

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables from ORM metadata (dev only -- production uses Alembic)."""
    # Import all models so their metadata is registered on Base
    import app.models  # noqa: F401
    from app.db.base import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
