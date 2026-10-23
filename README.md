# Type C Simulation Data & Carrier Defect Generator

Standalone module and CLI for generating synthetic tracking and status files for Type C batch carriers with configurable defect injection, plus idempotent database seeding for WMS integration.

## Features

### 1. Type C Carrier File Simulator (`simulators.type_c`)
- Supports simulated carriers with custom layouts and formats (CSV, XLSX).
- Deterministic byte-to-byte reproducibility using random seeds.
- Anomaly / Defect injection engine:
  - Header line corruption / noise
  - Repeated headers mid-file
  - Null / missing mandatory columns
  - Unmapped status codes
  - Trailing totals/summary rows
  - Whitespace and encoding variations
- CLI interface (`type-c-sim` or `python -m simulators.type_c.cli`).

### 2. WMS Database Seeder (`simulators.seed`)
- Idempotent initialization of reference data:
  - Shipment Types
  - Distribution Centers (DCs)
  - Commercial Brands
  - Carriers & State Mappings
  - Orders, Order Lines, Recipients, and Shipping Labels
- Strict environment guards to prevent accidental execution against production databases.

---

## Installation

Using `uv` (recommended):
```bash
uv sync
```

Or using standard `pip`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Usage

### Type C Simulator CLI

Run with default parameters (Carrier 1, 100 rows, 10% error rate, seed 42):
```bash
uv run type-c-sim
```

Or via python module:
```bash
uv run python -m simulators.type_c.cli --carrier 2 --rows 500 --error-rate 0.05 --seed 123 --format csv
```

Available CLI Flags:
- `--seed <int>`: Random seed for deterministic reproducibility (default: 42).
- `--carrier <int>` or `--transportadora <int>`: Carrier identifier (1 to 3, default: 1).
- `--output-dir <path>`: Destination directory for generated files (default: `./data/type_c`).
- `--rows <int>`: Number of base rows to generate (default: 100).
- `--error-rate <float>`: Anomaly injection rate between 0.0 and 1.0 (default: 0.1).
- `--format <csv|xlsx>`: Force output format (defaults to carrier's native format).

### WMS Seeder

Configure environment variables and run:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/cargaexpress"
export SEED_PROFILE="dev" # or "full"
uv run python -m simulators.seed
```

---

## Running Tests

Run the full test suite with pytest:
```bash
uv run pytest -v
```

---

## Docker Multi-Stage Build & Optimization (RIWI-168)

The WMS Seeder and Type C simulator container (simulators/seed/Dockerfile) implements a hardened multi-stage build:
1. **Builder Stage**: Uses ghcr.io/astral-sh/uv:0.11.7 on python:3.12-slim to resolve dependencies from pyproject.toml and uv.lock with --frozen --no-dev. Virtualenv is compiled ahead-of-time with bytecode optimization (UV_COMPILE_BYTECODE=1).
2. **Runtime Stage**: Copies solely the compiled /app/.venv and source directories (pp, simulators) into a clean python:3.12-slim image.
3. **Security Hardening**: Executes under non-root unprivileged user seeduser (uid=1000, gid=1000). Package managers, dev tools, and compilers are stripped from the final runtime image.

### Build & Verification Commands

`ash
# Build the production seed image
docker build -f simulators/seed/Dockerfile -t cargaexpress-seed:latest .

# Run via Compose
docker compose -f docker-compose.seed.yml build

# Verify non-root user
docker run --rm cargaexpress-seed:latest whoami
# Output: seeduser

# Verify UID/GID
docker run --rm cargaexpress-seed:latest id
# Output: uid=1000(seeduser) gid=1000(seeduser) groups=1000(seeduser)

# Verify absence of build toolchains
docker run --rm cargaexpress-seed:latest which uv
# Output: (exit code 1, not found)
`

### Benchmarking & Size Optimization

| Metric | Single-Stage Baseline | Multi-Stage Optimized | Reduction |
| :--- | :--- | :--- | :--- |
| **Uncompressed Disk Size** | 430 MB | **257 MB** | **-173 MB (-40.2%)** |
| **Compressed Transfer Size** | ~125 MB | **60.7 MB** | **-64.3 MB (-51.4%)** |
| **Build Tools & Wheels** | Present (uv, dev caches) | **Removed** (only runtime virtualenv) | 100% eliminated |
| **Execution User** | root | **seeduser (UID 1000)** | Hardened |
