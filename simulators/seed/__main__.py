import asyncio
import logging
import os

from sqlalchemy import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from simulators.seed.guards import (
    SeedGuardError,
    guard_app_environment,
    guard_database_host,
)
from simulators.seed.settings import SeedSettings

LOGGER = logging.getLogger("simulators.seed")


async def _run(settings: SeedSettings, database_url: str) -> None:
    from simulators.seed.orders_seed import run_seed

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await run_seed(engine, settings, database_url)
    finally:
        await engine.dispose()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings = SeedSettings.from_env()
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required.")
    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 1
    try:
        host = make_url(database_url).host or "(unknown)"
    except (ArgumentError, ValueError):
        LOGGER.error("DATABASE_URL is invalid.")
        return 1

    try:
        guard_app_environment(settings.app_env)
        guard_database_host(database_url, settings.allow_remote)
    except SeedGuardError as exc:
        LOGGER.error("%s", exc)
        return 1

    LOGGER.info("seed database host=%s", host)
    try:
        asyncio.run(_run(settings, database_url))
    except (SeedGuardError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except SQLAlchemyError:
        LOGGER.error("Database operation failed; check DATABASE_URL and database availability.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
