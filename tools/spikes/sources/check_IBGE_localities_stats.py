"""
Checks Assumptions:
- A1: Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)

Evidence:
- IBGE_localities_stats.json
"""

from __future__ import annotations

import gzip
import json
import random
import sys
import time

from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from _utils import OUTPUT_DIR, _size, _duration

LOCALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
# kind -> API route
LOCALITIES = {
    "municipalities": "municipios",
    "states": "estados",
    "regions": "regioes",
}


USER_AGENT = "ibge-downloader/1.0"
RETRIABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 300  # seconds; never sleep longer than this on a server hint

DEFAULT_RETRIES = 4
DEFAULT_TIMEOUT = 30.0
DEFAULT_BACKOFF = 2.0


class Blocked(Exception):
    """The server refused us (403). Retrying would only make it worse."""


class FetchError(Exception):
    """A request failed for good (permanent status or retries exhausted)."""


def fetch(url: str, *, retries: int, timeout: float, backoff: float) -> bytes:
    """GET ``url`` and return the body, retrying transient failures politely."""
    request = Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    )
    last_error = "unknown error"

    for attempt in range(retries + 1):
        wait = backoff * (2**attempt) * random.uniform(0.8, 1.2)
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except HTTPError as error:
            if error.code == 403:
                raise Blocked(f"HTTP 403 from {url}") from error
            if error.code not in RETRIABLE_STATUS:
                raise FetchError(f"HTTP {error.code}") from error
            last_error = f"HTTP {error.code}"
            retry_after = error.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = min(int(retry_after), MAX_RETRY_AFTER)
        # URLError, timeouts, resets, truncated bodies (IncompleteRead) and bad gzip.
        except (OSError, EOFError, HTTPException) as error:
            last_error = f"{type(error).__name__}: {error}"

        if attempt < retries:
            print(
                f"  retry {attempt + 1}/{retries} in {wait:.1f}s ({last_error})",
                file=sys.stderr,
            )
            time.sleep(wait)

    raise FetchError(f"{last_error} after {retries + 1} attempts")


def parse_locality_list(body: bytes) -> list[dict]:
    """Return the records in ``body``, or raise ValueError if it is not a list of them."""
    try:
        data = json.loads(body)
    except ValueError as error:
        raise ValueError(f"not valid JSON ({error})") from error
    if (
        not isinstance(data, list)
        or not data
        or not all(isinstance(r, dict) and "id" in r for r in data)
    ):
        raise ValueError("not a non-empty list of records with an id")
    return data


def main() -> int:
    results: dict[str, dict] = {}
    total_records = 0
    total_size = 0
    total_duration = 0.0
    for kind, route in LOCALITIES.items():
        started = time.monotonic()
        body = fetch(
            f"{LOCALITIES_URL}/{route}",
            retries=DEFAULT_RETRIES,
            timeout=DEFAULT_TIMEOUT,
            backoff=DEFAULT_BACKOFF,
        )
        records = parse_locality_list(body)
        total_records += len(records)
        total_size += len(body)
        duration = time.monotonic() - started
        total_duration += duration
        results[kind] = {
            "records_count": len(records),
            "size": _size(len(body)),
            "duration": _duration(duration),
        }

    stats = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_count": len(results),
        "records_count": total_records,
        "size": _size(total_size),
        "duration": _duration(total_duration),
        **results,
    }
    with open(OUTPUT_DIR / "IBGE_localities_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

    print(json.dumps(stats, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
