#!/usr/bin/env python3
"""Download the PRF accident files (one row per occurrence), one folder per year.

PRF publishes one zip per year on Google Drive. This script stores each one as:

    data/raw/brazil/PRF/accidents/<year>/by-occurrence.csv

Only the per-occurrence files are allowed: the per-person files carry personal
data. Two guards enforce it:

* the Drive file name must be ``datatran<year>.zip``, checked before any byte of
  the file is downloaded;
* the CSV must have exactly the per-occurrence columns and only dates of that
  year, checked before it is stored.

A year whose file already exists is not downloaded again (``--force`` replaces
it). The zip is unpacked in a temporary folder and the CSV is moved into place
only after the checks pass, so a failed run never leaves a partial file behind.

``gdown`` is used instead of plain ``requests`` because it already handles the
Drive confirmation and error pages, retries, truncated bodies and atomic writes.

Usage (from tools/spikes):

    .venv/bin/python sources/download_PRF_accidents.py                 # 2022 to 2025
    .venv/bin/python sources/download_PRF_accidents.py --years 2024 2025
    .venv/bin/python sources/download_PRF_accidents.py --years 2025 --force

Evidence:
- PRF_accidents_metadata.json
"""

from __future__ import annotations

import argparse
import csv
import gdown
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

from gdown.exceptions import DownloadError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _prf import PRF_ACCIDENTS_DIR, BASE_COLUMNS
from _utils import OUTPUT_DIR, _duration, _size, _peak_memory

# "Agrupados por ocorrência" rows of
# https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf
# (retrieved 2026-11-26). The page also has links without text that point to other
# files: copy the ID from the visible "Baixar planilha" link of the right row.
FILE_IDS = {
    2022: "1PRQjuV5gOn_nn6UNvaJyVURDIfbSAK4-",
    2023: "1-WO3SfNrwwZ5_l7fRTiwBKRw7mi1-HUq",
    2024: "14lB0vqMFkaZj8HZ44b0njYgxs9nAN8KO",
    2025: "1-G3MdmHBt6CprDwcW99xxC4BZ2DU5ryR",
}
FILE_NAME = "by-occurrence.csv"
METADATA_NAME = "PRF_accidents_metadata.json"

NOTES = []


def inspect_csv(path: Path, year: int) -> int:
    """Return the number of records, or raise ValueError if the file is not expected."""
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, [])
        if tuple(header) != BASE_COLUMNS:
            extra = [c for c in header if c not in BASE_COLUMNS]
            missing = [c for c in BASE_COLUMNS if c not in header]
            raise ValueError(
                f"unexpected columns (extra: {extra}, missing: {missing}, or reordered)"
            )

        date_index = BASE_COLUMNS.index("data_inversa")
        records = 0
        for row in reader:
            records += 1
            if len(row) != len(BASE_COLUMNS):
                raise ValueError(f"line {reader.line_num} has {len(row)} fields")
            if not row[date_index].startswith(f"{year}-"):
                raise ValueError(
                    f"line {reader.line_num} is dated {row[date_index]!r}, not in {year}"
                )

    if records == 0:
        raise ValueError("the file has no records")
    return records


def describe(path: Path, year: int) -> dict:
    """Validate a stored CSV and return its metadata entry."""
    records = inspect_csv(path, year)
    with path.open("rb") as f:
        sha256 = hashlib.file_digest(f, "sha256").hexdigest()
    size = path.stat().st_size
    return {
        "records": records,
        "size": _size(size),
        "size_bytes": size,
        "sha256": sha256,
    }


