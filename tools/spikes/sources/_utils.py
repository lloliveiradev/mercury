import re
import unicodedata

from datetime import date, time, datetime
from pathlib import Path
from typing import Literal, Optional, Any

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
STG_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "stg" / "brazil"


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


def _slugify(text: str, separator: Optional[str] = None) -> str:
    if not separator:
        separator = "-"
    return _clean_str(text).replace(" ", separator)


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
