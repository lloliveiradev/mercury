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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _prf import PRF_ACCIDENTS_DIR
from _utils import OUTPUT_DIR, _size, _duration, _peak_memory


def main() -> int:
    if not PRF_ACCIDENTS_DIR.is_dir():
        print("error: PRF accidents raw directory not found", file=sys.stderr)
        return 1

    started = time.monotonic()
    total_files = 0
    total_records = 0
    total_size = 0

    for f in sorted(PRF_ACCIDENTS_DIR.glob("*/*.csv")):
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
        "time_to_process": _duration(time.monotonic() - started),
        "peak_memory": _peak_memory(),
        "total_files": total_files,
        "total_records": total_records,
        "total_size": _size(total_size),
    }
    with open(OUTPUT_DIR / "PRF_accidents_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

    print(json.dumps(stats, indent=4))


if __name__ == "__main__":
    sys.exit(main())
