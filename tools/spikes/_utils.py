import re
import resource
import sys
import unicodedata

from datetime import date, time, datetime
from pathlib import Path
from typing import Literal, Optional, Any

# Shared by every spike folder. Each script adds this folder to sys.path first.
SPIKES_DIR = Path(__file__).resolve().parent
DATA_DIR = SPIKES_DIR.parents[1] / "data"

OUTPUT_DIR = SPIKES_DIR / "output"
STG_DATA_DIR = DATA_DIR / "stg" / "brazil"
INMET_WEATHER_DIR = DATA_DIR / "raw" / "brazil" / "INMET" / "weather"

INMET_WEATHER_CH_STRUCT = [
    "data String",
    "hora_utc String",
    "precipitacao_total_horario_mm Float",
    "pressao_atmosferica_ao_nivel_da_estacao_horaria_mb Float",
    "pressao_atmosferica_maxna_hora_ant_aut_mb Float",
    "pressao_atmosferica_min_na_hora_ant_aut_mb Float",
    "radiacao_global_kjm2 Float",
    "temperatura_do_ar_bulbo_seco_horaria_c Float",
    "temperatura_do_ponto_de_orvalho_c Float",
    "temperatura_maxima_na_hora_ant_aut_c Float",
    "temperatura_minima_na_hora_ant_aut_c Float",
    "temperatura_orvalho_max_na_hora_ant_aut_c Float",
    "temperatura_orvalho_min_na_hora_ant_aut_c Float",
    "umidade_rel_max_na_hora_ant_aut Float",
    "umidade_rel_min_na_hora_ant_aut Float",
    "umidade_relativa_do_ar_horaria Float",
    "vento_direcao_horaria_gr_gr Float",
    "vento_rajada_maxima_ms Float",
    "vento_velocidade_horaria_ms Float",
    "regiao String",
    "uf String",
    "estacao String",
    "codigo_wmo String",
    "latitude String",
    "longitude String",
    "altitude String",
    "data_de_fundacao String",
    "year Int32",
]

CHECKS_TO_PRINT = [
    "last_checked_at",
    "time_to_process",
    "peak_memory",
    "total_files",
    "total_records",
    "total_size",
]


class Blocked(Exception):
    """The server refused us (403). Retrying would only make it worse."""


class FetchError(Exception):
    """A request failed for good (permanent status or retries exhausted)."""


type Transform = Literal["upper", "lower", "title", "capitalize"]


def _clean_str(
    text: str, keep_numbers: bool = True, transform: Transform = "lower"
) -> str:
    if text is None or text == "":
        return ""

    # 1. Remove diacritics (e.g. "ação" -> "acao")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # 2. Remove special characters and punctuation
    if keep_numbers:
        text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    else:
        text = re.sub(r"[^a-zA-Z\s]", "", text)

    # 3. Standardize whitespace and lowercase
    text = re.sub(r"\s+", " ", text).strip()
    if transform == "upper":
        return text.upper()
    elif transform == "lower":
        return text.lower()
    elif transform == "title":
        return text.title()
    elif transform == "capitalize":
        return text.capitalize()


def _slugify(
    text: str,
    separator: Optional[str] = None,
    transform: Transform = "lower",
) -> str:
    if not separator:
        separator = "-"
    return _clean_str(text, transform=transform).replace(" ", separator)


def _str(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return str(value)
    except ValueError:
        return None


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    if isinstance(value, str):
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError as e:
        print(f"Error parsing float {value}: {e}")
        return None


def _int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None

    if isinstance(value, str) and not value.isdigit():
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _date(value: Any, format: str = "%Y/%m/%d") -> Optional[date]:
    if value is None or value == "":
        return None

    try:
        return datetime.strptime(value, format).date()
    except ValueError:
        return None


def _time(value: Any, format: str = "%H:%M") -> Optional[time]:
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, format).time()
    except ValueError:
        return None


def _size(size: int) -> str:
    """Human-readable size in binary units, e.g. ``12.1 KiB``."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _duration(seconds: float) -> str:
    """Human-readable duration, e.g. ``0.31 s``, ``42.5 s`` or ``1 h 02 min``."""
    if seconds < 60:
        return f"{seconds:.2f} s" if seconds < 10 else f"{seconds:.1f} s"
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)

    combined = []
    if hours > 0:
        combined.append(f"{hours} h")
    if minutes > 0:
        combined.append(f"{minutes} min")
    if secs > 0:
        combined.append(f"{secs} s")
    return " ".join(combined)


def _pct(value: float, total: float, decimals: int = 2) -> float:
    if total == 0 or value == 0:
        return 0
    return round((value / total) * 100, decimals)


def _rate(value: float, total: float, decimals: int = 2) -> float:
    if total == 0 or value == 0:
        return 0
    return round(value / total, decimals)


def _peak_memory() -> str:
    """Peak resident memory of this process so far, e.g. ``300.3 MiB``."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux reports kibibytes.
    return _size(peak if sys.platform == "darwin" else peak * 1024)
