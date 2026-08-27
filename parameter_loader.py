"""Зареждане на динамични стойности за параметри чрез SQL заявки.

Поддържа два формата за описание на източник:
    1. Директно "query" поле:
        {"name": "warehouse", "query": "SELECT ID as value, Name as label FROM Objects"}

    2. Гъвкав "source" формат (препоръчителен за бъдеще разширение):
        {"name": "warehouse", "source": {"type": "sql", "query": "SELECT ..."}}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from db_config import MSSQL_CONN_STR


@dataclass
class LoadResult:
    """Резултат от зареждане на параметър."""
    is_select_options: bool  # True за type=select -> връща списък с value/label
    data: Any  # list за select, dict с 'value' за другите


def _extract_query_config(param_def: dict) -> str | None:
    """Извлича SQL заявката от параметъра, независимо от формата.

    Поддържа:
      - param_def["query"]
      - param_def["source"]["query"] (при source.type == "sql")
    """
    if isinstance(param_def, dict):
        direct_query = param_def.get("query")
        if isinstance(direct_query, str) and direct_query.strip():
            return direct_query.strip()

        source = param_def.get("source")
        if isinstance(source, dict):
            if source.get("type", "sql") == "sql":
                src_query = source.get("query")
                if isinstance(src_query, str) and src_query.strip():
                    return src_query.strip()

    return None


def has_dynamic_source(param_def: dict) -> bool:
    """Проверява дали параметърът има динамичен източник (query или source.sql)."""
    return _extract_query_config(param_def) is not None


def _coerce_sql_params(params: dict) -> dict:
    """Подготвя стойностите за SQLAlchemy bind параметри."""
    coerced = {}
    for key, value in params.items():
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    coerced[key] = datetime.strptime(value, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                coerced[key] = value
        else:
            coerced[key] = value
    return coerced


def _get_engine(connection_string: str | None = None) -> Engine:
    conn_str = connection_string or MSSQL_CONN_STR
    return create_engine(conn_str)


def _row_to_value_label(row: Any) -> dict:
    """Преобразува един ред от резултатна таблица към {value, label} речник."""
    if isinstance(row, dict):
        value = row.get("value")
        label = row.get("label", value)
    else:
        if hasattr(row, "_mapping"):
            mapping = dict(row._mapping)
            value = mapping.get("value")
            label = mapping.get("label", value)
        else:
            try:
                cols = list(row.keys())
            except Exception:
                cols = None
            if cols and "value" in cols:
                idx_val = cols.index("value")
                idx_label = cols.index("label") if "label" in cols else idx_val
                value = row[idx_val]
                label = row[idx_label]
            else:
                value = row[0]
                label = row[1] if len(row) > 1 else value

    return {"value": value, "label": label if label is not None else ""}


def _row_to_single_value(row: Any) -> Any:
    """Извлича 'value' колоната (или първата колона) от един ред."""
    if isinstance(row, dict):
        return row.get("value")
    if hasattr(row, "_mapping"):
        return dict(row._mapping).get("value")
    try:
        cols = list(row.keys())
        if cols and "value" in cols:
            return row[cols.index("value")]
    except Exception:
        pass
    return row[0] if row is not None else None


def load_parameter_values(
    param_def: dict,
    bind_params: dict | None = None,
    connection_string: str | None = None,
) -> LoadResult:
    """Изпълнява SQL заявката за даден параметър и връща унифициран резултат.

    Args:
        param_def: Дефиниция на параметър от JSON-a (с 'query' или 'source' поле).
        bind_params: Стойности на други параметри (например {'warehouse': 12}),
            които ще се използват като bind параметри в SQL заявката.
        connection_string: Лично connection string; по подразбиране MSSQL_CONN_STR.

    Returns:
        LoadResult със data:
          - за type == 'select':  list[dict] = [{"value": ..., "label": ...}, ...]
          - за всички останали:   dict = {"value": ...}
    """
    query = _extract_query_config(param_def)
    if not query:
        raise ValueError("Параметърът няма зададена динамична SQL заявка (query/source).")

    param_type = param_def.get("type", "text")
    engine = _get_engine(connection_string)
    bind = _coerce_sql_params(bind_params or {})

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), bind)
            rows = list(result.fetchall())
    except Exception as exc:
        raise RuntimeError(f"Грешка при изпълнение на заявка за параметър: {exc}") from exc

    if param_type == "select":
        options = [_row_to_value_label(r) for r in rows]
        return LoadResult(is_select_options=True, data=options)

    if rows:
        value = _row_to_single_value(rows[0])
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            value = value.isoformat()
        return LoadResult(is_select_options=False, data={"value": value})

    return LoadResult(is_select_options=False, data={"value": None})
