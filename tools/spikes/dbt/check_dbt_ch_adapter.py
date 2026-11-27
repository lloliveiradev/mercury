import sys
import json
import subprocess
import time

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _utils import OUTPUT_DIR, _duration, _peak_memory

DBT_PROJECT_DIR = Path(__file__).resolve().parent / "ch"

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
    started = time.monotonic()
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "time_to_process": None,
        "peak_memory": None,
        "dbt_debugs_successfully": False,
        "dbt_builds_successfully": False,
        "notes": [],
    }

    checks["dbt_debugs_successfully"] = run_dbt_debug()
    checks["dbt_builds_successfully"] = run_dbt_build()

    checks["time_to_process"] = _duration(time.monotonic() - started)
    checks["peak_memory"] = _peak_memory()
    checks["notes"] = NOTES

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "DBT_ch_adapter.json", "w") as f:
        json.dump(checks, f, indent=4)

    print(json.dumps(checks, indent=4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
