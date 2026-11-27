"""
Checks Assumptions:
- A1: Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)

Evidence:
- INMET_weather_stats.json
"""

from __future__ import annotations

import json
import pandas as pd
import sys
import time

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _inmet import INMET_WEATHER_DIR
from _utils import _size, _duration, _peak_memory, OUTPUT_DIR


def main() -> int:
    if not INMET_WEATHER_DIR.is_dir():
        print("error: INMET weather raw directory not found", file=sys.stderr)
        return 1

    started = time.monotonic()
    total_files = 0
    total_records = 0
    total_size = 0
    stations_by_year = {}

    for f in sorted(INMET_WEATHER_DIR.glob("*/*.csv")):
        year = f.parent.name
        stations_by_year.setdefault(year, 0)
        total_files += 1
        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            decimal=",",
            thousands=".",
            skiprows=8,
        )
        total_records += len(df.to_dict(orient="records"))
        total_size += f.stat().st_size
        stations_by_year[year] += 1

    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": _duration(time.monotonic() - started),
        "peak_memory": _peak_memory(),
        "total_files": total_files,
        "total_records": total_records,
        "total_size": _size(total_size),
        "stations_by_year": stations_by_year,
        "notes": [],
    }
    if len(set(stations_by_year.values())) != 1:
        checks["notes"].append(
            "INFO: The years do not have the same number of stations. It may indicate "
            "that some stations were not operational during some years, and some may "
            "have been added later. Or even that some stations did not reported data "
            "to INMET (which is very unlikely, but possible)."
        )

    with open(OUTPUT_DIR / "INMET_weather_stats.json", "w") as f:
        json.dump(checks, f, indent=4)

    print("INMET weather stats:")
    print(json.dumps(checks, indent=4))


if __name__ == "__main__":
    sys.exit(main())
