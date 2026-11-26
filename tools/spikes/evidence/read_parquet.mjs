import { createServer } from 'node:http';
import { Database } from 'duckdb-async';

const file = new URL(
  './sources/parquets/INMET_weather_2022.parquet',
  import.meta.url,
).pathname;
const port = Number(process.env.PARQUET_PORT ?? 18787);

const db = await Database.create(':memory:');
const sql = `
  SELECT
    "ESTACAO:"                          AS station,
    "CODIGO (WMO):"                     AS wmo_code,
    CAST("YEAR" AS VARCHAR)             AS year,
    "Data"                              AS date,
    "Hora UTC"                          AS hour,
    "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)"  AS precipitation_mm
  FROM read_parquet('${file.replaceAll("'", "''")}')
  LIMIT 10
`;

const server = createServer(async (_req, res) => {
  try {
    const rows = await db.all(sql);
    const body = rows
      .map((row) =>
        JSON.stringify({
          station: row.station,
          wmo_code: row.wmo_code,
          year: String(row.year),
          date: row.date,
          hour: row.hour,
          precipitation_mm:
            row.precipitation_mm == null ? null : Number(row.precipitation_mm),
        }),
      )
      .join('\n');
    res.writeHead(200, { 'content-type': 'application/x-ndjson' });
    res.end(body);
  } catch (error) {
    res.writeHead(500, { 'content-type': 'text/plain' });
    res.end(error instanceof Error ? error.message : String(error));
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`parquet read_parquet on :${port}`);
});
