#!/usr/bin/env python3
"""Download the INMET hourly-weather yearly archives and unpack them as station files.

For each year the portal publishes one zip:

    https://portal.inmet.gov.br/uploads/dadoshistoricos/<year>.zip

with one CSV per station, named like ``INMET_NE_CE_A347_CAMPOS SALES_01-01-2022_A_31-12-2022.CSV``.
This script downloads the zip and stores the stations as:

    data/raw/brazil/INMET/weather/<year>/<station code>.csv     (for example 2022/A347.csv)

Only the station code is kept from each name (``INMET_FILE`` in ``_inmet.py``).
The default years are 2022 to 2025, the sample used for the project.

How it behaves:

* A year whose folder already exists is skipped (``--force`` replaces it). A year is
  unpacked into a hidden temporary folder and renamed to ``<year>`` only when every
  file was written, so an existing ``<year>`` folder always means "complete".
* The zip is streamed to ``<year>.zip.part`` and, if the connection drops, the next
  attempt resumes with an HTTP ``Range`` request (or starts over if the server
  ignores ranges). The portal has been seen resetting connections, so retries wait
  longer than the IBGE scripts do.
* The zip is deleted after a successful unpack unless ``--keep-zip`` is given. A kept
  ``<year>.zip`` is reused next time instead of being downloaded again.
* Only the base name of each zip member is used, so the folder layout inside the zip
  does not matter and nothing can be written outside the year folder.
* If a ``.csv`` member does not match the INMET file name pattern, or two members
  would get the same station code, the year fails before anything is written.
* One request at a time, a pause between years, a 403 stops the whole run.

Usage (from tools/spikes, after ``uv sync``):

    .venv/bin/python sources/download_INMET_weather.py                  # 2022 to 2025
    .venv/bin/python sources/download_INMET_weather.py --years 2023 2024
    .venv/bin/python sources/download_INMET_weather.py --years 2022 --force --keep-zip
    .venv/bin/python sources/download_INMET_weather.py --user-agent "Mozilla/5.0 ..."

Evidence:
- INMET_weather_metadata.json (files, records, source checksum and retrieval date)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
import zipfile

from datetime import date
from http.client import HTTPException
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _inmet import (
    YearError,
    CHUNK,
    DEFAULT_USER_AGENT,
    DEFAULT_YEARS,
    INMET_WEATHER_DIR,
    INMET_FILE,
    MAX_RETRY_AFTER,
    PROGRESS_EVERY,
    RETRIABLE_STATUS,
    WEATHER_URL_TEMPLATE,
)
from _utils import Blocked, FetchError, OUTPUT_DIR, _duration, _peak_memory, _size

METADATA_NAME = "INMET_weather_metadata.json"
HEADER_LINES = 9  # 8 lines about the station, then the column names
NOTES = []


def download_zip(
    url: str,
    part: Path,
    *,
    retries: int,
    timeout: float,
    backoff: float,
    user_agent: str,
    label: str,
) -> None:
    """Stream ``url`` into ``part``, resuming a partial file when possible."""
    last_error = "unknown error"

    for attempt in range(retries + 1):
        wait = backoff * (2**attempt) * random.uniform(0.8, 1.2)
        offset = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": user_agent, "Accept": "*/*"}
        if offset:
            headers["Range"] = f"bytes={offset}-"

        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                length = response.headers.get("Content-Length")
                if offset and response.status == 206:
                    match = re.match(
                        r"bytes (\d+)-", response.headers.get("Content-Range", "")
                    )
                    if match and int(match.group(1)) == offset:
                        mode = "ab"
                    else:  # the server resumed somewhere else: do not trust it
                        offset, mode = 0, "wb"
                else:  # no range support (200), or nothing to resume
                    offset, mode = 0, "wb"
                total = offset + int(length) if length and length.isdigit() else None

                if offset:
                    print(f"  {label}: resuming at {_size(offset)}")
                written = offset
                next_report = time.monotonic() + PROGRESS_EVERY
                with part.open(mode) as out:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        written += len(chunk)
                        if time.monotonic() >= next_report:
                            of = (
                                f" of {_size(total)} ({written * 100 // total}%)"
                                if total
                                else ""
                            )
                            print(f"  {label}: {_size(written)}{of}")
                            next_report = time.monotonic() + PROGRESS_EVERY

            if total is not None and written != total:
                raise OSError(f"truncated download: {written} of {total} bytes")
            return
        except HTTPError as error:
            if error.code == 403:
                raise Blocked(f"HTTP 403 from {url}") from error
            if (
                error.code == 416
            ):  # our partial file does not fit the server's: start over
                part.unlink(missing_ok=True)
                last_error = "HTTP 416 (partial file discarded)"
            elif error.code not in RETRIABLE_STATUS:
                raise FetchError(f"HTTP {error.code} from {url}") from error
            else:
                last_error = f"HTTP {error.code}"
                retry_after = error.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = min(int(retry_after), MAX_RETRY_AFTER)
        # URLError, timeouts, resets, truncated bodies (IncompleteRead).
        except (OSError, HTTPException) as error:
            last_error = f"{type(error).__name__}: {error}"

        if attempt < retries:
            print(
                f"  retry {attempt + 1}/{retries} in {wait:.1f}s ({last_error})",
                file=sys.stderr,
            )
            time.sleep(wait)

    raise FetchError(f"{last_error} after {retries + 1} attempts")


def new_name(file_name: str) -> str | None:
    """Return the normalized name, or None if the file is not an INMET download."""
    match = INMET_FILE.match(file_name)
    if match is None:
        return None
    return f"{match.group('code').upper()}.csv"


def plan_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Map target file name -> zip member. Raise YearError on anything ambiguous."""
    targets: dict[str, tuple[str, zipfile.ZipInfo]] = (
        {}
    )  # casefolded name -> (name, member)
    unmatched: list[str] = []
    clashes: list[str] = []

    for info in archive.infolist():
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename.replace("\\", "/"))
        base = path.name
        # macOS adds resource-fork copies ("__MACOSX/._name.CSV"); they are not data.
        if (
            "__MACOSX" in path.parts
            or base.startswith("._")
            or not base.lower().endswith(".csv")
        ):
            continue
        target = new_name(base)
        if target is None:
            unmatched.append(info.filename)
            continue
        key = target.casefold()
        if key in targets:
            clashes.append(
                f"{info.filename!r} and {targets[key][1].filename!r} both become {target!r}"
            )
            continue
        targets[key] = (target, info)

    problems = []
    if unmatched:
        shown = ", ".join(repr(n) for n in unmatched[:5])
        more = f" (+{len(unmatched) - 5} more)" if len(unmatched) > 5 else ""
        problems.append(
            f"{len(unmatched)} csv member(s) do not match the INMET name pattern: {shown}{more}"
        )
    problems.extend(clashes)
    if problems:
        raise YearError("; ".join(problems))
    if not targets:
        raise YearError("the zip has no station csv files")
    return dict(targets.values())


