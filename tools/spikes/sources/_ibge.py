import gzip
import json
import os
import random
import sys
import time

from http.client import HTTPException
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from _utils import Blocked, FetchError

IBGE_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "brazil" / "IBGE"
IBGE_LOCALITIES_DIR = IBGE_DIR / "localities"

LOCALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
LOCALITIES = {
    "municipalities": ("municipios", "municipalities.json"),
    "states": ("estados", "states.json"),
    "regions": ("regioes", "regions.json"),
}

USER_AGENT = "ibge-downloader/1.0"
RETRIABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 300  # seconds; never sleep longer than this on a server hint

MESH_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}"
MESH_FORMAT = "application/vnd.geo+json"
QUALITIES = ("minima", "intermediaria", "maxima")
IBGE_MESH_DIR = IBGE_DIR / "meshes"


def get_mesh_geometry(body: bytes | dict) -> Optional[dict]:
    try:
        data = body if isinstance(body, dict) else json.loads(body)
    except ValueError as error:
        raise ValueError(f"not valid JSON ({error})") from error

    if (
        not isinstance(data, dict)
        or not data.get("features")
        or not isinstance(data.get("features"), list)
        or len(data.get("features")) == 0
    ):
        return None

    return data.get("features")[0].get("geometry")


def count_mesh_coordinates(body: bytes | dict) -> Optional[int]:
    """Return the number of points in every ring of the mesh, holes included."""
    geometry = get_mesh_geometry(body)
    if not geometry or not geometry.get("coordinates"):
        return None

    coordinates = geometry["coordinates"]
    if geometry.get("type") == "Polygon":
        polygons = [coordinates]
    elif geometry.get("type") == "MultiPolygon":
        polygons = coordinates
    else:
        return None

    return sum(len(ring) for polygon in polygons for ring in polygon)


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


def write_atomic(path: Path, body: bytes) -> None:
    """Write ``body`` to ``path`` so readers never see a partial file."""
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    os.replace(partial, path)


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


def ensure_locality(
    kind: str,
    directory: Path,
    *,
    force: bool = False,
    retries: int,
    timeout: float,
    backoff: float,
) -> tuple[list[dict], bool]:
    """Return ``(records, downloaded)`` for ``kind`` (a key of ``LOCALITIES``).

    If ``directory`` already holds a valid file for ``kind`` it is reused and
    nothing is requested (unless ``force``). A missing, empty or corrupt file is
    downloaded again. Raises ``Blocked``, ``FetchError`` or ``ValueError``.
    """
    route, file_name = LOCALITIES[kind]
    saved = directory / file_name

    if not force and saved.is_file():
        try:
            return parse_locality_list(saved.read_bytes()), False
        except ValueError:
            pass  # corrupt or empty: fall through and download it again

    body = fetch(
        f"{LOCALITIES_URL}/{route}", retries=retries, timeout=timeout, backoff=backoff
    )
    records = parse_locality_list(body)
    directory.mkdir(parents=True, exist_ok=True)
    write_atomic(saved, body)
    return records, True


GEOJSON_SCHEMA = {
    "x-schema-url": "https://geojson.org/",
    "title": "GeoJSON Geometry",
    "type": "object",
    "required": ["type"],
    "oneOf": [
        {
            "title": "Point",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "Point"},
                "coordinates": {"$ref": "#/definitions/position"},
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "LineString",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "LineString"},
                "coordinates": {
                    "type": "array",
                    "minItems": 2,
                    "items": {"$ref": "#/definitions/position"},
                },
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "Polygon",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "Polygon"},
                "coordinates": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "minItems": 4,
                        "items": {"$ref": "#/definitions/position"},
                    },
                },
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "MultiPoint",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "MultiPoint"},
                "coordinates": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/position"},
                },
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "MultiLineString",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "MultiLineString"},
                "coordinates": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "items": {"$ref": "#/definitions/position"},
                    },
                },
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "MultiPolygon",
            "required": ["coordinates"],
            "properties": {
                "type": {"const": "MultiPolygon"},
                "coordinates": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "minItems": 4,
                            "items": {"$ref": "#/definitions/position"},
                        },
                    },
                },
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
        {
            "title": "GeometryCollection",
            "required": ["geometries"],
            "properties": {
                "type": {"const": "GeometryCollection"},
                "geometries": {"type": "array", "items": {"$ref": "#"}},
                "bbox": {"$ref": "#/definitions/bbox"},
            },
        },
    ],
    "definitions": {
        "position": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {"type": "number"},
        },
        "bbox": {"type": "array", "minItems": 4, "items": {"type": "number"}},
    },
}
