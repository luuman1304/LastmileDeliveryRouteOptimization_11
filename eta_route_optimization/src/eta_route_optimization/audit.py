from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
from typing import Any

LADE_REQUIRED_COLUMNS = {
    "order_id",
    "region_id",
    "city",
    "courier_id",
    "lng",
    "lat",
    "aoi_id",
    "aoi_type",
    "accept_time",
    "delivery_time",
    "ds",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

AMAZON_REQUIRED_FILES = {
    "route_data.json",
    "package_data.json",
    "travel_times.json",
    "actual_sequences.json",
}


def audit_lade(pattern: str) -> dict[str, Any]:
    """Kiểm tra schema và số dòng mà không thay đổi raw data."""

    import pandas as pd
    import pyarrow.parquet as pq

    files = [Path(path) for path in sorted(glob.glob(pattern))]
    if not files:
        raise FileNotFoundError(f"No LaDe-D files matched: {pattern}")

    records: list[dict[str, Any]] = []
    for path in files:
        parquet = pq.ParquetFile(path)
        columns = set(parquet.schema_arrow.names)
        missing = sorted(LADE_REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"{path} is missing required columns: {missing}")
        columns_to_check = sorted(
            LADE_REQUIRED_COLUMNS
            | {"accept_gps_lng", "accept_gps_lat", "delivery_gps_lng", "delivery_gps_lat"}
        )
        frame = pd.read_parquet(path, columns=columns_to_check)
        accept = pd.to_datetime(
            "2022-" + frame["accept_time"].astype(str),
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )
        delivery = pd.to_datetime(
            "2022-" + frame["delivery_time"].astype(str),
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )
        records.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows": parquet.metadata.num_rows,
                "row_groups": parquet.metadata.num_row_groups,
                "columns": parquet.schema_arrow.names,
                "city_counts": {str(k): int(v) for k, v in frame["city"].value_counts().items()},
                "duplicate_order_ids": int(frame["order_id"].duplicated().sum()),
                "negative_accept_to_delivery": int((delivery < accept).sum()),
                "missing_stop_coordinate_pairs": int((frame["lng"].isna() | frame["lat"].isna()).sum()),
                "missing_accept_gps_pairs": int(
                    (frame["accept_gps_lng"].isna() | frame["accept_gps_lat"].isna()).sum()
                ),
                "missing_delivery_gps_pairs": int(
                    (frame["delivery_gps_lng"].isna() | frame["delivery_gps_lat"].isna()).sum()
                ),
                "null_counts": {str(k): int(v) for k, v in frame.isna().sum().items()},
            }
        )
    return {
        "dataset": "LaDe-D",
        "files": records,
        "total_rows": sum(record["rows"] for record in records),
    }


def audit_amazon(root: Path) -> dict[str, Any]:
    """Kiểm tra sự hiện diện của các sidecar bắt buộc của Amazon."""

    missing = sorted(name for name in AMAZON_REQUIRED_FILES if not (root / name).is_file())
    if missing:
        raise FileNotFoundError(f"Amazon training root is missing files: {missing}")
    return {
        "dataset": "Amazon Last Mile Routing Research Challenge",
        "root": str(root),
        "files": {
            name: {
                "bytes": (root / name).stat().st_size,
                "sha256": sha256(root / name),
            }
            for name in sorted(AMAZON_REQUIRED_FILES)
        },
        "semantic_counts": (
            "See artifacts/data_audit_snapshot_2026-11-16.json. The experiment loader checks route, "
            "stop, sequence, package and travel-matrix key consistency before evaluation."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit the two research datasets.")
    parser.add_argument("--lade-glob", required=True)
    parser.add_argument("--amazon-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = {
        "lade": audit_lade(args.lade_glob),
        "amazon": audit_amazon(args.amazon_root),
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
