# Disposable order seed

This optional Compose override creates deterministic sample brands, distribution centers, shipment types, and orders with recipients, lines, and labels. It does not create carriers or alter backend behavior.

Run from the repository root:

```powershell
docker compose -f docker-compose.yml -f docker-compose.seed.yml up --build seed
docker compose -f docker-compose.yml -f docker-compose.seed.yml down -v
```

| Variable | Default | Purpose |
|---|---|---|
| `SEED_PROFILE` | `dev` | `dev` is 3 days x 200 orders; `full` is 7 days x 15000. |
| `SEED_DAYS` | Profile value | Positive day count override. |
| `SEED_ORDERS_PER_DAY` | Profile value | Positive daily order count override. |
| `SEED_START_DATE` | `2026-10-01` | First date, in ISO format. |
| `SEED_RANDOM_SEED` | `42` | Integer seed for reproducible data. |
| `SEED_ALLOW_REMOTE` | `false` | Explicitly permit a non-local database host. |
| `APP_ENV` | `development` | Production environments are refused. |
| `SEED_BRAND_KEY_1..3` | Required | API keys for seeded brand IDs 1, 2, and 3 on a fresh database. |

Call the API using the matching brand key, for example:

```powershell
curl.exe -H "X-API-Key: $env:SEED_BRAND_KEY_1" http://localhost:8000/api/v1/orders
```

The seed refuses production `APP_ENV`, remote hosts unless explicitly allowed, and databases containing non-seed orders. It also requires the migrations' simulated carriers.

To remove this feature, delete `docker-compose.seed.yml`, `simulators/seed/settings.py`, `simulators/seed/guards.py`, `simulators/seed/orders_seed.py`, `simulators/seed/__main__.py`, `simulators/seed/Dockerfile`, `simulators/seed/README.md`, and `tests/test_orders_seed.py`. A real database only requires setting `DATABASE_URL`; do not include the seed override file.
