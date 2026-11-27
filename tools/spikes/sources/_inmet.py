import pandas as pd
import re

from pathlib import Path
from typing import Optional

from _utils import _date, _clean_str, _float

INMET_WEATHER_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "brazil"
    / "INMET"
    / "weather"
)
INMET_FILE = re.compile(
    r"^(?:INMET_)?[A-Z]{1,2}_[A-Z]{2}_(?P<code>[A-Z]\d{3})_.+\.csv$",
    re.IGNORECASE,
)


WEATHER_URL_TEMPLATE = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
DEFAULT_YEARS = (2022, 2023, 2024, 2025)
DEFAULT_USER_AGENT = "inmet-weather-downloader/1.0"
RETRIABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 300  # seconds
CHUNK = 1024 * 1024
PROGRESS_EVERY = 10.0  # seconds between progress lines


class YearError(Exception):
    """A year cannot be processed; the message says why."""


def check_station_data(md: dict) -> bool:
    required = [
        "REGIAO:",
        "UF:",
        "ESTACAO:",
        "CODIGO (WMO):",
        "LATITUDE:",
        "LONGITUDE:",
        "ALTITUDE:",
        "DATA DE FUNDACAO:",
    ]

    missing = []
    invalid = []
    for k in required:
        if k not in list(md.keys()):
            missing.append(k)
        if md.get(k) is None:
            invalid.append(k)

    if len(missing) > 0:
        print(f"WARN: station data is missing keys: {missing}")
    if len(invalid) > 0:
        print(f"WARN: station data has invalid values: {invalid}")

    return len(missing) == 0 and len(invalid) == 0


def format_station_data(md: list[dict]) -> Optional[dict]:
    obj = {r["key"]: r["value"] for r in md}

    if not check_station_data(obj):
        return None

    f_date = _date(obj.get("DATA DE FUNDACAO:"), format="%d/%m/%y")

    return dict(
        region=_clean_str(obj.get("REGIAO:"), transform="upper"),
        uf=_clean_str(obj.get("UF:"), transform="upper"),
        station=_clean_str(obj.get("ESTACAO:"), transform="upper"),
        wmo_code=_clean_str(obj.get("CODIGO (WMO):"), transform="upper"),
        latitude=_float(obj.get("LATITUDE:")),
        longitude=_float(obj.get("LONGITUDE:")),
        altitude=_float(obj.get("ALTITUDE:")),
        foundation_date=f_date.isoformat() if f_date else None,
    )


TEXT_COLUMNS = {"Data", "Hora UTC"}


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
    "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)",
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
    "description": "INMET Weather observations by station and hour",
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
            "type": ["number", "null"],
            "description": "Total precipitation in mm observed within the hour",
            "minimum": 0,
        },
        "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)": {
            "type": ["number", "null"],
            "description": "Atmospheric pressure in mB observed within the hour",
        },
        "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB)": {
            "type": ["number", "null"],
            "description": "Maximum atmospheric pressure in mB observed within the hour",
        },
        "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB)": {
            "type": ["number", "null"],
            "description": "Minimum atmospheric pressure in mB observed within the hour",
        },
        "RADIACAO GLOBAL (Kj/m²)": {
            "type": ["number", "null"],
            "description": "Global radiation in Kj/m² observed within the hour",
        },
        "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)": {
            "type": ["number", "null"],
            "description": "Air temperature in °C observed within the hour",
        },
        "TEMPERATURA DO PONTO DE ORVALHO (°C)": {
            "type": ["number", "null"],
            "description": "Dew temperature in °C observed within the hour",
        },
        "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)": {
            "type": ["number", "null"],
            "description": "Maximum air temperature in °C observed within the hour",
        },
        "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)": {
            "type": ["number", "null"],
            "description": "Minimum air temperature in °C observed within the hour",
        },
        "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)": {
            "type": ["number", "null"],
            "description": "Maximum dew temperature in °C observed within the hour",
        },
        "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)": {
            "type": ["number", "null"],
            "description": "Minimum dew temperature in °C observed within the hour",
        },
        "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)": {
            "type": ["number", "null"],
            "description": "Maximum relative humidity in % observed within the hour",
        },
        "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)": {
            "type": ["number", "null"],
            "description": "Minimum relative humidity in % observed within the hour",
        },
        "UMIDADE RELATIVA DO AR, HORARIA (%)": {
            "type": ["number", "null"],
            "description": "Relative humidity in % observed within the hour",
        },
        "VENTO, DIREÇÃO HORARIA (gr) (° (gr))": {
            "type": ["number", "null"],
            "description": "Wind direction in gr observed within the hour",
        },
        "VENTO, RAJADA MAXIMA (m/s)": {
            "type": ["number", "null"],
            "description": "Maximum wind speed in m/s observed within the hour",
        },
        "VENTO, VELOCIDADE HORARIA (m/s)": {
            "type": ["number", "null"],
            "description": "Wind speed in m/s observed within the hour",
        },
        # Metadata columns
        "YEAR": {"type": "integer", "description": "Year of observation"},
        "REGIAO:": {
            "type": "string",
            "description": "Station region acronym",
            "minLength": 1,
            "maxLength": 2,
            "pattern": r"^[A-Z]{1,2}$",
        },
        "UF:": {
            "type": "string",
            "description": "Station state acronym",
            "minLength": 2,
            "maxLength": 2,
            "pattern": r"^[A-Z]{2}$",
        },
        "ESTACAO:": {"type": "string", "description": "Station name, in pt-BR"},
        "CODIGO (WMO):": {
            "type": "string",
            "description": "WMO code of the station",
            "minLength": 4,
            "maxLength": 4,
            "pattern": r"^[A-Z]\d{3}$",
        },
        "LATITUDE:": {
            "type": "number",
            "description": "Latitude of the station",
            "minimum": -90,
            "maximum": 90,
        },
        "LONGITUDE:": {
            "type": "number",
            "description": "Longitude of the station",
            "minimum": -180,
            "maximum": 180,
        },
        "ALTITUDE:": {"type": "number", "description": "Altitude of the station"},
        "DATA DE FUNDACAO:": {
            "type": "string",
            "description": "Station foundation date in DD/MM/YY format",
            "pattern": r"^\d{2}/\d{2}/\d{2}$",
        },
    },
    "required": BASE_COLUMNS,
    "additionalProperties": False,
}
