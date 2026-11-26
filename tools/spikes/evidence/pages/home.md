# Evidence Spike

Two ways to read the INMET Parquet snapshot, plus the ClickHouse mart.

# ClickHouse

```sql municipality_hour
SELECT
    toString(municipality_id) AS municipality_id,
    uf,
    toString(observed_hour) AS observed_hour,
    accident_count,
    precipitation_mm
FROM mercury.municipality_hour
LIMIT 10
```

{% table data="municipality_hour" subtotals=false /%}

# Parquet in Evidence

DuckDB `read_parquet` on `sources/parquets/INMET_weather_2022.parquet`, the same read the parquet connector uses. `node read_parquet.mjs` serves the rows. ClickHouse only fetches that result so the table can render next to the warehouse query.

```sql weather_evidence
SELECT
    station,
    wmo_code,
    year,
    date,
    hour,
    precipitation_mm
FROM url(
    'http://host.docker.internal:18787/',
    'JSONEachRow',
    'station String, wmo_code String, year String, date String, hour String, precipitation_mm Nullable(Float64)'
)
```

{% table data="weather_evidence" subtotals=false /%}

# Parquet in ClickHouse

```sql weather_clickhouse
SELECT
    `ESTACAO:`                          AS station,
    `CODIGO (WMO):`                     AS wmo_code,
    toString(`YEAR`)                    AS year,
    `Data`                              AS date,
    `Hora UTC`                          AS hour,
    `PRECIPITAÇÃO TOTAL, HORÁRIO (mm)`  AS precipitation_mm
FROM file('INMET_weather_2022.parquet', Parquet)
LIMIT 10
```

{% table data="weather_clickhouse" subtotals=false /%}
