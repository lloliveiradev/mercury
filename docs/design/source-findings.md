# Phase 00 source findings

Downloaded on 2026-11-26 and checked on 2026-11-26 and 2026-11-27 with the scripts in [`tools/spikes`](../../tools/spikes/README.md). Each row points at the JSON those scripts wrote. The PRF and INMET shape checks read every row of every year. Where a check uses a sample, the sample size is stated.

Peak memory is the peak resident memory of each check process on macOS. No download recorded it. A6 is still open: a SeaweedFS container was added to the spike stack, and the retest against it has not been run.

## Assumptions

| #   | Assumption                                                                                | Status    | Evidence                                                                                                                                                                                                                                                                                        |
| --- | ----------------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)                        | confirmed | Unpacked sources are about 1.6 GiB. The heaviest check, the PRF shape check, peaked at 447.0 MiB; the INMET checks stayed near 120 MiB because they read one station file at a time. See the volume table.                                                                                      |
| A2  | PRF per-occurrence files have municipality, highway, km and date and time                 | confirmed | The downloader stored 2022–2025 only after the occurrence column allow-list matched, and `failed` is empty. All 278,103 rows pass the dictionary schema, including `municipio`, `br`, `km`, `data_inversa` and `horario`.                                                                       |
| A3  | PRF files have coordinates                                                                | confirmed | `latitude` and `longitude` are on the allow-list, and no row of the 278,103 lacks either one.                                                                                                                                                                                                   |
| A4  | INMET catalogue has station coordinates and the yearly files are parseable                | confirmed | Four yearly zips unpacked to 2,293 station CSVs. Every file has a valid preamble (station, WMO code, latitude, longitude) and the same observation header. The schema passed on 111,777 sampled rows, 48 per file. Coordinates come from the file preamble, not from a separate catalogue.      |
| A5  | INMET provides precipitation hourly for most stations                                     | confirmed | All 2,293 station files step by one hour. 31.1% of the 19,899,048 station-hours have no precipitation value. 221 station files have none at all and 428 lack it in more than half of their hours, so 1,865 files have a value in at least half. The gap changes by year; see the INMET section. |
| A6  | AWS Emulator serves S3 to boto3, Dagster and ClickHouse `s3()` with large Parquet files   | refuted   | boto3, Dagster's pickle IO manager, and ClickHouse `s3()` on `hello.txt` succeeded. All four year Parquets returned HTTP 413. `fits_large_parquet_files` is false.                                                                                                                              |
| A7  | The dbt adapter for ClickHouse supports the marts we need                                 | confirmed | `dbt debug` and `dbt build` succeeded for one synthetic municipality-hour model and its grain test. The spike pins `dbt-core` 1.12.7 and `dbt-clickhouse` 1.10.4. This does not exercise the real weather-accident mart.                                                                        |
| A8  | Evidence reads a Parquet snapshot (primary path); ClickHouse only for local development   | confirmed | `evidence validate` passed, and all three page queries returned rows: the ClickHouse mart, the Parquet via the DuckDB reader, and ClickHouse `file()` on that Parquet. Evidence is 0.12.2.                                                                                                      |
| A9  | PRF records the weather condition per occurrence (a data-quality cross-check)             | confirmed | `condicao_metereologica` is filled on every row. The files hold ten distinct values, listed in the PRF section.                                                                                                                                                                                 |
| A10 | PRF gives the municipality as a name, not an IBGE code, and names can be matched to codes | confirmed | `municipio` is a name. On normalized name plus UF, 277,187 of 278,103 rows (99.67%) match an IBGE municipality. No row lacks the UF. The 916 unmatched rows are 11 name and UF pairs, listed in the PRF section.                                                                                |
| A11 | INMET hours are UTC and PRF times are local time                                          | changed   | Every INMET file is labelled `HHMM UTC`. PRF `horario` is `HH:MM:SS` with no offset. The local dictionary text labels that clock as UTC−3; the files do not say so, and Brazil is not one offset.                                                                                               |
| A12 | IBGE municipal boundary files exist in a format PostGIS loads                             | confirmed | 5,570 GeoJSON meshes exist for 5,571 municipality codes. 100 of them, evenly spaced over the codes, passed the GeoJSON check with closed rings and `ST_GeomFromGeoJSON` on the spike PostGIS. One code has no mesh; see below.                                                                  |

