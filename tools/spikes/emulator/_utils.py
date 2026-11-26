from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
STG_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "stg" / "brazil"

INMET_WEATHER_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "brazil"
    / "INMET"
    / "weather"
)


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