def unpack(zip_path: Path, temp_dir: Path) -> tuple[int, int]:
    """Unpack the stations of ``zip_path`` into ``temp_dir``; return (files, bytes)."""
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as error:
        raise YearError(f"not a valid zip file ({error})") from error

    with archive:
        members = plan_members(archive)
        temp_dir.mkdir(parents=True)
        total = 0
        for target_name, info in sorted(members.items()):
            try:
                with (
                    archive.open(info) as source,
                    (temp_dir / target_name).open("wb") as out,
                ):
                    shutil.copyfileobj(source, out, CHUNK)
            except zipfile.BadZipFile as error:  # CRC mismatch and similar
                raise YearError(
                    f"corrupt member {info.filename!r} ({error})"
                ) from error
            total += info.file_size
    return len(members), total


def process_year(year: int, args: argparse.Namespace) -> Optional[dict]:
    """Download and unpack one year.

    Return None if the year was already there, otherwise where its files came from.
    """
    final = args.output / str(year)
    if final.exists() and not args.force:
        count = sum(1 for _ in final.glob("*.csv"))
        print(
            f"{year}: already present ({count} csv files in {final}), skipped (--force to replace)"
        )
        return None

    args.output.mkdir(parents=True, exist_ok=True)
    zip_path = args.output / f"{year}.zip"
    part = args.output / f"{year}.zip.part"
    temp_dir = args.output / f".{year}.extracting"
    if temp_dir.exists():  # left by a crash during a previous run
        shutil.rmtree(temp_dir)

    started = time.monotonic()
    url = WEATHER_URL_TEMPLATE.format(year=year)
    download_duration = None  # unknown when a kept zip is reused
    if zip_path.is_file() and zipfile.is_zipfile(zip_path) and not args.force:
        print(f"{year}: reusing {zip_path} ({_size(zip_path.stat().st_size)})")
    else:
        print(f"{year}: downloading {url}")
        download_started = time.monotonic()
        download_zip(
            url,
            part,
            retries=args.retries,
            timeout=args.timeout,
            backoff=args.backoff,
            user_agent=args.user_agent,
            label=str(year),
        )
        seconds = time.monotonic() - download_started
        download_duration = _duration(seconds)
        size = part.stat().st_size
        os.replace(part, zip_path)
        if not zipfile.is_zipfile(
            zip_path
        ):  # e.g. an HTML maintenance page served with status 200
            zip_path.unlink()
            raise YearError(
                "the download is not a zip file (the portal may be serving an error page)"
            )
        print(
            f"{year}: downloaded {_size(size)} in {_duration(seconds)} ({_size(int(size / max(seconds, 1e-9)))}/s)"
        )

    with zip_path.open("rb") as f:
        source = {
            "source_url": url,
            "source_size": _size(zip_path.stat().st_size),
            "source_sha256": hashlib.file_digest(f, "sha256").hexdigest(),
            # The zip is last written when its download ends.
            "retrieved_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(zip_path.stat().st_mtime)
            ),
            "duration": download_duration,
        }

    unpack_started = time.monotonic()
    try:
        files, total = unpack(zip_path, temp_dir)
    except YearError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    # Swap in the finished folder; with --force the old one is removed only now.
    if final.exists():
        shutil.rmtree(final)
    os.replace(temp_dir, final)
    print(
        f"{year}: {files} stations, {_size(total)} unpacked in {_duration(time.monotonic() - unpack_started)} -> {final}"
    )

    if not args.keep_zip:
        zip_path.unlink()
    print(f"{year}: done in {_duration(time.monotonic() - started)}")
    return source