## Volumes

Unpacked size is the CSV or JSON on disk. INMET and PRF durations in the metadata are the download. The stats durations are a local re-read. Localities have no checksum in the metadata.

| Source          | Years   | URL                                                                                                  | Retrieved  | Unpacked | Records     | Download    | Re-read |
| --------------- | ------- | ---------------------------------------------------------------------------------------------------- | ---------- | -------- | ----------- | ----------- | ------- |
| PRF accidents   | 2022–25 | [PRF open data](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf) | 2026-11-26 | 77.3 MiB | 278,103     | 27.5 s      | 2.94 s  |
| INMET weather   | 2022–25 | `https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip`                                     | 2026-11-26 | 1.5 GiB  | 19,899,048  | 59.0 s      | 57.8 s  |
| IBGE localities | 2026    | `https://servicodados.ibge.gov.br/api/v1/localidades`                                                | 2026-11-26 | 2.4 MiB  | 5,603       | 1.72 s      | 0.02 s  |
| IBGE meshes     | 2026    | `https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}`                                   | 2026-11-26 | 53.8 MiB | 5,570 files | 49 min 17 s | 1.26 s  |

Localities are 5,571 municipalities, 27 states and 5 regions.

### PRF, per occurrence, one zip per year

The publication page was read on 2026-11-26. Each zip is the "Agrupados por ocorrência" file `datatran<year>.zip`. The person-level files were not downloaded.

| Year | Rows   | CSV      | CSV sha256                                                         | Zip sha256                                                         |
| ---- | ------ | -------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 2022 | 64,606 | 17.9 MiB | `d11bbfdec9b5df6f08a083c63acb2c1b4d3bad71d31481d7ce1368d5fa38783a` | `5ace05699b82c720e47e28768323630310ef7fe300db57388da246fb448c8855` |
| 2023 | 67,766 | 18.9 MiB | `2e6a9eac714524822fc3150be4d0614e27c7f14aa674520c94e5d2e4089356dd` | `b233c47d16b3980a6692472f9fe1bbab57698700fbb918d22628a5c0a382d985` |
| 2024 | 73,202 | 20.4 MiB | `7d26e6f4528c2ca2636a8fea2c5bc8755a0ff6a182d82c238a8793b016e4366d` | `905dac836867297b261e4edefff6cdb470809814e7e1796b3f2f57517099d165` |
| 2025 | 72,529 | 20.2 MiB | `bb844d45a07b5b50f5f76011e28f47e370fa6742e9211edac5510dcbe72ce4d8` | `52c8a631ac9d428bf845e2fa996b8c61f66b219f7014a61d292f9d95d186bb0f` |

Drive file ids, from the visible download link on that page: 2022 `1PRQjuV5gOn_nn6UNvaJyVURDIfbSAK4-`, 2023 `1-WO3SfNrwwZ5_l7fRTiwBKRw7mi1-HUq`, 2024 `14lB0vqMFkaZj8HZ44b0njYgxs9nAN8KO`, 2025 `1-G3MdmHBt6CprDwcW99xxC4BZ2DU5ryR`.

Occurrence columns, semicolon-separated, `latin-1`: `id`, `data_inversa` (`YYYY-MM-DD`), `dia_semana`, `horario` (`HH:MM:SS`), `uf`, `br`, `km`, `municipio`, `causa_acidente`, `tipo_acidente`, `classificacao_acidente`, `fase_dia`, `sentido_via`, `condicao_metereologica`, `tipo_pista`, `tracado_via`, `uso_solo`, `pessoas`, `mortos`, `feridos_leves`, `feridos_graves`, `ilesos`, `ignorados`, `feridos`, `veiculos`, `latitude`, `longitude`, `regional`, `delegacia`, `uop`. Decimals use a comma. The dictionary copied for the schema is the Drive file `11pXLw_0D0hHVS8fiC8cv2dPX39vpuOH1`. The schema was relaxed where the files differ from the dictionary text: hyphenated municipality names and `Não Informado` as a direction are accepted, and the patterns for `regional`, `delegacia` and `uop` are off because those fields hold values such as `NPF/DEL06-MT`, `SEOP-AP` and `UniPRF`. With that, every row passes.

