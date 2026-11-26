"""
Checks Assumptions:
- A2:   PRF per-occurrence files have municipality, highway, km and date and time
- A3:   PRF files have coordinates
- A9:   PRF records the weather condition per occurrence (a data-quality cross-check)
- A10:  PRF gives the municipality as a name, not an IBGE code, and names can be matched to codes
- A11:  INMET hours are UTC and PRF times are local time

Evidence:
- PRF_accidents_shape.json
"""

from __future__ import annotations

import json
import pandas as pd
import sys
import time

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from typing import Optional

from _utils import OUTPUT_DIR, _clean_str
from _ibge import IBGE_LOCALITIES_DIR
from _prf import PRF_ACCIDENTS_DIR, PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA

NOTES = []


def format_municipality(data: dict) -> dict:
    imediate: dict = data.get("regiao-imediata")
    intermediary: dict = imediate.get("regiao-intermediaria") if imediate else {}
    uf: dict = intermediary.get("UF") if intermediary else {}

    return {
        "id": data.get("id"),
        "name": _clean_str(data.get("nome"), transform="upper"),
        "uf": _clean_str(uf.get("sigla"), transform="upper"),
    }


def find_municipality(
    municipalities: list[dict],
    name: str,
    uf: str,
) -> Optional[dict]:
    results: list[dict] = []

    results = [
        m
        for m in municipalities
        if m["name"] == _clean_str(name, transform="upper")
        and m["uf"] == _clean_str(uf, transform="upper")
    ]

    if len(results) > 1:
        NOTES.append(
            "WARN: multiple municipalities found, provide more specific parameters"
        )

    return results[0] if results else None


def main() -> int:
    if not PRF_ACCIDENTS_DIR.is_dir():
        print("error: PRF accidents raw directory not found", file=sys.stderr)
        return 1

    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema_validates_records": False,
        "columns_match_dictionary": False,
        "municipality_match_by_name": False,
        "has_weather_conditions": False,
        "notes": [],
        "accidents_sample": [],
        "weather_conditions_sample": [],
    }

    for f in PRF_ACCIDENTS_DIR.glob("*/*.csv"):
        if f.is_file() and f.suffix == ".csv":
            df = pd.read_csv(
                f,
                sep=";",
                encoding="latin-1",
                decimal=",",
                thousands=".",
                nrows=10,
                keep_default_na=False,
            )
            checks["accidents_sample"] = df.to_dict(orient="records")[:5]
            for a in checks["accidents_sample"]:
                try:
                    validate(a, PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA)
                    checks["schema_validates_records"] = True
                except ValidationError as e:
                    NOTES.append(f"ERROR: not valid accident data: {e}")

            checks["columns_match_dictionary"] = df.columns.tolist() == list(
                PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA["properties"].keys()
            )
            break  # only one check is enough for now

    weather_conditions = [
        _clean_str(r["condicao_metereologica"], transform="upper")
        for r in checks["accidents_sample"]
    ]
    weather_conditions = list(set(weather_conditions))
    weather_conditions.sort()
    checks["has_weather_conditions"] = len(weather_conditions) > 0
    checks["weather_conditions_sample"] = weather_conditions[:5]
    checks["notes"].append(
        "WARN: The dictionary does not say that there is a enum for weather"
        "conditions, might have a high cardinality of values.",
    )

    if not IBGE_LOCALITIES_DIR.exists() or not IBGE_LOCALITIES_DIR.is_dir():
        checks["municipality_match_by_name"] = False
        checks["notes"].append("WARN: IBGE localities directory not found")
    mfile = IBGE_LOCALITIES_DIR / "municipalities.json"
    if (
        not mfile.exists()
        or not mfile.is_file()
        or mfile.suffix != ".json"
        or mfile.stat().st_size == 0
    ):
        checks["municipality_match_by_name"] = False
        checks["notes"].append(
            "WARN: IBGE municipalities file is not valid or is empty"
        )
    mdf = pd.read_json(mfile)
    municipalities = [format_municipality(m) for m in mdf.to_dict(orient="records")]

    for a in checks["accidents_sample"]:
        municipality = find_municipality(municipalities, a["municipio"], a["uf"])
        if municipality:
            checks["municipality_match_by_name"] = True
            a["matched_municipality"] = municipality

    checks["notes"].extend(NOTES)

    with open(OUTPUT_DIR / "PRF_accidents_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(
        json.dumps(
            {
                k: v
                for k, v in checks.items()
                if k
                in [
                    "last_checked_at",
                    "schema_validates_records",
                    "columns_match_dictionary",
                    "municipality_match_by_name",
                    "has_weather_conditions",
                    "notes",
                ]
            },
            indent=4,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
