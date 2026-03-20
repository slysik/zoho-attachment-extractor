from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models import Metric


def extract_csv(file_path: Path) -> list[Metric]:
    """Extract metrics from a CSV file.

    Uses the same header-alias logic as the Excel extractor.
    """
    df = pd.read_csv(file_path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    col_map = _resolve_columns(df.columns.tolist())
    if "metric_name" not in col_map or "metric_value" not in col_map:
        if len(df.columns) >= 2:
            col_map = {"metric_name": df.columns[0], "metric_value": df.columns[1]}
        else:
            return []

    metrics: list[Metric] = []
    for _, row in df.iterrows():
        name = row.get(col_map["metric_name"])
        value_raw = row.get(col_map["metric_value"])
        if pd.isna(name) or pd.isna(value_raw):
            continue
        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            continue

        metrics.append(
            Metric(
                metric_name=str(name),
                metric_value=value,
                metric_unit=str(row.get(col_map.get("metric_unit", ""), "") or ""),
                period=str(row.get(col_map.get("period", ""), "") or ""),
                category=str(row.get(col_map.get("category", ""), "") or ""),
            )
        )

    return metrics


def _resolve_columns(headers: list[str]) -> dict[str, str]:
    """Map standard field names to actual column names using aliases."""
    aliases: dict[str, list[str]] = {
        "metric_name": ["metric_name", "name", "metric", "kpi"],
        "metric_value": ["metric_value", "value", "amount", "total"],
        "metric_unit": ["metric_unit", "unit", "currency"],
        "period": ["period", "date", "month", "year"],
        "category": ["category", "type", "group", "department"],
    }
    col_map: dict[str, str] = {}
    for field, names in aliases.items():
        for h in headers:
            if h in names:
                col_map[field] = h
                break
    return col_map
