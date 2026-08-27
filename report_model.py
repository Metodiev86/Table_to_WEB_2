"""Модел на справка с optional параметри."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parameter_resolver import defaults_from_definitions, validate_parameters

METADATA_DIR = Path(__file__).parent / "metadata"
SQL_QUERIES_DIR = Path(__file__).parent / "sql_queries"


@dataclass
class ReportParameter:
    name: str
    label: str
    type: str
    default: Any = None
    options: list | None = None
    query: str | None = None
    source: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ReportParameter:
        return cls(
            name=data["name"],
            label=data.get("label", data["name"]),
            type=data.get("type", "text"),
            default=data.get("default"),
            options=data.get("options"),
            query=data.get("query"),
            source=data.get("source"),
        )

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.options:
            result["options"] = self.options
        if self.query:
            result["query"] = self.query
        if self.source:
            result["source"] = self.source
        return result


@dataclass
class Report:
    name: str
    title: str
    sql: str
    columns: list | None = None
    parameters: list[ReportParameter] = field(default_factory=list)
    category: str = "Други"

    @property
    def has_parameters(self) -> bool:
        return len(self.parameters) > 0

    def parameter_definitions(self) -> list[dict]:
        return [p.to_dict() for p in self.parameters]

    def validate_parameters(self, raw_params: dict | None) -> dict:
        return validate_parameters(self.parameter_definitions(), raw_params)

    def default_parameters(self) -> dict:
        return defaults_from_definitions(self.parameter_definitions())

    @classmethod
    def load(cls, report_name: str) -> Report | None:
        metadata = _load_metadata(report_name)
        sql_text = _load_sql(report_name)
        if not sql_text and not metadata:
            return None

        param_defs = metadata.get("parameters") or []
        parameters = [ReportParameter.from_dict(p) for p in param_defs]

        return cls(
            name=report_name,
            title=metadata.get("title") or report_name,
            sql=sql_text or "",
            columns=metadata.get("columns"),
            parameters=parameters,
            category=metadata.get("category", "Други"),
        )


def _load_metadata(report_name: str) -> dict:
    metadata_file = METADATA_DIR / f"{report_name}.json"
    if not metadata_file.exists():
        return {}
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _load_sql(report_name: str) -> str | None:
    sql_file = SQL_QUERIES_DIR / f"{report_name}.sql"
    if not sql_file.exists():
        return None
    return sql_file.read_text(encoding="utf-8")


def save_report_metadata(report_name: str, category: str, parameters: list[dict] | None = None, title: str | None = None):
    """Записва/обновява metadata за справка."""
    metadata_file = METADATA_DIR / f"{report_name}.json"
    data = _load_metadata(report_name)
    data["category"] = category
    if title:
        data["title"] = title
    if parameters is not None:
        data["parameters"] = parameters
    metadata_file.parent.mkdir(exist_ok=True)
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
