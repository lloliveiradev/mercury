"""
Checks Assumptions:
- A1: Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)

Evidence:
- PRF_accidents_stats.json
"""

from __future__ import annotations

import json
import pandas as pd
import sys
import time

from pathlib import Path

from _utils import OUTPUT_DIR, _size, _duration

PRF_ACCIDENTS_RAW = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "brazil"
    / "PRF"
    / "accidents"
)


def main() -> int:
    if not PRF_ACCIDENTS_RAW.is_dir():
        print("error: PRF accidents raw directory not found", file=sys.stderr)
        return 1

    total_files = 0
    total_records = 0
    total_size = 0
    started = time.monotonic()

    for f in PRF_ACCIDENTS_RAW.glob("*/*.csv"):
        if f.is_file() and f.suffix == ".csv":
            total_files += 1
            df = pd.read_csv(
                f,
                sep=";",
                encoding="latin-1",
                decimal=",",
                thousands=".",
                keep_default_na=False,
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
    with open(OUTPUT_DIR / "PRF_accidents_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

    print(json.dumps(stats, indent=4))


if __name__ == "__main__":
    sys.exit(main())
