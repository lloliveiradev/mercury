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

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from _ibge import get_mesh_geometry, IBGE_DIR
from _utils import OUTPUT_DIR
from _postgis import PG_CONN_INFO

MESHES_DIR = IBGE_DIR / "meshes"

GEOJSON_SCHEMA = {
    "$schema": "http://json-schema.org",
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


NOTES = []


def check_postgis_geojson(geometry: Optional[dict]) -> bool:
    if geometry is None:
        return False

    try:
        validate(geometry, GEOJSON_SCHEMA)
    except ValidationError as error:
        NOTES.append(f"ERROR: not valid GeoJSON ({error})")
        return False

    if geometry.get("type") == "Polygon":
        fst = geometry.get("coordinates")[0]
        last = geometry.get("coordinates")[-1]
        if fst != last:
            NOTES.append("WARN: polygon is not closed")
            return False

    return True


def check_postgis_loadable(geometry: Optional[dict]) -> bool:
    if geometry is None:
        return False

    try:
        with psycopg.connect(PG_CONN_INFO) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ST_GeomFromGeoJSON(%s)", (json.dumps(geometry),))
                result = cur.fetchone()
                if result is None:
                    return False
    except psycopg.Error as error:
        NOTES.append(f"ERROR: not able to connect to PostGIS: {error}")
        return False

    return True


def main() -> int:
    if not MESHES_DIR.is_dir():
        print("error: meshes directory not found", file=sys.stderr)
        return 1

    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "is_postgis_compatible": False,
        "is_postgis_loadable": False,
        "notes": [],
    }

    for file in MESHES_DIR.glob("*.json"):
        if (
            file.is_file()
            and file.stat().st_size > 0
            and not file.name.startswith("_metadata")
        ):
            geometry = get_mesh_geometry(file.read_bytes())
            checks["is_postgis_compatible"] = check_postgis_geojson(geometry)
            checks["is_postgis_loadable"] = check_postgis_loadable(geometry)
            break  # only one check is enough for now

    checks["notes"].extend(NOTES)

    with open(OUTPUT_DIR / "IBGE_meshes_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
