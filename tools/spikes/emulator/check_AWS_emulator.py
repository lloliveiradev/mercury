"""
Checks Assumptions:
- A6: AWS Emulator serves S3 to boto3, Dagster and ClickHouse s3() with large Parquet files

Evidence:
- AWS_emulator.json
"""

from __future__ import annotations

import argparse
import dagster as dg
import io
import json
import pandas as pd
import sys
import time

from dagster_aws.s3 import S3PickleIOManager
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _aws import s3, BUCKET, get_emulator_access, _s3
from _clickhouse import ClickHouse
from _utils import (
    INMET_WEATHER_DIR,
    OUTPUT_DIR,
    STG_DATA_DIR,
    _size,
    _duration,
    _peak_memory,
)

PARQUET_PATH = "raw/brazil/INMET/weather"
TEXT_COLUMNS = {"Data", "Hora UTC"}
NOTES = []


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


def create_and_check_bucket() -> bool:
    try:
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key="hello.txt", Body=b"Hi from the emulator")
        s3.get_object(Bucket=BUCKET, Key="hello.txt")
        return True
    except Exception as e:
        NOTES.append(f"Error creating bucket: {e}")
        return False


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
        df = df.assign(**{"YEAR": int(year)})

        return df
    except Exception as e:
        NOTES.append(f"ERROR: Error formatting INMET file {f}: {e}")
        return None


def _s3_put_object(path: str, body: bytes) -> Optional[dict]:
    try:
        started_at = time.monotonic()
        s3.put_object(Bucket=BUCKET, Key=path, Body=body)
        return {
            "path": path,
            "size": _size(len(body)),
            "time_to_upload": _duration(time.monotonic() - started_at),
        }
    except Exception as e:
        NOTES.append(f"ERROR: Error uploading object {path} to s3: {e}")
        return None


def upload_parquets_to_s3(force: bool = False) -> list[dict]:
    results: list[dict] = []
    try:
        INMET_STG_DIR = STG_DATA_DIR / "INMET" / "weather"
        INMET_STG_DIR.mkdir(parents=True, exist_ok=True)
        for d in INMET_WEATHER_DIR.iterdir():
            if not d.is_dir():
                continue

            if force or not (INMET_STG_DIR / f"{d.name}.parquet").exists():
                files: list[pd.DataFrame] = []
                for f in d.glob("*.csv"):
                    if not f.is_file() or f.suffix != ".csv":
                        continue

                    df = format_inmet_file(f, f.parent.name)
                    if df is None:
                        continue
                    files.append(df)

                if len(files) == 0:
                    continue

                df = pd.concat((f for f in files), ignore_index=True)
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False)

                with open(INMET_STG_DIR / f"{d.name}.parquet", "wb") as f:
                    f.write(buffer.getvalue())
            else:
                buffer = io.BytesIO(
                    open(INMET_STG_DIR / f"{d.name}.parquet", "rb").read()
                )

            result = _s3_put_object(
                f"{PARQUET_PATH}/{d.name}.parquet",
                buffer.getvalue(),
            )
            if result is None:
                continue
            results.append(result)
        return results
    except Exception as e:
        NOTES.append(f"ERROR: Error uploading parquets to s3: {e}")
        return results


def _ch_query_s3_test_file(ch: ClickHouse, access: dict) -> Optional[dict]:
    try:
        if not (
            s3.head_object(Bucket=BUCKET, Key="hello.txt").get("ContentLength") == 0
        ):
            s3.put_object(Bucket=BUCKET, Key="hello.txt", Body=b"Hi from the emulator")

        started_at = time.monotonic()
        result = ch.query(f"""
            SELECT * FROM s3(
                '{access['url']}/{BUCKET}/hello.txt',
                '{access['access_key']}',
                '{access['secret_key']}',
                'Text'
            )
        """)
        if len(result) == 0:
            NOTES.append("WARN: ClickHouse read 0 rows from hello.txt with s3()")
            return None
        return {
            "path": f"/{BUCKET}/hello.txt",
            "records": len(result),
            "time_to_read": _duration(time.monotonic() - started_at),
        }
    except Exception as e:
        NOTES.append(f"ERROR: Error querying s3 test file: {e}")
        return None


