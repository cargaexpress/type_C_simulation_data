from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession

SEED_PREFIX = "SEED-"
LOCAL_DATABASE_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


class SeedGuardError(ValueError):
    pass


def guard_app_environment(app_env: str) -> None:
    if app_env.strip().lower() in {"prod", "production"}:
        raise SeedGuardError("Seed refused: APP_ENV must not be prod or production.")


def guard_database_host(database_url: str, allow_remote: bool) -> None:
    try:
        host = make_url(database_url).host
    except (ArgumentError, TypeError, ValueError) as exc:
        raise SeedGuardError("Seed refused: DATABASE_URL is invalid.") from exc
    if (host is None or host.lower() not in LOCAL_DATABASE_HOSTS) and not allow_remote:
        raise SeedGuardError("Seed refused: remote database host requires SEED_ALLOW_REMOTE=true.")


async def guard_existing_orders(session: AsyncSession) -> None:
    from app.models.order import Order

    existing_order_id = await session.scalar(
        select(Order.order_id).where(~Order.brand_order_ref.startswith(SEED_PREFIX)).limit(1)
    )
    if existing_order_id is not None:
        raise SeedGuardError("Seed refused: the database contains orders without the SEED- prefix.")


async def run_guards(
    session: AsyncSession,
    app_env: str,
    database_url: str,
    allow_remote: bool,
) -> None:
    guard_app_environment(app_env)
    guard_database_host(database_url, allow_remote)
    await guard_existing_orders(session)
