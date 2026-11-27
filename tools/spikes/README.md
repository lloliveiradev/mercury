# Phase 00 spikes

Throwaway checks for the assumptions in [`docs/design/source-findings.md`](../../docs/design/source-findings.md). Nothing here is imported by product code. Downloaded files stay under `data/` and are not committed. Each script writes a JSON file under `output/`.

Run every command from this directory, after `uv sync`. Python is 3.13, the version this environment was built for.

```bash
uv sync
docker compose up -d
```

`_utils.py` in this folder holds the helpers every spike shares (output folder, size, duration, peak memory, text cleaning). Each script adds this folder to `sys.path` before importing it, so the scripts still run as plain files.

`compose.yaml` includes the AWS Emulator, PostGIS and ClickHouse definitions under `docker/`. `compose.override.yaml` is picked up automatically: ClickHouse shares the emulator network so `s3()` can use the emulator certificate. Host ports are ClickHouse `18123`/`19000` and Postgres `15432`.

## Sources

Downloads are idempotent. A year or a mesh that is already on disk is skipped unless `--force` is passed. A failed download does not leave a partial file in place.

| Script                                   | Measures                                                                                                                                       | Output                                 |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `sources/download_PRF_accidents.py`      | PRF per-occurrence zips for 2022–2025. Refuses a file that is not `datatran<year>.zip` or whose columns differ from the occurrence allow-list. | `output/PRF_accidents_metadata.json`   |
| `sources/download_INMET_weather.py`      | INMET yearly automatic-station zips, unpacked to one CSV per station.                                                                          | `output/INMET_weather_metadata.json`   |
| `sources/download_IBGE_localities.py`    | IBGE municipalities, states and regions from `/api/v1/localidades`.                                                                            | `output/IBGE_localities_metadata.json` |
| `sources/download_IBGE_meshes.py`        | One GeoJSON mesh per municipality from `/api/v3/malhas`.                                                                                       | `output/IBGE_meshes_metadata.json`     |
| `sources/check_PRF_accidents_stats.py`   | CSV file count, row count, size and parse time.                                                                                                | `output/PRF_accidents_stats.json`      |
| `sources/check_INMET_weather_stats.py`   | Station-file count, row count, size and parse time.                                                                                            | `output/INMET_weather_stats.json`      |
| `sources/check_IBGE_localities_stats.py` | Record count, size and fetch time of the three locality lists.                                                                                 | `output/IBGE_localities_stats.json`    |
| `sources/check_IBGE_meshes_stats.py`     | Mesh file count, size and coordinate counts.                                                                                                   | `output/IBGE_meshes_stats.json`        |
| `sources/check_PRF_accidents_shape.py`   | Every row of every year: columns against the occurrence dictionary, missing coordinates, weather conditions, and a name-plus-UF match to IBGE. | `output/PRF_accidents_shape.json`      |
| `sources/check_INMET_weather_shape.py`   | Every station file: one-hour steps, missing precipitation per row and per file, header variants. The schema is checked on 48 rows per file.    | `output/INMET_weather_shape.json`      |
| `sources/check_IBGE_meshes_shape.py`     | 100 meshes spread over every state as GeoJSON, then `ST_GeomFromGeoJSON` on the spike PostGIS. Requires the compose stack.                     | `output/IBGE_meshes_shape.json`        |

```bash
.venv/bin/python sources/download_PRF_accidents.py                  # 2022 to 2025
.venv/bin/python sources/download_PRF_accidents.py --years 2025 --force
.venv/bin/python sources/download_INMET_weather.py
.venv/bin/python sources/download_INMET_weather.py --years 2022 --force --keep-zip
.venv/bin/python sources/download_IBGE_localities.py
.venv/bin/python sources/download_IBGE_meshes.py
.venv/bin/python sources/download_IBGE_meshes.py --codes 5221403 --limit 5

.venv/bin/python sources/check_PRF_accidents_stats.py
.venv/bin/python sources/check_PRF_accidents_shape.py
.venv/bin/python sources/check_INMET_weather_stats.py
.venv/bin/python sources/check_INMET_weather_shape.py
.venv/bin/python sources/check_IBGE_localities_stats.py
.venv/bin/python sources/check_IBGE_meshes_stats.py
.venv/bin/python sources/check_IBGE_meshes_shape.py
```

## AWS Emulator

`emulator/check_AWS_emulator.py` checks assumption A6. It creates a bucket and reads `hello.txt` back with boto3, asks ClickHouse `s3()` to read that object, materializes a small DataFrame through Dagster's `S3PickleIOManager`, and tries to upload one Parquet per INMET year. Requires the compose stack and `dagster-aws`.

```bash
.venv/bin/python emulator/check_AWS_emulator.py
```

Evidence: `output/AWS_emulator.json`.

## SeaweedFS

The S3-compatible alternative tested because the emulator refuses large objects. `docker/seaweedfs/compose.yaml` runs `chrislusf/seaweedfs:4.55` as one process (master, volume server, filer and S3 gateway) and is part of the compose stack.

| From                | Endpoint                 |
| ------------------- | ------------------------ |
| The host            | `http://127.0.0.1:8333`  |
| ClickHouse `s3()`   | `http://seaweedfs:8333`  |
| Filer UI, to browse | `http://127.0.0.1:8888/` |

The access key and secret come from `SEAWEEDFS_ACCESS_KEY` and `SEAWEEDFS_SECRET_KEY` (defaults in `docker/seaweedfs/.env.example`). It is plain HTTP with path-style addressing, so no CA bundle is needed. Data lives in the `seaweedfs-data` volume.

## dbt

`dbt/check_dbt_ch_adapter.py` runs `dbt debug` and `dbt build` in `dbt/ch`. The project profile is `ch`. The model is a synthetic municipality-hour mart (`seeds/hour_observations.csv`, `models/municipality_hour.sql`) with a grain test. Requires ClickHouse.

```bash
.venv/bin/python dbt/check_dbt_ch_adapter.py
```

Evidence: `output/DBT_ch_adapter.json`.

## Evidence

`evidence/check_evidence_connection.py` runs `evidence validate` and the three queries on `evidence/pages/home.md`: the ClickHouse mart, the Parquet snapshot through `read_parquet.mjs` on port 18787, and ClickHouse `file()` on the same Parquet. The check starts the Node reader when the port is free. Requires the compose stack and the Evidence CLI. The project pins Evidence `0.12.2` in `evidence/evidence.config.yaml`.

```bash
.venv/bin/python evidence/check_evidence_connection.py
```

Evidence: `output/EVIDENCE_connection.json`.
