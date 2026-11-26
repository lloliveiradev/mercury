#!/usr/bin/env python3
"""Download the IBGE municipal meshes as GeoJSON, one file per municipality.

For every municipality in the IBGE localities API (5571 on 2026-11-26) this
script requests its mesh and stores it under:

    data/raw/brazil/IBGE/meshes/<municipality code>.json

for example ``data/raw/brazil/IBGE/meshes/5221403.json``. On 2026-11-26 the mesh
API answered HTTP 500 for 5101837 (Boa Esperança do Norte), so that one is
reported as failed.

The mesh API has no documented rate limit that we could verify, and it sits
behind Cloudflare, so the script is deliberately gentle:

* one request at a time, with a pause (default 0.3 s, with jitter) between them;
* 429 and 5xx answers and network errors are retried with exponential backoff,
  honouring ``Retry-After`` when the server sends it;
* a 403 (Cloudflare block or challenge) stops the run at once;
* the run stops after several municipalities in a row fail, instead of
  hammering a server that is refusing us;
* it is resumable: a file that already exists is skipped, so after any
  interruption the same command continues where it stopped.

Each answer is validated before it is written (valid GeoJSON, a feature whose
``codarea`` matches the requested code), and written atomically, so a crash never
leaves a half-written ``.json`` behind.

Usage (from tools/spikes, after ``uv sync``):

    .venv/bin/python sources/download_IBGE_meshes.py             # everything missing
    .venv/bin/python sources/download_IBGE_meshes.py --force     # everything again
    .venv/bin/python sources/download_IBGE_meshes.py --limit 5   # quick try
    .venv/bin/python sources/download_IBGE_meshes.py --codes 5221403 2615607
    .venv/bin/python sources/download_IBGE_meshes.py --delay 1 --quality intermediaria

Evidence:
- IBGE_meshes_metadata.json (describes every stored mesh)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

from pathlib import Path
from urllib.parse import urlencode

from _ibge import (
    IBGE_LOCALITIES_DIR,
    IBGE_MESH_DIR,
    MESH_FORMAT,
    MESH_URL,
    QUALITIES,
    count_mesh_coordinates,
    ensure_locality,
    fetch,
    write_atomic,
)
from _utils import Blocked, FetchError, OUTPUT_DIR, _duration, _size

NOTES = []


def validate_mesh(body: bytes, code: str) -> None:
    """Raise ValueError unless ``body`` is a GeoJSON mesh for ``code``."""
    try:
        data = json.loads(body)
    except ValueError as error:
        raise ValueError(f"not valid JSON ({error})") from error
    if (
        not isinstance(data, dict)
        or data.get("type") != "FeatureCollection"
        or not data.get("features")
    ):
        raise ValueError("not a non-empty FeatureCollection")
    codes = {str(f.get("properties", {}).get("codarea")) for f in data["features"]}
    if code not in codes:
        raise ValueError(f"codarea {sorted(codes)} does not match {code}")


def mesh_url(code: str, quality: str) -> str:
    query = urlencode({"formato": MESH_FORMAT, "qualidade": quality})
    return f"{MESH_URL.format(code=code)}?{query}"


def load_previous(path: Path) -> dict[str, dict]:
    """Return the mesh entries of an earlier run, so download times are not lost."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k.isdigit() and isinstance(v, dict)}


