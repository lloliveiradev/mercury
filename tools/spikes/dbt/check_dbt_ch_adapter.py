import sys
import json
import subprocess
import time

from pathlib import Path

DBT_PROJECT_DIR = Path(__file__).resolve().parent / "ch"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

NOTES: list[str] = []


def run_dbt_debug() -> bool:
    result = subprocess.run(
        ["dbt", "debug"],
        cwd=DBT_PROJECT_DIR,
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    else:
        NOTES.append(f"ERROR: {result.stderr.decode("utf-8")}")
        return False


def run_dbt_build() -> bool:
    result = subprocess.run(
        ["dbt", "build"],
        cwd=DBT_PROJECT_DIR,
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    else:
        NOTES.append(f"ERROR: {result.stderr.decode("utf-8")}")
        return False


def main() -> int:
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dbt_debugs_successfully": False,
        "dbt_builds_successfully": False,
        "notes": [],
    }

    checks["dbt_debugs_successfully"] = run_dbt_debug()
    checks["dbt_builds_successfully"] = run_dbt_build()

    checks["notes"].extend(NOTES)

    with open(OUTPUT_DIR / "DBT_ch_adapter.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