def _ch_query_s3(
    ch: ClickHouse, access: dict, path: str, file_type: str
) -> Optional[dict]:
    try:
        started_at = time.monotonic()
        result = ch.query(f"""
            SELECT * FROM s3(
                '{access['url']}/{BUCKET}/{path}',
                '{access['access_key']}',
                '{access['secret_key']}',
                '{file_type}'
            )
        """)
        if len(result) == 0:
            NOTES.append(f"WARN: ClickHouse read 0 rows from {path} with s3()")
            return None
        return {
            "path": path,
            "records": len(result),
            "time_to_read": _duration(time.monotonic() - started_at),
        }
    except Exception as e:
        NOTES.append(f"ERROR: Error querying s3: {e}")
        return None


def ch_read_parquets_from_s3(paths: list[str]) -> list[dict]:
    ch = ClickHouse()
    access = get_emulator_access()
    results: list[dict] = []
    try:
        if not paths or len(paths) == 0:
            result = _ch_query_s3_test_file(ch, access)
            if result is None:
                return []
            return [result]

        for path in paths:
            result = _ch_query_s3(ch, access, path, "Parquet")
            if result is None:
                continue
            results.append(result)

        return results
    except Exception as e:
        NOTES.append(f"ERROR: ClickHouse s3() read failed: {e}")
        return []


@dg.asset
def spike_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "municipality_id": [3550308, 3550308, 3550308, 3304557],
            "uf": ["SP", "SP", "SP", "RJ"],
            "accidents": [1, 2, 1, 1],
            "precipitation_mm": [0.0, 1.4, 1.4, None],
        }
    )


@dg.asset
def spike_frame_roundtrip(spike_frame: pd.DataFrame) -> Optional[int]:
    if len(spike_frame) != 4 or not all(spike_frame["accidents"].isin([1, 2])):
        NOTES.append("S3 IO manager returned different data")
        return None
    return len(spike_frame)


def check_dagster_s3_io() -> bool:
    result = dg.materialize(
        [spike_frame, spike_frame_roundtrip],
        resources={
            "io_manager": S3PickleIOManager(
                s3_resource=_s3(),
                s3_bucket=BUCKET,
                s3_prefix="spike/dagster-io",
            )
        },
    )
    return result.success


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "serves_s3_to_boto3": False,
        "serves_s3_to_clickhouse": False,
        "serves_s3_to_dagster": False,
        "fits_large_parquet_files": False,
        "uploaded_parquets": None,
        "read_parquets": None,
        "notes": [],
    }

    checks["serves_s3_to_boto3"] = create_and_check_bucket()

    uploaded = upload_parquets_to_s3(args.force)
    if len(uploaded) > 0:
        checks["uploaded_parquets"] = uploaded
        checks["fits_large_parquet_files"] = True
    else:
        NOTES.append(
            "WARN: S3 on emulator limits put_object to 16 MiB, a bucket to 64 MiB, "
            "and all buckets together to 128 MiB, see issues #67 and #73: "
            "https://github.com/aws/aws-emulator/issues/"
        )

    read = ch_read_parquets_from_s3([p["path"] for p in uploaded])
    if len(read) > 0:
        checks["serves_s3_to_clickhouse"] = True
        checks["read_parquets"] = read

    checks["serves_s3_to_dagster"] = check_dagster_s3_io()
    checks["notes"] = NOTES
    checks["time_to_process"] = _duration(time.monotonic() - started)
    checks["peak_memory"] = _peak_memory()

    with open(OUTPUT_DIR / "AWS_emulator.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
