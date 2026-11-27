"""
Checks Assumptions:
- A6: AWS Emulator serves S3 to boto3, Dagster and ClickHouse s3() with large Parquet files

Runs the same four checks against every S3 store in S3_SOURCES, so the result
says which store holds A6 and which does not.

Evidence:
- AWS_emulator.json
"""

from __future__ import annotations

import argparse
import dotenv
import json
import os
import pandas as pd
import sys
import time

from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _aws import (
    AWS_EMULATOR_STR,
    BUCKET,
    S3Source,
    S3_SOURCES,
    SEAWEEDFS_STR,
    check_s3_operations,
    get_s3_access,
    _s3_delete_object,
    _s3_put_object,
)
from _dagster import check_dagster_s3_io
from _clickhouse import ClickHouse
from _utils import (
    INMET_WEATHER_DIR,
    INMET_WEATHER_CH_STRUCT,
    OUTPUT_DIR,
    STG_DATA_DIR,
    _duration,
    _peak_memory,
    _size,
    _slugify,
)

dotenv.load_dotenv()

PARQUET_PATH = "raw/brazil/INMET/weather"
HELLO_PATH = "spike/clickhouse/hello.txt"
STORE_KEYS = {AWS_EMULATOR_STR: "aws_emulator", SEAWEEDFS_STR: "seaweedfs"}
KNOWN_LIMITS = {
    AWS_EMULATOR_STR: (
        "S3 on AWS Emulator limits put_object to 16 MiB, a bucket to 64 MiB, "
        "and all buckets together to 128 MiB, see issues #67 and #73: "
        "https://github.com/aws/aws-emulator/issues/"
    )
}
TEXT_COLUMNS = {"Data", "Hora UTC"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check AWS Emulator.")
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Forces persistence of parquet files in the staging directory",
    )
    return parser.parse_args(argv)


def _measurements(df: pd.DataFrame) -> pd.DataFrame:
    # INMET writes 0.4 as ",4". One such cell keeps the whole column as text,
    # and a later file parsed as float cannot share a Parquet column with it.
    out = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    for column in out.columns:
        if column in TEXT_COLUMNS or pd.api.types.is_numeric_dtype(out[column]):
            continue
        text = out[column].astype("string").str.strip()
        text = text.str.replace(r"^-,", "-0,", regex=True)
        text = text.str.replace(r"^,", "0,", regex=True)
        text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[column] = pd.to_numeric(text, errors="coerce")
    return out


def format_inmet_file(f: Path, year: str) -> Optional[pd.DataFrame]:
    try:
        md = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            header=None,
            nrows=8,
            names=["key", "value"],
        )
        if md.empty:
            return None
        fmt_md = {r["key"]: r["value"] for r in md.to_dict(orient="records")}

        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            decimal=",",
            thousands=".",
            skiprows=8,
            keep_default_na=False,
        )
        df = _measurements(df)

        df = df.assign(**fmt_md)
        df = df.assign(**{"year": int(year)})
        df = df.rename(columns={c: _slugify(c, "_") for c in df.columns})

        return df
    except Exception as e:
        print(f"ERROR: Error formatting INMET file {f}: {e}", file=sys.stderr)
        return None


def build_parquets(force: bool = False) -> list[dict]:
    """One Parquet per INMET year in the staging folder, built once and reused."""
    stg_dir = STG_DATA_DIR / "INMET" / "weather"
    stg_dir.mkdir(parents=True, exist_ok=True)
    parquets: list[dict] = []
    for d in sorted(INMET_WEATHER_DIR.iterdir()):
        if not d.is_dir():
            continue

        target = stg_dir / f"{d.name}.parquet"
        started_at = time.monotonic()
        built = force or not target.exists()
        if built:
            files = [format_inmet_file(f, d.name) for f in sorted(d.glob("*.csv"))]
            files = [df for df in files if df is not None]
            if len(files) == 0:
                continue
            pd.concat(files, ignore_index=True).to_parquet(target, index=False)
        parquets.append(
            {
                "year": d.name,
                "file": target,
                # Null when the staged file was reused instead of rebuilt.
                "time_to_build": (
                    _duration(time.monotonic() - started_at) if built else None
                ),
            }
        )
    return parquets


def check_boto3(source: S3Source, notes: list[str]) -> bool:
    try:
        return check_s3_operations(source)
    except Exception as e:
        notes.append(str(e))
        return False