Municipality match by year, on normalized name plus UF (`PRF_accidents_shape.json`, 25.0 s, peak 447.0 MiB):

| Year | Rows   | Matched | Rate   |
| ---- | ------ | ------- | ------ |
| 2022 | 64,606 | 64,390  | 99.67% |
| 2023 | 67,766 | 67,545  | 99.67% |
| 2024 | 73,202 | 72,938  | 99.64% |
| 2025 | 72,529 | 72,314  | 99.70% |

The 11 pairs with no IBGE match. Most are an older or differently spelled name of a municipality that exists:

| PRF name                  | UF  | Rows |
| ------------------------- | --- | ---- |
| SANTO ANTONIO DO LEVERGER | MT  | 376  |
| MUQUEM DE SAO FRANCISCO   | BA  | 98   |
| ACU                       | RN  | 89   |
| FORTALEZA DO TABOCAO      | TO  | 72   |
| BELEM DE SAO FRANCISCO    | PE  | 68   |
| SANTA TERESINHA           | BA  | 59   |
| GOVERNADOR EDISON LOBAO   | MA  | 55   |
| POXOREO                   | MT  | 40   |
| ARES                      | RN  | 38   |
| AUGUSTO SEVERO            | RN  | 20   |
| SAO LUIZ                  | RR  | 1    |

Weather condition per occurrence, as normalized by the check (accents and punctuation removed):

| Value           | Rows    |
| --------------- | ------- |
| CEU-CLARO       | 175,036 |
| NUBLADO         | 43,059  |
| CHUVA           | 27,688  |
| SOL             | 15,846  |
| GAROACHUVISCO   | 9,971   |
| IGNORADO        | 3,690   |
| NEVOEIRONEBLINA | 2,350   |
| VENTO           | 449     |
| GRANIZO         | 9       |
| NEVE            | 5       |

### INMET automatic stations

Encoding `latin-1`, separator `;`, decimal comma. Eight preamble lines, then the observation header. The preamble carries region, UF, station name, WMO code, latitude, longitude, altitude and foundation date.

| Year | Stations | Rows      | Unpacked  | Zip       | Zip sha256                                                         |
| ---- | -------- | --------- | --------- | --------- | ------------------------------------------------------------------ |
| 2022 | 567      | 4,948,920 | 354.7 MiB | 86.2 MiB  | `292d997e0589486404827055f887327732f11d0bed9b5507952e6cad9bea286b` |
| 2023 | 567      | 4,966,920 | 396.3 MiB | 102.1 MiB | `b17391392cc1219151977cc2c46a7ab24368d821fd780311da9fff62a627bfd8` |
| 2024 | 565      | 4,962,960 | 386.7 MiB | 98.0 MiB  | `0a7f89de57427f79b6f82943b2f7f2e932202d9253e34bf25629ed088d108ae7` |
| 2025 | 594      | 5,020,248 | 359.2 MiB | 86.7 MiB  | `14988d0b736ba969b48881589f602f3a6d7e97b95bd1de934456851fdac2cb89` |

Observation columns the parser expects: `Data` (`YYYY/MM/DD`), `Hora UTC` (`HHMM UTC`), `PRECIPITAÇÃO TOTAL, HORÁRIO (mm)`, station-level and previous-hour pressure, global radiation, dry-bulb and dew-point temperature plus their previous-hour max and min, previous-hour max and min relative humidity, `UMIDADE RELATIVA DO AR, HORARIA (%)`, and hourly wind direction, gust and speed. All 2,293 files carry the same header. The station count is not stable: 565 in 2024, 594 in 2025.

Precipitation gaps (`INMET_weather_shape.json`, 1 min 47 s, peak 119.9 MiB). A station-hour counts as missing when the precipitation cell is empty:

| Year | Station-hours | Missing   | Rate   | Files with no value | Files missing over half |
| ---- | ------------- | --------- | ------ | ------------------- | ----------------------- |
| 2022 | 4,948,920     | 1,791,746 | 36.20% | 41                  | 163                     |
| 2023 | 4,966,920     | 1,104,499 | 22.24% | 28                  | 70                      |
| 2024 | 4,962,960     | 1,304,009 | 26.27% | 43                  | 86                      |
| 2025 | 5,020,248     | 1,987,706 | 39.59% | 109                 | 109                     |

