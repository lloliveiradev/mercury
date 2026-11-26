"""
Checks Assumptions:
- A1: Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)

Evidence:
- IBGE_meshes_stats.json
"""

from __future__ import annotations

import json
import sys
import time

from _ibge import count_mesh_coordinates, IBGE_DIR
from _utils import _size, _duration, OUTPUT_DIR

MESHES_DIR = IBGE_DIR / "meshes"


def main() -> int:
    if not MESHES_DIR.is_dir():
        print("error: meshes directory not found", file=sys.stderr)
        return 1

    total_files = 0
    total_size = 0
    started = time.monotonic()
    results: dict[str, dict] = {}

    for file in MESHES_DIR.glob("*.json"):
        if file.is_file() and (size := file.stat().st_size) > 0:
            total_files += 1
            total_size += size
            results[file.name.removesuffix(".json")] = {
                "coordinates_count": count_mesh_coordinates(file.read_bytes()) or 0,
                "size": _size(size),
                "duration": None,
            }

    stats = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_count": total_files,
        "records_count": total_files,
        "size": _size(total_size),
        "duration": _duration(time.monotonic() - started),
        **results,
    }
    with open(OUTPUT_DIR / "IBGE_meshes_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

    print(
        json.dumps(
            {
                k: v
                for k, v in stats.items()
                if k
                in [
                    "last_checked_at",
                    "files_count",
                    "records_count",
                    "size",
                    "duration",
                    "notes",
                ]
            },
            indent=4,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
