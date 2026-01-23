from __future__ import annotations


def safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def format_mmss(sec: int) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"



