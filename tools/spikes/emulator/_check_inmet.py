import io
import pandas as pd
import sys

from pathlib import Path
from typing import Optional

from _utils import INMET_WEATHER_DIR, STG_DATA_DIR

BASE_COLUMNS = [
    "Data",
    "Hora UTC",
    "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)",
    "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)",
    "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB)",
    "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB)",
    "RADIACAO GLOBAL (Kj/m²)",
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)",
    "TEMPERATURA DO PONTO DE ORVALHO (°C)",
    "TEMPERATURA MÁXIMANA HORA ANT. (AUT) (°C)",
    "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)",
    "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)",
    "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)",
    "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)",
    "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)",
    "UMIDADE RELATIVA DO AR, HORARIA (%)",
    "VENTO, DIREÇÃO HORARIA (gr) (° (gr))",
    "VENTO, RAJADA MAXIMA (m/s)",
    "VENTO, VELOCIDADE HORARIA (m/s)",
]
TEXT_COLUMNS = {"Data", "Hora UTC"}
STATION_COLUMNS = [
    "REGIAO:",
    "UF:",
    "ESTACAO:",
    "CODIGO (WMO):",
    "LATITUDE:",
    "LONGITUDE:",
    "ALTITUDE:",
    "DATA DE FUNDACAO:",
]

INMET_WEATHER_SCHEMA = {
    "title": "INMET Weather",
    "description": "INMET Weather data",
    "type": "object",
    "properties": {
        "Data": {
            "type": "string",
            "description": "Date of observation in YYYY/MM/DD format",
            "pattern": r"^\d{4}/\d{2}/\d{2}$",
        },
        "Hora UTC": {
            "type": "string",
            "description": "Hour of observation in UTC time (HHMM UTC)",
            "pattern": r"^\d{4} UTC$",
        },
        "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)": {
            "type": "number",
            "description": "Total precipitation in mm observed within the hour",
            "minimum": 0,
        },
        "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)": {
            "type": "number",
            "description": "Atmospheric pressure in mB observed within the hour",
        },
        "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB)": {
            "type": "number",
            "description": "Maximum atmospheric pressure in mB observed within the hour",
        },
        "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB)": {
            "type": "number",
            "description": "Minimum atmospheric pressure in mB observed within the hour",
        },
        "RADIACAO GLOBAL (Kj/m²)": {
            "type": ["number", "null"],
            "description": "Global radiation in Kj/m² observed within the hour",
        },
        "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)": {
            "type": "number",
            "description": "Air temperature in °C observed within the hour",
        },
        "TEMPERATURA DO PONTO DE ORVALHO (°C)": {
            "type": "number",
            "description": "Dew temperature in °C observed within the hour",
        },
        "TEMPERATURA MÁXIMANA HORA ANT. (AUT) (°C)": {
            "type": "number",
            "description": "Maximum air temperature in °C observed within the hour",
        },
        "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)": {
            "type": "number",
            "description": "Minimum air temperature in °C observed within the hour",
        },
        "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)": {
            "type": "number",
            "description": "Maximum dew temperature in °C observed within the hour",
        },
        "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)": {
            "type": "number",
            "description": "Minimum dew temperature in °C observed within the hour",
        },
        "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)": {
            "type": "number",
            "description": "Maximum relative humidity in % observed within the hour",
        },
        "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)": {
            "type": "number",
            "description": "Minimum relative humidity in % observed within the hour",
        },
        "UMIDADE RELATIVA DO AR, HORARIA (%)": {
            "type": "number",
            "description": "Relative humidity in % observed within the hour",
        },
        "VENTO, DIREÇÃO HORARIA (gr) (° (gr))": {
            "type": "number",
            "description": "Wind direction in gr observed within the hour",
        },
        "VENTO, RAJADA MAXIMA (m/s)": {
            "type": "number",
            "description": "Maximum wind speed in m/s observed within the hour",
        },
        "VENTO, VELOCIDADE HORARIA (m/s)": {
            "type": "number",
            "description": "Wind speed in m/s observed within the hour",
        },
    },
    "required": BASE_COLUMNS,
    "additionalProperties": False,
}


def _measurements(df: pd.DataFrame) -> pd.DataFrame:
    # INMET writes 0.4 as ",4". One such cell keeps the whole column as text,
    # and a later file parsed as float cannot share a Parquet column with it.
    out = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    for column in out.columns:
        if column in TEXT_COLUMNS or pd.api.types.is_numeric_dtype(out[column]):
            continue
        text = out[column].astype("string").str.strip()
        text = text.str.replace(r"^-,", "-0,", regex=True)
        text = text.str.replace(r"^,", "0,", regex=True)
        text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[column] = pd.to_numeric(text, errors="coerce")
    return out


def format_inmet_file(f: Path, year: str) -> Optional[pd.DataFrame]:
    try:
        md = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            header=None,
            nrows=8,
            names=["key", "value"],
        )
        if md.empty:
            return None
        fmt_md = {r["key"]: r["value"] for r in md.to_dict(orient="records")}

        df = pd.read_csv(
            f,
            sep=";",
            encoding="latin-1",
            decimal=",",
            thousands=".",
            skiprows=8,
            keep_default_na=False,
        )
        df = _measurements(df)

        df = df.assign(**fmt_md)
        df = df.assign(**{"YEAR": int(year)})

        cols = df.columns.tolist()
        print(cols)

        return df
    except Exception as e:
        print(f"ERROR: Error formatting INMET file {f}: {e}")
        return None


def main() -> int:
    INMET_STG_DIR = STG_DATA_DIR / "INMET" / "weather"
    INMET_STG_DIR.mkdir(parents=True, exist_ok=True)
    for d in INMET_WEATHER_DIR.iterdir():
        if not d.is_dir():
            continue

        files: list[pd.DataFrame] = []
        for f in d.glob("*.csv"):
            if not f.is_file() or f.suffix != ".csv":
                continue

            df = format_inmet_file(f, f.parent.name)
            if df is None:
                continue
            break
            # files.append(df)

            # if len(files) == 0:
            #     continue

        # df = pd.concat((f for f in files), ignore_index=True)
        # buffer = io.BytesIO()
        # df.to_parquet(buffer, index=False)

        # with open(INMET_STG_DIR / f"{d.name}.parquet", "wb") as f:
        #     f.write(buffer.getvalue())
        break
    return 0


if __name__ == "__main__":
    sys.exit(main())
