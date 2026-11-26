SELECT 
    municipality_id,
    observed_hour,
    count()         AS rows_in_grain
FROM {{ ref("municipality_hour") }}
GROUP BY municipality_id, observed_hour
HAVING rows_in_grain > 1