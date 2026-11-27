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

from collections import Counter
from jsonschema.validators import validator_for
from jsonschema.exceptions import ValidationError

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _utils import OUTPUT_DIR, _clean_str, _duration, _peak_memory, _rate, _slugify
from _ibge import IBGE_LOCALITIES_DIR
from _prf import PRF_ACCIDENTS_DIR, PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA

NOTES = []
SCHEMA = PRF_ACCIDENTS_BY_OCCURRENCE_DICTIONARY_SCHEMA
VALIDATOR = validator_for(SCHEMA)(SCHEMA)
INVALID_EXAMPLES = 5


def get_municipality_key(data: dict) -> str:
    imediate: dict = data.get("regiao-imediata")
    intermediary: dict = imediate.get("regiao-intermediaria") if imediate else {}
    uf: dict = intermediary.get("UF") if intermediary else {}

    name = _clean_str(data.get("nome"), transform="upper")
    uf = _clean_str(uf.get("sigla"), transform="upper")

    if not name or not uf:
        return None

    return f"{name}-{uf}"


def main() -> int:
    if not PRF_ACCIDENTS_DIR.is_dir():
        print("error: PRF accidents raw directory not found", file=sys.stderr)
        return 1

    started = time.time()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "total_files": 0,
        "total_records": 0,
        "schema_validated_rows": 0,
        "municipality_matched_rows": 0,
        "municipality_matched_rate": 0.0,
        "rows_without_uf": 0,
        "unmatched_municipalities_count": 0,
        "unmatched_municipalities": [],
        "missing_coordinates_rows": 0,
        "weather_conditions_count": 0,
        "weather_conditions_rows": {},
        "by_year": {},
        "invalid_schema_rows": 0,
        "invalid_schema_fields": {},
        "notes": [],
    }
    weather_conditions: Counter = Counter()
    unmatched: Counter = Counter()
    invalid: dict[str, dict] = {}

    if not IBGE_LOCALITIES_DIR.exists() or not IBGE_LOCALITIES_DIR.is_dir():
        NOTES.append("WARN: IBGE localities directory not found")
    mfile = IBGE_LOCALITIES_DIR / "municipalities.json"
    if (
        not mfile.exists()
        or not mfile.is_file()
        or mfile.suffix != ".json"
        or mfile.stat().st_size == 0
    ):
        NOTES.append("WARN: IBGE municipalities file is not valid or is empty")
    mdf = pd.read_json(mfile)
    municipalities = (
        {get_municipality_key(m): m["id"] for m in mdf.to_dict(orient="records")}
        if not mdf.empty
        else {}
    )

    for f in sorted(PRF_ACCIDENTS_DIR.glob("*/*.csv")):
        checks["total_files"] += 1
        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            decimal=",",
            thousands=".",
            keep_default_na=False,
        )
        if df.empty:
            continue
        rows = df.to_dict(orient="records")
        checks["total_records"] += len(rows)
        year = {
            "rows": len(rows),
            "municipality_matched_rows": 0,
            "rows_without_uf": 0,
            "missing_coordinates_rows": 0,
        }
        checks["by_year"][f.parent.name] = year
        for a in rows:
            weather_conditions[
                _slugify(a["condicao_metereologica"], transform="upper")
            ] += 1
            name = _clean_str(a["municipio"], transform="upper")
            uf = _clean_str(a["uf"], transform="upper")
            if not uf:
                year["rows_without_uf"] += 1
            elif municipalities.get(f"{name}-{uf}"):
                year["municipality_matched_rows"] += 1
            else:
                unmatched[(name, uf)] += 1

            try:
                VALIDATOR.validate(a)
                checks["schema_validated_rows"] += 1
            except ValidationError as e:
                field = (
                    ".".join(str(p) for p in e.absolute_path)
                    or "Invalid accident structure"
                )
                failure = invalid.setdefault(field, {"rows": 0, "examples": []})
                failure["rows"] += 1
                if (
                    len(failure["examples"]) < INVALID_EXAMPLES
                    and e.message not in failure["examples"]
                ):
                    failure["examples"].append(str(e.message))
        coordinates = df[["latitude", "longitude"]].apply(
            pd.to_numeric, errors="coerce"
        )
        year["missing_coordinates_rows"] = int(coordinates.isna().any(axis=1).sum())
        year["municipality_matched_rate"] = _rate(
            year["municipality_matched_rows"], year["rows"], 4
        )
        for key in (
            "municipality_matched_rows",
            "rows_without_uf",
            "missing_coordinates_rows",
        ):
            checks[key] += year[key]

    checks["invalid_schema_rows"] = sum(f["rows"] for f in invalid.values())
    checks["invalid_schema_fields"] = invalid
    checks["unmatched_municipalities_count"] = len(unmatched)
    checks["unmatched_municipalities"] = [
        {"municipio": name, "uf": uf, "rows": rows}
        for (name, uf), rows in unmatched.most_common()
    ]
    checks["weather_conditions_count"] = len(weather_conditions)
    checks["weather_conditions_rows"] = dict(weather_conditions.most_common())
    checks["municipality_matched_rate"] = _rate(
        checks["municipality_matched_rows"], checks["total_records"], 4
    )
    checks["time_to_process"] = _duration(time.time() - started)
    checks["peak_memory"] = _peak_memory()
    checks["notes"] = NOTES

    with open(OUTPUT_DIR / "PRF_accidents_shape.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
