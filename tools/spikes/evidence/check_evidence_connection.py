"""
Checks Assumptions:
- A8: Evidence reads a Parquet snapshot (primary path); ClickHouse only for local development

Evidence:
- EVIDENCE_connection.json
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time

from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
PAGE = EVIDENCE_DIR / "pages" / "home.md"
PARQUET_PORT = 18787

QUERY_RE = re.compile(r"```sql (\w+)\n(.*?)```", re.DOTALL)
QUERY_COLUMNS = {
    "municipality_hour": [
        "municipality_id",
        "uf",
        "observed_hour",
        "accident_count",
        "precipitation_mm",
    ],
    "weather_evidence": [
        "station",
        "wmo_code",
        "year",
        "date",
        "hour",
        "precipitation_mm",
    ],
    "weather_clickhouse": [
        "station",
        "wmo_code",
        "year",
        "date",
        "hour",
        "precipitation_mm",
    ],
}

NOTES: list[str] = []


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def page_queries() -> dict[str, str]:
    found = {
        name: sql.strip()
        for name, sql in QUERY_RE.findall(PAGE.read_text(encoding="utf-8"))
    }
    missing = [name for name in QUERY_COLUMNS if name not in found]
    if missing:
        NOTES.append(f"ERROR: pages/home.md is missing queries: {', '.join(missing)}")
    return found


def start_parquet_reader() -> subprocess.Popen[str] | None:
    """Start the DuckDB reader when port 18787 is free. None means it was already up."""
    if _port_open(PARQUET_PORT):
        return None
    proc = subprocess.Popen(
        ["node", "read_parquet.mjs"],
        cwd=EVIDENCE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout is not None else ""
            NOTES.append(f"ERROR: parquet reader exited: {output.strip()}")
            return None
        if _port_open(PARQUET_PORT):
            return proc
        time.sleep(0.2)
    NOTES.append("ERROR: parquet reader did not listen on 18787")
    proc.kill()
    return None


def stop_parquet_reader(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_evidence_validate() -> bool:
    result = subprocess.run(
        ["evidence", "validate"],
        cwd=EVIDENCE_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    report = result.stdout.strip()
    if result.returncode != 0:
        NOTES.append(f"ERROR: {report or result.stderr.strip()}")
        return False
    try:
        payload = json.loads(report)
    except json.JSONDecodeError:
        NOTES.append(f"ERROR: evidence validate did not return JSON: {report}")
        return False
    if payload.get("valid") is True and payload.get("errorCount") == 0:
        return True
    NOTES.append(f"ERROR: {report}")
    return False


def query_rows(name: str, sql: str) -> list[dict] | None:
    result = subprocess.run(
        ["evidence", "query", "--format", "json", "--limit", "10"],
        cwd=EVIDENCE_DIR,
        input=sql,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        detail = (result.stdout or result.stderr).strip()
        NOTES.append(f"ERROR: {name}: {detail[:500]}")
        return None
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        NOTES.append(f"ERROR: {name} did not return JSON: {result.stdout.strip()[:500]}")
        return None
    if not isinstance(rows, list) or not rows:
        NOTES.append(f"ERROR: {name} returned no rows")
        return None
    missing = [column for column in QUERY_COLUMNS[name] if column not in rows[0]]
    if missing:
        NOTES.append(f"ERROR: {name} missing columns: {', '.join(missing)}")
        return None
    return rows


def rows_match_contract(name: str, rows: list[dict]) -> bool:
    if name == "municipality_hour":
        ok = all(str(row["municipality_id"]).isdigit() for row in rows)
        if not ok:
            NOTES.append("ERROR: municipality_hour municipality_id is not a digit code")
        return ok
    ok = all(
        isinstance(row["station"], str)
        and row["station"]
        and isinstance(row["wmo_code"], str)
        and row["wmo_code"]
        and row["year"] == "2022"
        and isinstance(row["date"], str)
        and row["date"]
        and isinstance(row["hour"], str)
        and row["hour"]
        for row in rows
    )
    if not ok:
        NOTES.append(f"ERROR: {name} rows do not match the page column contract")
    return ok


def run_named(name: str, queries: dict[str, str]) -> bool:
    sql = queries.get(name)
    if sql is None:
        return False
    rows = query_rows(name, sql)
    if rows is None:
        return False
    return rows_match_contract(name, rows)


def main() -> int:
    checks = {
        "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validates_successfully": False,
        "reads_from_clickhouse": False,
        "reads_from_parquet": False,
        "clickhouse_can_read_parquet": False,
        "notes": [],
    }
    reader = start_parquet_reader()
    try:
        queries = page_queries()
        checks["validates_successfully"] = run_evidence_validate()
        checks["reads_from_clickhouse"] = run_named("municipality_hour", queries)
        checks["reads_from_parquet"] = run_named("weather_evidence", queries)
        checks["clickhouse_can_read_parquet"] = run_named("weather_clickhouse", queries)
    finally:
        stop_parquet_reader(reader)

    checks["notes"].extend(NOTES)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "EVIDENCE_connection.json", "w") as f:
        json.dump(checks, f, indent=4)
        f.write("\n")

    print(json.dumps(checks, indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
