"""
Checks Assumptions:
- A12: IBGE municipal boundary files exist in a format PostGIS loads

Evidence:
- IBGE_meshes_shape.json
"""

from __future__ import annotations

import json
import psycopg
import sys
import time

from typing import Optional

from jsonschema.validators import validator_for
from jsonschema.exceptions import ValidationError

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _ibge import get_mesh_geometry, IBGE_DIR, GEOJSON_SCHEMA
from _utils import _duration, _peak_memory, _rate, OUTPUT_DIR
from _postgis import PG_CONN_INFO

MESHES_DIR = IBGE_DIR / "meshes"

SCHEMA = GEOJSON_SCHEMA
VALIDATOR = validator_for(SCHEMA)(SCHEMA)
SCHEMA_SAMPLE_ROWS = 100

NOTES = []


def check_postgis_geojson(geometry: Optional[dict]) -> int:
    if geometry is None:
        return 0

    try:
        VALIDATOR.validate(geometry)
    except ValidationError as error:
        NOTES.append(f"ERROR: not valid GeoJSON ({error})")
        return 0

    coordinates = geometry.get("coordinates") or []
    polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates
    if geometry.get("type") in ("Polygon", "MultiPolygon"):
        for polygon in polygons:
            for ring in polygon:
                if ring[0] != ring[-1]:
                    NOTES.append("WARN: polygon ring is not closed")
                    return 0

    return 1


def check_postgis_loadable(geometry: Optional[dict]) -> int:
    if geometry is None:
        return 0

    try:
        with psycopg.connect(PG_CONN_INFO) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ST_GeomFromGeoJSON(%s)", (json.dumps(geometry),))
                result = cur.fetchone()
                if result is None:
                    return 0
    except psycopg.Error as error:
        NOTES.append(f"ERROR: not able to connect to PostGIS: {error}")
        return 0

    return 1


def main() -> int:
    if not MESHES_DIR.is_dir():
        print("error: meshes directory not found", file=sys.stderr)
        return 1

    started = time.monotonic()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "postgis_compatible_rows": 0,
        "postgis_loadable_rows": 0,
        "schema_sampled_rows": 0,
        "sample_compatibility_rate": 0,
        "notes": [],
    }

    files = sorted(MESHES_DIR.glob("*.json"))
    step = max(len(files) // SCHEMA_SAMPLE_ROWS, 1)
    for file in files[::step][:SCHEMA_SAMPLE_ROWS]:
        geometry = get_mesh_geometry(file.read_bytes())
        checks["postgis_compatible_rows"] += check_postgis_geojson(geometry)
        checks["postgis_loadable_rows"] += check_postgis_loadable(geometry)
        checks["schema_sampled_rows"] += 1
    checks["sample_compatibility_rate"] = _rate(
        checks["postgis_compatible_rows"], checks["schema_sampled_rows"], 4
    )
    checks["time_to_process"] = _duration(time.monotonic() - started)
    checks["peak_memory"] = _peak_memory()
    checks["notes"] = NOTES

    with open(OUTPUT_DIR / "IBGE_meshes_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
