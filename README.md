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


---

## Type C Autonomous Batch Simulator & MinIO Object Storage (F5 Requirement)

Fulfills requirement **F5** by continuously generating simulated carrier tracking files (CSV / Excel XLSX) with controlled defect injection every 4 hours and depositing them into an S3-compatible Object Storage (MinIO) backed by persistent Docker volumes and automated retention cleanup.

### Architecture Overview

- **3 Carriers Simulated**:
  - **Carrier 1 (TransExpress Logistics)**: English technical CSV (`waybill_no`, `status_code`, `event_time`, `hub_city`).
  - **Carrier 2 (Rápido Andino)**: Operational Spanish Excel XLSX (`numero_guia`, `estado_operativo`, `fecha_hora_evento`, `sucursal`).
  - **Carrier 3 (Logística 360)**: Numeric code CSV (`tracking_code`, `code`, `event_date`, `center_id`).
- **Defect Injection Engine**: Automatically introduces nonexistent waybills, out-of-sequence events, mixed date formats, summary footers, and duplicates.
- **MinIO Object Storage**: S3-compatible storage engine (`pgsty/silo`) running on port `9000` (API) and `9001` (Web Console).
- **Automated Retention Policy**: Objects older than `RETENTION_DAYS` (default: 3 days) are purged during each 4-hour cycle to prevent storage costs and unbounded disk consumption.
- **Persistent Volume**: Backed by named volume `cargaexpress_type_c_minio_data`.

### Document Extraction Methods

Downstream consumers, data pipelines, and operators can extract generated carrier files via four production-ready methods:

1. **HTTPS Unified Gateway (Zero-Cost SSL + Domain)**:
   Accessible via public HTTPS with valid Let's Encrypt certificates:
   - **Carrier 1 (TransExpress Logistics - CSV)**:
     - Swagger UI: [https://cargaexpress-simulator-b.mooo.com/carrier-1/docs](https://cargaexpress-simulator-b.mooo.com/carrier-1/docs)
     - Direct CSV Download: [https://cargaexpress-simulator-b.mooo.com/carrier-1/download](https://cargaexpress-simulator-b.mooo.com/carrier-1/download)
     - JSON Events: [https://cargaexpress-simulator-b.mooo.com/carrier-1/events](https://cargaexpress-simulator-b.mooo.com/carrier-1/events)
   - **Carrier 2 (Rápido Andino - Excel XLSX)**:
     - Swagger UI: [https://cargaexpress-simulator-b.mooo.com/carrier-2/docs](https://cargaexpress-simulator-b.mooo.com/carrier-2/docs)
     - Direct XLSX Download: [https://cargaexpress-simulator-b.mooo.com/carrier-2/download](https://cargaexpress-simulator-b.mooo.com/carrier-2/download)
     - JSON Events: [https://cargaexpress-simulator-b.mooo.com/carrier-2/events](https://cargaexpress-simulator-b.mooo.com/carrier-2/events)
   - **Carrier 3 (Logística 360 - CSV Numeric)**:
     - Swagger UI: [https://cargaexpress-simulator-b.mooo.com/carrier-3/docs](https://cargaexpress-simulator-b.mooo.com/carrier-3/docs)
     - Direct CSV Download: [https://cargaexpress-simulator-b.mooo.com/carrier-3/download](https://cargaexpress-simulator-b.mooo.com/carrier-3/download)
     - JSON Events: [https://cargaexpress-simulator-b.mooo.com/carrier-3/events](https://cargaexpress-simulator-b.mooo.com/carrier-3/events)

2. **Dedicated Carrier Direct Ports (8005, 8006, 8007)**:
   Directly hit each transportadora on its dedicated TCP port:
   - Carrier 1: `http://<SERVER_IP>:8005/docs` (and `/download`, `/events`)
   - Carrier 2: `http://<SERVER_IP>:8006/docs` (and `/download`, `/events`)
   - Carrier 3: `http://<SERVER_IP>:8007/docs` (and `/download`, `/events`)

3. **Web Console UI (MinIO Object Storage Browser)**:
   - Web Console: [https://cargaexpress-simulator-b.mooo.com/minio/](https://cargaexpress-simulator-b.mooo.com/minio/) or `http://<SERVER_IP>:9001`
   - Credentials: User `cargaexpress_admin` / Password `cargaexpress_minio_secret_123`
   - Action: Navigate to bucket `type-c-carriers`, browse folders (`carrier_1/`, `carrier_2/`, `carrier_3/`), and download files with 1 click.

4. **Standard S3 Protocol / CLI / SDK**:
   - Access: `http://<SERVER_IP>:9000` (or internal Docker network `http://minio:9000`)
   - Example Command:
     ```bash
     aws --endpoint-url http://3.129.10.158:9000 s3 cp s3://type-c-carriers/carrier_1/latest.csv ./downloads/
     ```
   - Python `boto3` Extraction:
     ```python
     import boto3
     s3 = boto3.client(
         "s3",
         endpoint_url="http://3.129.10.158:9000",
         aws_access_key_id="cargaexpress_admin",
         aws_secret_access_key="cargaexpress_minio_secret_123",
     )
     s3.download_file("type-c-carriers", "carrier_1/latest.csv", "carrier_1.csv")
     ```

### Quick Start with Docker Compose

```bash
cp .env.example .env
docker compose up -d
```
