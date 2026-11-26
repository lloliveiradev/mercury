{{ config(
    materialized="table",
    engine="MergeTree()",
    order_by=["municipality_id", "observed_hour"],
) }}

WITH observations AS (
    SELECT 
        municipality_id,
        uf,
        toDateTime(observed_hour)                                       AS observed_hour,
        accidents,
        toFloat32OrNull(nullIf(trim(toString(precipitation_mm)), ''))   AS precipitation_mm
    FROM {{ ref("hour_observations") }}
)
SELECT
    CAST(municipality_id AS UInt32)                     AS municipality_id,
    CAST(uf AS LowCardinality(String))                  AS uf,
    observed_hour,
    CAST(sum(accidents) AS UInt32)                      AS accident_count,
    any(precipitation_mm)                               AS precipitation_mm
FROM observations
GROUP BY municipality_id, uf, observed_hour