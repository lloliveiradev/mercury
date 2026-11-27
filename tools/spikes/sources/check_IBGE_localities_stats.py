"""
Checks Assumptions:
- A1: Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)

Evidence:
- IBGE_localities_stats.json
"""

from __future__ import annotations

import json
import sys
import time

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _ibge import IBGE_LOCALITIES_DIR
from _utils import CHECKS_TO_PRINT, OUTPUT_DIR, _size, _duration, _peak_memory


def main() -> int:
    if not IBGE_LOCALITIES_DIR.is_dir():
        print("ERROR: IBGE localities directory not found", file=sys.stderr)
        return 1

    started = time.monotonic()
    total_files = 0
    total_records = 0
    total_size = 0
    results: dict[str, dict] = {}

    for file in sorted(IBGE_LOCALITIES_DIR.glob("*.json")):
        size = file.stat().st_size
        total_files += 1
        total_size += size
        # Each file holds one JSON array, one item per locality.
        records = len(json.loads(file.read_bytes()))
        total_records += records
        results[file.name.removesuffix(".json")] = {
            "records": records,
            "size": _size(size),
        }

    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": _duration(time.monotonic() - started),
        "peak_memory": _peak_memory(),
        "total_files": len(results),
        "total_records": total_records,
        "total_size": _size(total_size),
        **results,
    }
    with open(OUTPUT_DIR / "IBGE_localities_stats.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(
        json.dumps(
            {k: v for k, v in checks.items() if k in CHECKS_TO_PRINT},
            indent=4,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
