#!/usr/bin/env python3
"""Download IBGE localities lists: municipalities, states and regions.

Each list is stored under data/raw/brazil/IBGE/localities/. A saved list is
reused unless ``--force`` is given.

They come from the ``/api/v1/localidades`` routes ``municipios``, ``estados`` and
``regioes``.

Usage (from tools/spikes, after ``uv sync``):

    .venv/bin/python sources/download_IBGE_localities.py             # all three
    .venv/bin/python sources/download_IBGE_localities.py --force     # refresh

Evidence:
- IBGE_localities_metadata.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

from pathlib import Path

from _ibge import (
    IBGE_LOCALITIES_DIR,
    LOCALITIES,
    ensure_locality,
    parse_locality_list,
)
from _utils import Blocked, FetchError, OUTPUT_DIR, _duration, _size

NOTES = []


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IBGE localities into <output>."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="download even if the file already exists",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=IBGE_LOCALITIES_DIR,
        help="base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="seconds between requests (default: %(default)s)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="retries per request (default: %(default)s)",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=2.0,
        help="first retry wait in seconds, doubles each time (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="seconds per request (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.delay < 0 or args.retries < 0 or args.backoff < 0:
        parser.error("--delay, --retries and --backoff must not be negative")

    return args


def load_previous(path: Path) -> dict[str, dict]:
    """Return the list entries of an earlier run, so download times are not lost."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in LOCALITIES and isinstance(v, dict)}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory = args.output
    kinds = ["municipalities", "states", "regions"]

    failed = False
    requested = False
    aborted = None
    durations: dict[str, str] = {}
    started_run = time.monotonic()
    for kind in kinds:
        if requested:  # pause between real requests only
            time.sleep(args.delay * random.uniform(0.8, 1.2))
        started = time.monotonic()
        try:
            records, downloaded = ensure_locality(
                kind,
                directory,
                force=args.force,
                retries=args.retries,
                timeout=args.timeout,
                backoff=args.backoff,
            )
        except Blocked as error:
            aborted = (
                f"blocked by the server ({error}); wait a while before trying again"
            )
            NOTES.append(f"WARN: Stopped early: {aborted}")
            print(f"error: {aborted}", file=sys.stderr)
            break
        except (FetchError, ValueError) as error:
            NOTES.append(f"ERROR: {kind}: {error}")
            print(f"error: {kind}: {error}", file=sys.stderr)
            failed = True
            continue

        requested = requested or downloaded
        if downloaded:
            durations[kind] = _duration(time.monotonic() - started)

    # Describe every list on disk, including the ones this run did not download.
    metadata_path = OUTPUT_DIR / "IBGE_localities_metadata.json"
    previous = load_previous(metadata_path)
    entries: dict[str, dict] = {}
    total_records = total_size = 0
    for kind in kinds:
        path = directory / LOCALITIES[kind][1]
        if not path.is_file():
            continue
        body = path.read_bytes()
        try:
            records_count = len(parse_locality_list(body))
        except ValueError as error:
            NOTES.append(f"ERROR: {path.name}: {error}")
            failed = True
            continue
        total_records += records_count
        total_size += len(body)
        entries[kind] = {
            "records_count": records_count,
            "size": _size(len(body)),
            # A reused file keeps the time of the run that downloaded it.
            "duration": durations.get(kind) or previous.get(kind, {}).get("duration"),
        }

    summary = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_count": len(entries),
        "records_count": total_records,
        "size": _size(total_size),
        "duration": _duration(time.monotonic() - started_run),
        "aborted": aborted,
        "notes": NOTES,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump({**summary, **entries}, f, indent=4)

    print(json.dumps(summary, indent=4))

    return 1 if failed or aborted else 0


if __name__ == "__main__":
    sys.exit(main())