def download_year(year: int, args: argparse.Namespace) -> dict:
    """Download, check and store one year; return its metadata entry."""
    expected = f"datatran{year}.zip"
    options = {
        "id": FILE_IDS[year],
        "quiet": True,
        "use_cookies": False,  # do not read or write ~/.cache/gdown/cookies.txt
        "timeout": args.timeout,
    }
    started = time.monotonic()

    name = gdown.download(skip_download=True, **options).path
    if name != expected:
        raise ValueError(
            f"the Drive file is named {name!r}, expected {expected!r}; not downloaded"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output, prefix=f".{year}.") as temp:
        zip_path = Path(temp) / expected
        zip_hash = hashlib.sha256()
        gdown.download(
            output=str(zip_path), retries=args.retries, hasher=zip_hash, **options
        )

        extracted = Path(temp) / FILE_NAME
        with zipfile.ZipFile(zip_path) as archive:
            members = [
                i for i in archive.infolist() if i.filename.lower().endswith(".csv")
            ]
            if len(members) != 1:
                raise ValueError(f"expected one csv in the zip, found {len(members)}")
            # The member name is never used as a path.
            with archive.open(members[0]) as source, extracted.open("wb") as out:
                shutil.copyfileobj(source, out)

        entry = describe(extracted, year)
        final = args.output / str(year) / FILE_NAME
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(extracted, final)

    return {
        **entry,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_file": expected,
        "source_sha256": zip_hash.hexdigest(),
        "duration": _duration(time.monotonic() - started),
    }


def load_previous(path: Path) -> dict[str, dict]:
    """Return the year entries of an earlier run, so retrieval dates are not lost."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k.isdigit() and isinstance(v, dict)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download PRF per-occurrence accident files into <output>/<year>."
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        choices=sorted(FILE_IDS),
        default=sorted(FILE_IDS),
        help="years to download (default: all known years)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PRF_ACCIDENTS_DIR,
        help="accidents base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="download and replace a year even if its file exists",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="seconds between downloads (default: %(default)s)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="retries per download (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="seconds without data before a request fails (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.delay < 0 or args.retries < 0:
        parser.error("--delay and --retries must not be negative")
    args.years = sorted(set(args.years))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    metadata_path = OUTPUT_DIR / METADATA_NAME
    previous = load_previous(metadata_path)
    # Keep the entries of years that are still on disk.
    results = {
        year: entry
        for year, entry in previous.items()
        if (args.output / year / FILE_NAME).is_file()
    }

    failed: list[tuple[int, str]] = []
    requested = False
    aborted = None
    started = time.monotonic()

    try:
        for year in args.years:
            target = args.output / str(year) / FILE_NAME
            # Left by a run that was killed before it could clean up.
            for stale in args.output.glob(f".{year}.*"):
                shutil.rmtree(stale, ignore_errors=True)

            try:
                if target.is_file() and not args.force:
                    entry = describe(target, year)
                    old = previous.get(str(year), {})
                    if old.get("sha256") == entry["sha256"]:
                        entry = old  # same bytes: keep when and how they arrived
                    else:
                        entry |= {"retrieved_at": None, "duration": None}
                    status = "already present"
                else:
                    if requested:
                        time.sleep(args.delay)
                    requested = True
                    entry = download_year(year, args)
                    status = f"downloaded in {entry['duration']}"
            except (DownloadError, OSError, ValueError, zipfile.BadZipFile) as error:
                failed.append((year, str(error)))
                NOTES.append(f"ERROR: {year}: {error}")
                print(f"{year}: FAILED: {error}", file=sys.stderr)
                if target.is_file() and not args.force:
                    results.pop(str(year), None)  # the stored file is not valid
                continue

            results[str(year)] = entry
            print(
                f"{year}: {status}, {entry['records_count']} records, {entry['size']} -> {target}"
            )
    except KeyboardInterrupt:
        aborted = "interrupted; run the same command again to resume"
        NOTES.append(f"WARN: Stopped early: {aborted}")

    results = dict(sorted(results.items()))
    summary = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": _duration(time.monotonic() - started),
        "peak_memory": _peak_memory(),
        "total_files": len(results),
        "total_records": sum(e["records_count"] for e in results.values()),
        "total_size": _size(sum(e["size_bytes"] for e in results.values())),
        "failed": failed,
        "aborted": aborted or None,
        "notes": NOTES,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump({**summary, **results}, f, indent=4)

    print(json.dumps(summary, indent=4))

    return 1 if failed or aborted else 0


if __name__ == "__main__":
    sys.exit(main())
