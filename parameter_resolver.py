"""Разрешаване на default стойности и валидация на параметри за справки."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any


TODAY_PATTERN = re.compile(r"^today(?:([+-])(\d+))?$", re.IGNORECASE)


def resolve_default(value: Any, param_type: str) -> Any:
    """Преобразува default стойност (напр. today-90) към конкретна стойност."""
    if value is None:
        return None

    if param_type == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, str):
            m = TODAY_PATTERN.match(value.strip())
            if m:
                base = date.today()
                if m.group(1) and m.group(2):
                    delta = int(m.group(2))
                    if m.group(1) == "-":
                        base = base - timedelta(days=delta)
                    else:
                        base = base + timedelta(days=delta)
                return base.isoformat()
            return value
        return str(value)

    if param_type == "number":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and value.strip() != "":
            return float(value) if "." in value else int(value)
        return value

    if param_type == "checkbox":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    return value


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Невалидна дата: {value!r}")


def validate_parameter_value(param_def: dict, raw_value: Any) -> Any:
    """Валидира и нормализира една стойност спрямо дефиницията на параметъра."""
    name = param_def.get("name", "?")
    param_type = param_def.get("type", "text")

    if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
        if "default" in param_def:
            return resolve_default(param_def["default"], param_type)
        raise ValueError(f"Липсва задължителен параметър: {name}")

    if param_type == "date":
        return _parse_date(raw_value).isoformat()

    if param_type == "number":
        try:
            num = float(raw_value)
            if num == int(num):
                return int(num)
            return num
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Параметър '{name}' трябва да е число") from exc

    if param_type == "checkbox":
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw_value)

    if param_type == "select":
        text = str(raw_value)
        options = param_def.get("options") or []
        has_dynamic = (
            isinstance(param_def.get("query"), str) and param_def["query"].strip() != ""
        ) or (
            isinstance(param_def.get("source"), dict)
            and param_def["source"].get("type", "sql") == "sql"
            and isinstance(param_def["source"].get("query"), str)
            and param_def["source"]["query"].strip() != ""
        )
        if options:
            allowed = {str(opt.get("value", opt) if isinstance(opt, dict) else opt) for opt in options}
            if allowed and text not in allowed:
                raise ValueError(f"Невалидна стойност за '{name}': {text}")
        elif not has_dynamic:
            raise ValueError(f"Липсват опции за параметър '{name}' (нито статични options, нито динамичен query/source)")
        return text

    return str(raw_value)


def validate_parameters(param_defs: list[dict], raw_params: dict | None) -> dict:
    """Валидира целия речник с параметри и връща нормализирани стойности за SQL."""
    raw_params = raw_params or {}
    validated: dict[str, Any] = {}

    for param_def in param_defs:
        name = param_def["name"]
        validated[name] = validate_parameter_value(param_def, raw_params.get(name))

    return validated


def defaults_from_definitions(param_defs: list[dict]) -> dict:
    """Връща default стойности за всички параметри."""
    result = {}
    for param_def in param_defs:
        if "default" in param_def:
            result[param_def["name"]] = resolve_default(
                param_def["default"], param_def.get("type", "text")
            )
    return result