def describe_year(folder: Path) -> dict:
    """Count the station files, records and bytes of one stored year."""
    files = records = size = 0
    for path in folder.glob("*.csv"):
        body = path.read_bytes()
        lines = body.count(b"\n") + (not body.endswith(b"\n"))
        files += 1
        records += max(lines - HEADER_LINES, 0)
        size += len(body)
    return {
        "files": files,
        "records": records,
        "size": _size(size),
        "size_bytes": size,
    }


def load_previous(path: Path) -> dict[str, dict]:
    """Return the year entries of an earlier run, so retrieval dates are not lost."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k.isdigit() and isinstance(v, dict)}


def describe_years(
    output: Path, previous: dict[str, dict], sources: dict[str, dict]
) -> dict[str, dict]:
    """Describe every year stored under ``output`` that is known to the metadata."""
    entries: dict[str, dict] = {}
    for year in sorted(set(previous) | set(sources)):
        folder = output / year
        if not folder.is_dir():
            continue
        entry = describe_year(folder)
        old = previous.get(year, {})
        if year in sources:
            entry |= sources[year]
        elif all(old.get(k) == entry[k] for k in ("files_count", "size_bytes")):
            entry = old  # unchanged: keep when and how it arrived
        else:
            entry |= {"retrieved_at": None, "duration": None}
        entries[year] = entry
    return entries


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download INMET yearly weather zips and unpack them as <output>/<year>/<station code>.csv."
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(DEFAULT_YEARS),
        metavar="YEAR",
        help="years to download (default: 2022 2023 2024 2025)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=INMET_WEATHER_DIR,
        help="weather base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="download and replace a year even if its folder exists",
    )
    parser.add_argument(
        "--keep-zip", action="store_true", help="keep <year>.zip after unpacking"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="seconds between years (default: %(default)s)",
    )
    parser.add_argument(
        "--retries", type=int, default=5, help="retries per year (default: %(default)s)"
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=5.0,
        help="first retry wait in seconds, doubles each time (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="seconds without data before a request fails (default: %(default)s)",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    this_year = date.today().year
    bad = [y for y in args.years if not 2000 <= y <= this_year]
    if bad:
        parser.error(f"years must be between 2000 and {this_year}: {bad}")
    if args.delay < 0 or args.retries < 0 or args.backoff < 0:
        parser.error("--delay, --retries and --backoff must not be negative")
    args.years = sorted(set(args.years))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    metadata_path = OUTPUT_DIR / METADATA_NAME
    previous = load_previous(metadata_path)
    sources: dict[str, dict] = {}
    failed: list[tuple[int, str]] = []
    requested = False
    aborted = None
    interrupted = False
    started = time.monotonic()

    try:
        for year in args.years:
            if requested:
                time.sleep(args.delay * random.uniform(0.8, 1.2))
            try:
                source = process_year(year, args)
            except Blocked as error:
                aborted = (
                    f"blocked by the server ({error}); wait a while before trying again"
                )
                break
            except (FetchError, YearError) as error:
                failed.append((year, str(error)))
                NOTES.append(f"ERROR: {year}: {error}")
                print(f"{year}: FAILED: {error}", file=sys.stderr)
                requested = True
                continue

            if source is not None:
                sources[str(year)] = source
                requested = True
            elif str(year) not in previous:
                sources[str(year)] = {"retrieved_at": None, "duration": None}
    except KeyboardInterrupt:
        interrupted = True
        aborted = (
            "interrupted; run the same command again to resume "
            "(a partial zip is resumed)"
        )

    if aborted:
        NOTES.append(f"WARN: Stopped early: {aborted}")
        print(f"stopped early: {aborted}", file=sys.stderr)

    entries = describe_years(args.output, previous, sources)
    summary = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": _duration(time.monotonic() - started),
        "peak_memory": _peak_memory(),
        "total_files": sum(e["files_count"] for e in entries.values()),
        "total_records": sum(e["records_count"] for e in entries.values()),
        "total_size": _size(sum(e["size_bytes"] for e in entries.values())),
        "failed": failed,
        "aborted": aborted,
        "notes": NOTES,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump({**summary, **entries}, f, indent=4)

    print(json.dumps(summary, indent=4))

    if interrupted:
        return 130
    return 1 if failed or aborted else 0


if __name__ == "__main__":
    sys.exit(main())