"Files missing over half" includes the files with no value.

### IBGE

The localities API returned 5,571 municipalities. The mesh download wrote 5,570 files (53.8 MiB) and lists five failures:

| Code    | Result                    |
| ------- | ------------------------- |
| 2412807 | HTTP 522                  |
| 3108552 | HTTP 522                  |
| 3523602 | HTTP 522                  |
| 4305405 | HTTP 522                  |
| 5101837 | HTTP 500 after 5 attempts |

`downloaded_count` on that run is 5,566 and `total_codes` is 5,571. The stats re-read finds 5,570 files, so the four HTTP 522 codes already had a file from an earlier run. The one municipality with no mesh is 5101837, which the API answered with HTTP 500 on every attempt.

## Emulator, dbt and Evidence

Checked at 2026-11-27T14:35:52Z (`AWS_emulator.json`), on emulator build 1.0.611:

| Client                           | Result                                |
| -------------------------------- | ------------------------------------- |
| boto3 put and get of `hello.txt` | succeeded                             |
| ClickHouse `s3()` on that object | succeeded, 1 row, 0.23 s              |
| Dagster `S3PickleIOManager`      | succeeded                             |
| Year Parquet `put_object`        | HTTP 413 on 2022, 2023, 2024 and 2025 |

The note recorded with that run: the emulator limits `put_object` to 16 MiB, a bucket to 64 MiB, and all buckets together to 128 MiB (aws/aws-emulator issues 67 and 73). The pickle the IO manager writes is not Parquet, so ClickHouse was not asked to read a Dagster object. The emulator package is installed from the AWS LTS `latest` URL at image build time, the only one AWS serves: a versioned URL answered HTTP 403 on 2026-11-26. The build these results came from reported version 1.0.611, release date 2026.11.25.

dbt, at 2026-11-27T13:56:38Z: debug and build succeeded, notes empty. ClickHouse in the spike compose is `clickhouse/clickhouse-server:24.8-alpine`.

Evidence, at 2026-11-27T13:56:43Z: validate, the ClickHouse mart, the Parquet reader and ClickHouse `file()` all succeeded, notes empty. The mart query is one SQL statement. The Parquet page starts `node read_parquet.mjs` on port 18787 and then reads those rows with ClickHouse `url()`. That is the more moving parts of the two.

## Alignment left open for ADR-0009

Coordinates exist on PRF occurrences and on the INMET station preamble, so a nearest-station rule can be tried. No PRF row lacks coordinates. The distance limit, the match rate, and the share of hours with no station were not measured.

INMET hours are labelled UTC on every file. PRF times are local clock times with no offset in the file. A conversion rule has to state the offset per place. Treating every PRF clock as UTC−3 is not supported by the files.

Municipality matching on normalized name plus UF covers 99.67% of the rows. The rule is name plus UF, never the name alone, because names repeat across states. The 11 unmatched pairs need an alias table, and the unmatched share is the quality check the design asks for.

`condicao_metereologica` has ten values, two of them rain (`CHUVA`, `GAROACHUVISCO`). It can cross-check a weather join. It is not the exposure. The exposure column is `PRECIPITAÇÃO TOTAL, HORÁRIO (mm)`. It is empty in 31.1% of station-hours, between 22% and 40% depending on the year, and an empty cell is not zero rain.

The station set changes by year (565 to 594 files). A station-to-municipality map has to be built per year, not once.

## Decisions

Keep Brazil 2022–2025, as in ADR-0001. The unpacked sources fit on disk and the downloads finished. No check went above 447.0 MiB while reading one file at a time; a later phase that loads every station file at once still has to watch memory.

Do not adopt the AWS Emulator as the local lake in ADR-0008. Small S3 calls work from boto3, from Dagster's S3 IO manager, and from ClickHouse `s3()`. A year of INMET Parquet does not upload. SeaweedFS is the candidate: its container is in the spike stack, and the A6 checks have not been run against it. The stand-in is undecided until that run and a superseding ADR.

The ClickHouse dbt adapter can build and test a mart of this shape. Evidence can read that mart and a Parquet file. The real mart, the station join and the time-zone rule wait for ADR-0009.