def check_clickhouse(ch: ClickHouse, source: S3Source, notes: list[str]) -> bool:
    """ClickHouse s3() reads back a small text object written with boto3."""
    try:
        if (
            _s3_put_object(
                BUCKET, HELLO_PATH, b"Hi from ClickHouse", "text/plain", source
            )
            is None
        ):
            notes.append(f"ERROR: {source} refused {HELLO_PATH}")
            return False
        access = get_s3_access(source, host=os.getenv("SEAWEEDFS_CH_HOST"))
        rows = ch.query(f"""
            SELECT * FROM s3(
                '{access["url"]}/{BUCKET}/{HELLO_PATH}',
                '{access["access_key"]}',
                '{access["secret_key"]}',
                'LineAsString'
            )
        """)
        _s3_delete_object(BUCKET, HELLO_PATH, source)
        return len(rows) == 1
    except Exception as e:
        notes.append(f"ERROR: ClickHouse s3() could not read from {source}: {e}")
        return False


def read_parquet_with_clickhouse(
    ch: ClickHouse, source: S3Source, path: str, notes: list[str]
) -> Optional[dict]:
    """Every row and every column, on purpose: the time is the full read."""
    access = get_s3_access(source, host=os.getenv("SEAWEEDFS_CH_HOST"))
    try:
        started_at = time.monotonic()
        result = ch.query(f"""
            SELECT {", ".join([c.split(" ")[0] for c in INMET_WEATHER_CH_STRUCT])}
            FROM s3(
                '{access["url"]}/{BUCKET}/{path}',
                '{access["access_key"]}',
                '{access["secret_key"]}',
                'Parquet',
                '{", ".join(INMET_WEATHER_CH_STRUCT)}'
            )
        """)
        return {
            "records_read_by_clickhouse": len(result),
            "time_to_read_by_clickhouse": _duration(time.monotonic() - started_at),
        }
    except Exception as e:
        notes.append(f"ERROR: ClickHouse s3() could not read {path} on {source}: {e}")
        return None


def check_large_parquets(
    ch: ClickHouse, source: S3Source, parquets: list[dict], notes: list[str]
) -> list[dict]:
    results: list[dict] = []
    for parquet in parquets:
        path = f"{PARQUET_PATH}/{parquet['year']}.parquet"
        body = parquet["file"].read_bytes()
        result = {
            "path": f"{BUCKET}/{path}",
            "size": _size(len(body)),
            "time_to_build": parquet["time_to_build"],
            "uploaded": False,
            "time_to_upload": None,
            "records_read_by_clickhouse": None,
            "time_to_read_by_clickhouse": None,
        }
        results.append(result)
        # The helper prints the error and answers None when the store refuses.
        uploaded = _s3_put_object(
            BUCKET, path, body, "application/octet-stream", source
        )
        if uploaded is None:
            notes.append(f"ERROR: {source} refused {path} ({result['size']})")
            continue
        result["uploaded"] = True
        result["time_to_upload"] = uploaded["time_to_upload"]
        result.update(read_parquet_with_clickhouse(ch, source, path, notes) or {})
    return results


def check_store(source: S3Source, parquets: list[dict]) -> dict:
    """The four parts of A6 against one store."""
    notes: list[str] = []
    ch = ClickHouse()
    store = {
        "name": source,
        "holds_a6": False,
        "serves_s3_to_boto3": check_boto3(source, notes),
        "serves_s3_to_dagster": False,
        "serves_s3_to_clickhouse": False,
        "fits_large_parquet_files": False,
        "parquets": [],
        "notes": notes,
    }
    if not store["serves_s3_to_boto3"]:
        return store

    store["serves_s3_to_dagster"] = check_dagster_s3_io(source)
    store["serves_s3_to_clickhouse"] = check_clickhouse(ch, source, notes)
    store["parquets"] = check_large_parquets(ch, source, parquets, notes)
    store["fits_large_parquet_files"] = len(parquets) > 0 and all(
        p["uploaded"] and bool(p["records_read_by_clickhouse"])
        for p in store["parquets"]
    )
    if not store["fits_large_parquet_files"] and source in KNOWN_LIMITS:
        notes.append(f"WARN: {KNOWN_LIMITS[source]}")
    store["holds_a6"] = all(
        store[key]
        for key in (
            "serves_s3_to_boto3",
            "serves_s3_to_dagster",
            "serves_s3_to_clickhouse",
            "fits_large_parquet_files",
        )
    )
    return store


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "stores_holding_a6": [],
        "stores": {},
        "notes": [],
    }

    parquets = build_parquets(args.force)
    if len(parquets) == 0:
        checks["notes"].append("ERROR: no INMET year was found to build a Parquet from")

    for source in S3_SOURCES:
        store = check_store(source, parquets)
        checks["stores"][STORE_KEYS[source]] = store
        if store["holds_a6"]:
            checks["stores_holding_a6"].append(source)

    checks["time_to_process"] = _duration(time.monotonic() - started)
    checks["peak_memory"] = _peak_memory()

    with open(OUTPUT_DIR / "AWS_emulator.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
