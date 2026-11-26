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

from _inmet import INMET_WEATHER_DIR
from _utils import _size, _duration, OUTPUT_DIR


def main() -> int:
    if not INMET_WEATHER_DIR.is_dir():
        print("error: INMET weather raw directory not found", file=sys.stderr)
        return 1

    total_files = 0
    total_records = 0
    total_size = 0
    started = time.monotonic()

    for f in INMET_WEATHER_DIR.glob("*/*.csv"):
        if f.is_file() and f.suffix == ".csv":
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

    stats = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_count": total_files,
        "records_count": total_records,
        "size": _size(total_size),
        "duration": _duration(time.monotonic() - started),
    }

    with open(OUTPUT_DIR / "INMET_weather_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

    print("INMET weather stats:")
    print(json.dumps(stats, indent=4))


if __name__ == "__main__":
    sys.exit(main())
