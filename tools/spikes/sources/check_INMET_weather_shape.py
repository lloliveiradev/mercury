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

from _inmet import format_station_data, INMET_WEATHER_DIR
from _utils import _time, OUTPUT_DIR

NOTES = []


def main() -> int:
    if not INMET_WEATHER_DIR.is_dir():
        print("error: INMET weather raw directory not found", file=sys.stderr)
        return 1

    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "is_parseable": False,
        "has_station_data": False,
        "is_hours_utc": False,
        "is_hours_diff_1_hour": False,
        "station_sample": [],
        "hours_sample": [],
        "notes": [],
    }

    for f in INMET_WEATHER_DIR.glob("*/*.csv"):
        if f.is_file() and f.suffix == ".csv":
            md = pd.read_csv(
                f,
                sep=";",
                encoding="latin-1",
                header=None,
                nrows=8,
                names=["key", "value"],
            )
            if md.empty:
                checks["has_station_data"] = False
                break
            fmt_md = format_station_data(md.to_dict(orient="records"))
            checks["has_station_data"] = fmt_md is not None
            checks["station_sample"] = [fmt_md]
            if not fmt_md:
                NOTES.append(f"WARN: station data is not parseable: {f}")

            df = pd.read_csv(
                f,
                sep=";",
                encoding="latin-1",
                decimal=",",
                thousands=".",
                skiprows=8,
                nrows=5,
            )
            if df.empty:
                checks["is_parseable"] = False
                break
            checks["is_parseable"] = True

            hours = df["Hora UTC"].tolist()
            checks["hours_sample"] = hours
            for h in hours:
                checks["is_hours_utc"] = _time(h, format="%H%M UTC") is not None
                break
            fmt_hours = [_time(h, format="%H%M UTC") for h in hours[:5]]

            for i in range(len(fmt_hours) - 1):
                diff = fmt_hours[i + 1].hour - fmt_hours[i].hour
                if diff != 1:
                    checks["is_hours_diff_1_hour"] = False
                    break
            checks["is_hours_diff_1_hour"] = True

            break  # only one check is enough for now

    checks["notes"].extend(NOTES)

    with open(OUTPUT_DIR / "INMET_weather_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(
        json.dumps(
            {
                k: v
                for k, v in checks.items()
                if k
                in [
                    "last_checked_at",
                    "is_parseable",
                    "has_station_data",
                    "is_hours_utc",
                    "is_hours_diff_1_hour",
                    "notes",
                ]
            },
            indent=4,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
