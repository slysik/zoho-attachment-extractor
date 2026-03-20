from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from src.models import Metric


def extract_pdf(file_path: Path) -> list[Metric]:
    """Extract metrics from a PDF file.

    Strategy:
    1. Try table extraction first (structured PDFs)
    2. Fall back to regex-based KPI extraction from text
    """
    metrics: list[Metric] = []

    with pdfplumber.open(file_path) as pdf:
        # Attempt 1: extract tables
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                metrics.extend(_parse_table(table))

        # Attempt 2: regex fallback on full text
        if not metrics:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            metrics.extend(_parse_text_kpis(full_text))

    return metrics


def _parse_table(table: list[list[str | None]]) -> list[Metric]:
    """Parse a pdfplumber table into metrics."""
    if len(table) < 2:
        return []

    headers = [str(c).strip().lower() if c else "" for c in table[0]]

    # Find value column — look for numeric data in second row
    name_col = 0
    value_col = None
    for i in range(1, len(headers)):
        sample = table[1][i] if len(table[1]) > i else None
        if sample and _is_numeric(str(sample)):
            value_col = i
            break

    if value_col is None:
        return []

    metrics: list[Metric] = []
    for row in table[1:]:
        if not row or len(row) <= value_col:
            continue
        name = row[name_col]
        val_str = row[value_col]
        if not name or not val_str:
            continue
        cleaned = re.sub(r"[,$%]", "", str(val_str).strip())
        if not _is_numeric(cleaned):
            continue
        metrics.append(
            Metric(
                metric_name=str(name).strip(),
                metric_value=float(cleaned),
            )
        )

    return metrics


# Common patterns: "Total Revenue: $1,250,000" or "Revenue  1250000.00"
_KPI_PATTERN = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z &/\-]+?)[\s:]+\$?\s*"
    r"(?P<value>[\d,]+\.?\d*)\s*(?P<unit>%|USD|EUR|GBP)?",
)


def _parse_text_kpis(text: str) -> list[Metric]:
    """Regex-based extraction of key-value pairs from free text."""
    metrics: list[Metric] = []
    seen: set[str] = set()

    for match in _KPI_PATTERN.finditer(text):
        name = match.group("name").strip()
        value_str = match.group("value").replace(",", "")
        unit = match.group("unit") or ""

        if name.lower() in seen:
            continue
        seen.add(name.lower())

        try:
            value = float(value_str)
        except ValueError:
            continue

        metrics.append(Metric(metric_name=name, metric_value=value, metric_unit=unit))

    return metrics


def _is_numeric(s: str) -> bool:
    try:
        float(s.replace(",", ""))
        return True
    except ValueError:
        return False