def describe_meshes(directory: Path, durations: dict[str, str]) -> tuple[dict, int]:
    """Describe every mesh stored in ``directory``; return (entries, total bytes).

    The metadata always covers the whole folder, whatever this run downloaded.
    A file that cannot be read is listed in the notes.
    """
    entries: dict[str, dict] = {}
    total = 0
    for file in sorted(directory.glob("*.json")):
        code = file.stem
        if not code.isdigit() or not file.is_file():
            continue
        body = file.read_bytes()
        try:
            count = count_mesh_coordinates(body)
        except ValueError as error:
            NOTES.append(f"ERROR: {code}: {error}")
            continue
        total += len(body)
        entries[code] = {
            "coordinates_count": count,
            "size": _size(len(body)),
            "duration": durations.get(code),  # unknown for files from elsewhere
        }
    return entries, total


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IBGE municipal meshes (GeoJSON) into <output>/<code>.json."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=IBGE_MESH_DIR,
        help="meshes base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--localities-output",
        type=Path,
        default=IBGE_LOCALITIES_DIR,
        help="localities base directory, where municipalities.json goes (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="download and replace a mesh even if it already exists",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITIES,
        default="maxima",
        help="mesh quality (default: %(default)s)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
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
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
        help="abort after this many failures in a row (default: %(default)s)",
    )
    parser.add_argument(
        "--limit", type=int, help="only the first N municipalities (to try the script)"
    )
    parser.add_argument(
        "--codes",
        nargs="+",
        metavar="CODE",
        help="only these 7-digit municipality codes",
    )
    args = parser.parse_args(argv)

    if args.delay < 0 or args.retries < 0 or args.backoff < 0:
        parser.error("--delay, --retries and --backoff must not be negative")

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory = args.output
    localities_directory = args.localities_output

    for folder in (directory, localities_directory):
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob("*.part"):  # left by a crash during a previous run
            stale.unlink()

    try:
        municipalities, list_downloaded = ensure_locality(
            "municipalities",
            localities_directory,
            retries=args.retries,
            timeout=args.timeout,
            backoff=args.backoff,
        )
    except (Blocked, FetchError, ValueError) as error:
        print(f"error: could not get the municipality list: {error}", file=sys.stderr)
        return 1

    codes = sorted(str(m["id"]) for m in municipalities)
    if args.codes:
        unknown = sorted(set(args.codes) - set(codes))
        if unknown:
            print(
                f"error: not IBGE municipality codes: {', '.join(unknown)}",
                file=sys.stderr,
            )
            return 1
        codes = sorted(set(args.codes))
    if args.limit is not None:
        codes = codes[: args.limit]

    downloaded = skipped = 0
    total_bytes = 0
    total_fetch_seconds = 0.0
    failed: list[tuple[str, str]] = []
    consecutive_failures = 0
    aborted = ""
    started = time.monotonic()
    metadata_path = OUTPUT_DIR / "IBGE_meshes_metadata.json"
    durations = {
        code: entry.get("duration")
        for code, entry in load_previous(metadata_path).items()
    }

    try:
        for index, code in enumerate(codes, start=1):
            target = directory / f"{code}.json"
            if target.is_file() and target.stat().st_size > 0 and not args.force:
                skipped += 1
                continue

            if list_downloaded or downloaded + len(failed) > 0:
                time.sleep(args.delay * random.uniform(0.8, 1.2))

            try:
                request_started = time.monotonic()
                body = fetch(
                    mesh_url(code, args.quality),
                    retries=args.retries,
                    timeout=args.timeout,
                    backoff=args.backoff,
                )
                request_seconds = time.monotonic() - request_started
                validate_mesh(body, code)
            except Blocked as error:
                aborted = (
                    f"blocked by the server ({error}); wait a while before trying again"
                )
                break
            except (FetchError, ValueError) as error:
                failed.append((code, str(error)))
                consecutive_failures += 1
                print(f"[{index}/{len(codes)}] {code} FAILED: {error}", file=sys.stderr)
                if consecutive_failures >= args.max_consecutive_failures:
                    aborted = f"{consecutive_failures} failures in a row; the server may be refusing us"
                    break
                continue

            write_atomic(target, body)
            downloaded += 1
            consecutive_failures = 0
            total_bytes += len(body)
            total_fetch_seconds += request_seconds
            fmt_size = _size(len(body))
            fmt_duration = _duration(request_seconds)
            durations[code] = fmt_duration
            print(f"[{index}/{len(codes)}] {code}  {fmt_size:>10}  {fmt_duration:>9}")
            if downloaded % 100 == 0:
                elapsed = time.monotonic() - started
                remaining = (
                    (len(codes) - index) * elapsed / max(downloaded + len(failed), 1)
                )
                print(
                    f"  progress: {downloaded} downloaded, {skipped} skipped, {len(failed)} failed, {_size(total_bytes)} so far (~{remaining / 60:.0f} min left)"
                )
    except KeyboardInterrupt:
        aborted = "interrupted; run the same command again to resume"

    if aborted:
        NOTES.append(f"WARN: Stopped early: {aborted}")

    entries, stored_bytes = describe_meshes(directory, durations)
    summary = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_count": len(entries),
        "records_count": len(entries),
        "size": _size(stored_bytes),
        "downloaded_count": downloaded,
        "duration": _duration(time.monotonic() - started),
        "failed": failed,
        "aborted": aborted or None,
        "notes": NOTES,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump({**summary, **entries}, f, indent=4)

    print(json.dumps(summary, indent=4))

    return 1 if failed or aborted else 0


if __name__ == "__main__":
    sys.exit(main())
