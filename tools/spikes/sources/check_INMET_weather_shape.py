"""
Checks Assumptions:
- A4:   INMET catalogue has station coordinates and the yearly files are parseable
- A5:   INMET provides precipitation hourly for most stations
- A11:  INMET hours are UTC and PRF times are local time

Evidence:
- INMET_weather_shape.json
"""

from __future__ import annotations

import json
import pandas as pd
import sys
import time

from jsonschema.validators import validator_for
from jsonschema.exceptions import ValidationError

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _inmet import (
    INMET_WEATHER_DIR,
    INMET_WEATHER_SCHEMA,
    _measurements,
    format_station_data,
)
from _utils import _duration, _peak_memory, _rate, OUTPUT_DIR

NOTES = []
VALIDATOR = validator_for(INMET_WEATHER_SCHEMA)(INMET_WEATHER_SCHEMA)
SCHEMA_SAMPLE_ROWS = 48
PRECIPITATION = "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)"


def main() -> int:
    if not INMET_WEATHER_DIR.is_dir():
        print("error: INMET weather raw directory not found", file=sys.stderr)
        return 1

    started = time.time()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "total_files": 0,
        "total_records": 0,
        "valid_station_files": 0,
        "schema_sampled_rows": 0,
        "schema_validated_rows": 0,
        "no_precipitation_rows": 0,
        "no_precipitation_rate": 0,
        "no_precipitation_files": 0,
        "mostly_no_precipitation_files": 0,
        "measured_by_hour_files": 0,
        "distinct_headers": 0,
        "by_year": {},
        "invalid_schema_records": [],
        "notes": [],
    }

    headers = set()

    for f in sorted(INMET_WEATHER_DIR.glob("*/*.csv")):
        checks["total_files"] += 1
        year = checks["by_year"].setdefault(
            f.parent.name,
            {
                "files": 0,
                "records": 0,
                "no_precipitation_rows": 0,
                "no_precipitation_files": 0,
                "mostly_no_precipitation_files": 0,
                "measured_by_hour_files": 0,
            },
        )
        year["files"] += 1
        md = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            header=None,
            nrows=8,
            names=["key", "value"],
        )
        if md.empty:
            continue
        fmt_md = format_station_data(md.to_dict(orient="records"))
        if not fmt_md:
            continue
        checks["valid_station_files"] += 1

        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            decimal=",",
            thousands=".",
            skiprows=8,
            keep_default_na=False,
        )
        if df.empty:
            continue
        df = _measurements(df)
        headers.add(tuple(df.columns))
        checks["total_records"] += len(df)
        year["records"] += len(df)
        step = max(1, len(df) // SCHEMA_SAMPLE_ROWS)
        rows = (
            df.iloc[::step]
            .astype(object)
            .where(df.iloc[::step].notna(), None)
            .to_dict(orient="records")
        )
        checks["schema_sampled_rows"] += len(rows)
        for r in rows:
            try:
                VALIDATOR.validate(r)
                checks["schema_validated_rows"] += 1
            except ValidationError as e:
                field = (
                    ".".join(str(p) for p in e.absolute_path)
                    or "Invalid weather data structure"
                )
                checks["invalid_schema_records"].append(
                    {
                        "record": f"{f.parent.name}/{f.name}:{r['Data']} {r['Hora UTC']}",
                        "field": field,
                        "message": str(e.message),
                    }
                )
                continue
        stamps = pd.to_datetime(
            df["Data"].astype(str) + " " + df["Hora UTC"].astype(str),
            format="%Y/%m/%d %H%M UTC",
            errors="coerce",
        )
        steps = stamps.diff().dropna()
        if stamps.notna().all() and (steps == pd.Timedelta(hours=1)).all():
            checks["measured_by_hour_files"] += 1
            year["measured_by_hour_files"] += 1

        missing = df[PRECIPITATION].isnull()
        checks["no_precipitation_rows"] += int(missing.sum())
        year["no_precipitation_rows"] += int(missing.sum())
        if missing.all():
            checks["no_precipitation_files"] += 1
            year["no_precipitation_files"] += 1
        elif missing.mean() > 0.5:
            checks["mostly_no_precipitation_files"] += 1
            year["mostly_no_precipitation_files"] += 1

    for year in checks["by_year"].values():
        year["no_precipitation_rate"] = _rate(
            year["no_precipitation_rows"], year["records"], 4
        )
    checks["distinct_headers"] = len(headers)
    checks["no_precipitation_rate"] = _rate(
        checks["no_precipitation_rows"], checks["total_records"], 4
    )
    checks["time_to_process"] = _duration(time.time() - started)
    checks["peak_memory"] = _peak_memory()
    checks["notes"] = NOTES

    with open(OUTPUT_DIR / "INMET_weather_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
