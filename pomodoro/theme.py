from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    bg: str
    panel: str
    fg: str
    muted: str


def theme_for_system(is_dark: bool) -> Theme:
    if is_dark:
        return Theme(bg="#0B1020", panel="#111A2E", fg="#E5E7EB", muted="#94A3B8")
    return Theme(bg="#F3F4F6", panel="#FFFFFF", fg="#111827", muted="#6B7280")


def accent_for_mode(mode: str) -> str:
    return {"work": "#E11D48", "short_break": "#22C55E", "long_break": "#3B82F6"}.get(mode, "#E11D48")



