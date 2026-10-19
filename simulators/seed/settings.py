import os
from dataclasses import dataclass
from datetime import date

DEFAULT_START_DATE = date(2026, 10, 1)
PROFILE_DEFAULTS = {"dev": (3, 200), "full": (7, 15_000)}


@dataclass(frozen=True)
class SeedSettings:
    profile: str
    days: int
    orders_per_day: int
    start_date: date
    random_seed: int
    allow_remote: bool
    app_env: str

    @classmethod
    def from_env(cls) -> "SeedSettings":
        profile = os.getenv("SEED_PROFILE", "dev").strip().lower()
        if profile not in PROFILE_DEFAULTS:
            raise ValueError("SEED_PROFILE must be 'dev' or 'full'.")

        default_days, default_orders = PROFILE_DEFAULTS[profile]
        days = _positive_int("SEED_DAYS", default_days)
        orders_per_day = _positive_int("SEED_ORDERS_PER_DAY", default_orders)

        start_date_raw = os.getenv("SEED_START_DATE", DEFAULT_START_DATE.isoformat())
        try:
            start_date = date.fromisoformat(start_date_raw)
        except ValueError as exc:
            raise ValueError("SEED_START_DATE must be an ISO date (YYYY-MM-DD).") from exc

        random_seed_raw = os.getenv("SEED_RANDOM_SEED", "42")
        try:
            random_seed = int(random_seed_raw)
        except ValueError as exc:
            raise ValueError("SEED_RANDOM_SEED must be an integer.") from exc

        allow_remote_raw = os.getenv("SEED_ALLOW_REMOTE", "false").strip().lower()
        if allow_remote_raw not in {"true", "false"}:
            raise ValueError("SEED_ALLOW_REMOTE must be 'true' or 'false'.")

        return cls(
            profile=profile,
            days=days,
            orders_per_day=orders_per_day,
            start_date=start_date,
            random_seed=random_seed,
            allow_remote=allow_remote_raw == "true",
            app_env=os.getenv("APP_ENV", "development").strip(),
        )


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value
