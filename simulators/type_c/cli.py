"""CLI to execute Type C simulated carrier generator with defect injection."""

import argparse
import sys
from pathlib import Path

from simulators.type_c.catalogs import get_carrier_config
from simulators.type_c.generator import TypeCSimulator, compute_file_sha256


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Type C Batch Carrier File Simulator with Defect Injection (F5, Sec 5.2 and 5.3)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Fixed random seed to ensure exact reproducibility",
    )
    parser.add_argument(
        "--carrier",
        "--transportadora",
        dest="carrier",
        type=str,
        default="1",
        help="Carrier identifier (1 to 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/type_c",
        help="Path to output directory",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=100,
        help="Base number of rows/events to generate",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.1,
        help="Configurable anomaly injection rate (0.0 to 1.0)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default=None,
        choices=["csv", "xlsx", None],
        help="Output file format (defaults to carrier native format)",
    )

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        config = get_carrier_config(args.carrier)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    simulator = TypeCSimulator(
        carrier=config,
        seed=args.seed,
        error_rate=args.error_rate,
    )

    output_dir = Path(args.output_dir)
    generated_file = simulator.generate_file(
        output_dir=output_dir,
        num_rows=args.rows,
        file_format=args.format,
    )

    sha256_hash = compute_file_sha256(generated_file)

    print("=================================================================")
    print("TYPE C SIMULATOR - GENERATION COMPLETED SUCCESSFULLY")
    print("=================================================================")
    print(f" Carrier     : [{config.carrier_id}] {config.name} ({config.code})")
    print(f" Seed        : {args.seed}")
    print(f" Base rows   : {args.rows}")
    print(f" Error rate  : {args.error_rate * 100:.1f}%")
    print(f" Target file : {generated_file.resolve()}")
    print(f" SHA-256 Hash: {sha256_hash}")
    print("=================================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
