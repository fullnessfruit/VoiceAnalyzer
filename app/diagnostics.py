"""Bounded exception details shared by local audit rows and broker releases."""

from __future__ import annotations

import json


def one_line(value: object, limit: int = 500) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return " ".join(str(value).split())[:limit]


def error_details(error: BaseException) -> list[dict]:
    """Preserve explicit causes without traceback noise or recursive cycles."""
    rows = []
    seen = set()
    while error is not None and id(error) not in seen and len(rows) < 6:
        seen.add(id(error))
        row = {"type": type(error).__name__, "message": one_line(error)}
        diagnostics = getattr(error, "diagnostics", None)
        if diagnostics:
            row["diagnostics"] = diagnostics
        rows.append(row)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return rows


def error_summary(error: BaseException, limit: int = 2000) -> str:
    rows = error_details(error)
    messages = " <- ".join(f"{row['type']}: {row['message']}" for row in rows)
    details = [row["diagnostics"] for row in rows if "diagnostics" in row]
    if details:
        messages += " | " + json.dumps(details, ensure_ascii=False, separators=(",", ":"))
    return one_line(messages, limit)
