"""Data quality defect injection module for Type C carriers (Section 5.3).

Implements 5 types of deliberate anomalies:
1. Nonexistent shipping labels/waybills (outside WMS universe).
2. Out-of-sequence temporal events.
3. Mixed date formats (DD/MM/YYYY HH:MM vs MM/DD/YYYY HH:MM).
4. Junk rows and repeated headers (summary footer, intermediate headers).
5. Duplicate rows.
"""

import random
from copy import deepcopy
from datetime import datetime
from typing import Any


def inject_nonexistent_guides(
    rows: list[dict[str, Any]],
    tracking_col: str,
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Inject fictional waybill numbers that do not exist in the WMS."""
    if not rows or error_rate <= 0:
        return rows

    result = deepcopy(rows)
    target_count = max(1, int(len(result) * error_rate))
    indices_to_corrupt = rng.sample(range(len(result)), min(target_count, len(result)))

    for idx in indices_to_corrupt:
        fake_id = rng.randint(900000, 999999)
        result[idx][tracking_col] = f"FAKE_WAYBILL_{fake_id}"

    return result


def inject_out_of_sequence_events(
    rows: list[dict[str, Any]],
    tracking_col: str,
    status_col: str,
    timestamp_col: str,
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Generate out-of-sequence temporal events (e.g. delivered before transit or swapped timestamps)."""
    if not rows or error_rate <= 0:
        return rows

    result = deepcopy(rows)

    # Group indices by tracking_col
    guides_map: dict[str, list[int]] = {}
    for idx, row in enumerate(result):
        guide = str(row.get(tracking_col, ""))
        guides_map.setdefault(guide, []).append(idx)

    # Filter waybills with at least 2 events to swap temporally
    candidates = [indices for indices in guides_map.values() if len(indices) >= 2]
    if not candidates:
        return result

    target_count = max(1, int(len(candidates) * error_rate))
    selected_groups = rng.sample(candidates, min(target_count, len(candidates)))

    for group in selected_groups:
        # Pick two events in the group and swap their timestamps
        i, j = rng.sample(group, 2)
        ts_i = result[i][timestamp_col]
        ts_j = result[j][timestamp_col]
        result[i][timestamp_col] = ts_j
        result[j][timestamp_col] = ts_i

    return result


def inject_mixed_date_formats(
    rows: list[dict[str, Any]],
    timestamp_col: str,
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Interleave ambiguous date formats: DD/MM/YYYY HH:MM and MM/DD/YYYY HH:MM."""
    if not rows or error_rate <= 0:
        return rows

    result = deepcopy(rows)
    target_count = max(1, int(len(result) * error_rate))
    indices_to_corrupt = rng.sample(range(len(result)), min(target_count, len(result)))

    for idx in indices_to_corrupt:
        raw_val = result[idx].get(timestamp_col)
        # Parse datetime if standard format
        dt: datetime
        if isinstance(raw_val, datetime):
            dt = raw_val
        elif isinstance(raw_val, str):
            try:
                dt = datetime.fromisoformat(raw_val)
            except ValueError:
                continue
        else:
            continue

        # Randomly choose between DD/MM/YYYY and MM/DD/YYYY
        if rng.random() < 0.5:
            # European / Latin format
            result[idx][timestamp_col] = dt.strftime("%d/%m/%Y %H:%M")
        else:
            # Anglo-Saxon format
            result[idx][timestamp_col] = dt.strftime("%m/%d/%Y %H:%M")

    return result


def inject_duplicate_rows(
    rows: list[dict[str, Any]],
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Duplicate complete records within the events list."""
    if not rows or error_rate <= 0:
        return rows

    result = deepcopy(rows)
    target_count = max(1, int(len(rows) * error_rate))
    indices_to_duplicate = rng.sample(range(len(rows)), min(target_count, len(rows)))

    for idx in indices_to_duplicate:
        duplicate_item = deepcopy(rows[idx])
        # Insert at a random position
        insert_pos = rng.randint(0, len(result))
        result.insert(insert_pos, duplicate_item)

    return result


def inject_header_and_summary_rows(
    rows: list[dict[str, Any]],
    columns: list[str],
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Insert repeated intermediate header rows and footer/summary rows (e.g. TOTAL REGISTROS: N)."""
    if not rows or error_rate <= 0:
        return rows

    result = deepcopy(rows)

    # 1. Insertion of intermediate repeated headers
    num_headers = max(1, int(len(result) * (error_rate * 0.5)))
    for _ in range(num_headers):
        if len(result) < 3:
            break
        # Create a record where each column holds the column name itself
        repeated_header = {col: col for col in columns}
        insert_pos = rng.randint(1, len(result) - 1)
        result.insert(insert_pos, repeated_header)

    # 2. Insertion of footer rows with summary or totals
    summary_row = {col: "" for col in columns}
    primary_col = columns[0]
    secondary_col = columns[1] if len(columns) > 1 else primary_col
    summary_row[primary_col] = f"TOTAL REGISTROS: {len(rows)}"
    summary_row[secondary_col] = "--- FIN DE LOTE ---"

    result.append(summary_row)

    return result


def apply_all_corruptions(
    rows: list[dict[str, Any]],
    columns: list[str],
    tracking_col: str,
    status_col: str,
    timestamp_col: str,
    rng: random.Random,
    error_rate: float,
) -> list[dict[str, Any]]:
    """Apply the 5 deliberate anomaly types deterministically based on error_rate."""
    if error_rate <= 0.0:
        return rows

    # 1. Nonexistent waybills
    step1 = inject_nonexistent_guides(rows, tracking_col, rng, error_rate)

    # 2. Out-of-sequence events
    step2 = inject_out_of_sequence_events(
        step1, tracking_col, status_col, timestamp_col, rng, error_rate
    )

    # 3. Mixed date formats
    step3 = inject_mixed_date_formats(step2, timestamp_col, rng, error_rate)

    # 4. Duplicate rows
    step4 = inject_duplicate_rows(step3, rng, error_rate)

    # 5. Repeated headers and summary rows
    final_rows = inject_header_and_summary_rows(step4, columns, rng, error_rate)

    return final_rows
