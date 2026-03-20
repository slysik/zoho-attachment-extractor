from pathlib import Path
import tempfile

import pytest
from openpyxl import Workbook

from src.extractors.excel_extractor import extract_excel


def _create_test_xlsx(rows: list[list]) -> Path:
    """Helper: write rows to a temp .xlsx and return the path."""
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tmp.name)
    tmp.close()
    return Path(tmp.name)


def test_basic_extraction():
    path = _create_test_xlsx([
        ["Name", "Value", "Unit", "Period", "Category"],
        ["Total Revenue", 1250000, "USD", "2026-02", "Sales"],
        ["Units Sold", 3400, "", "2026-02", "Sales"],
    ])
    metrics = extract_excel(path)
    path.unlink()

    assert len(metrics) == 2
    assert metrics[0].metric_name == "Total Revenue"
    assert metrics[0].metric_value == 1250000
    assert metrics[0].metric_unit == "USD"
    assert metrics[1].metric_name == "Units Sold"
    assert metrics[1].metric_value == 3400


def test_alias_headers():
    path = _create_test_xlsx([
        ["KPI", "Amount", "Currency"],
        ["Revenue", 500000, "EUR"],
    ])
    metrics = extract_excel(path)
    path.unlink()

    assert len(metrics) == 1
    assert metrics[0].metric_name == "Revenue"
    assert metrics[0].metric_unit == "EUR"


def test_fallback_two_columns():
    path = _create_test_xlsx([
        ["Something", "Other"],
        ["Clicks", 12345],
    ])
    metrics = extract_excel(path)
    path.unlink()

    assert len(metrics) == 1
    assert metrics[0].metric_name == "Clicks"
    assert metrics[0].metric_value == 12345


def test_empty_file():
    path = _create_test_xlsx([["Name", "Value"]])
    metrics = extract_excel(path)
    path.unlink()
    assert len(metrics) == 0


def test_skips_non_numeric_values():
    path = _create_test_xlsx([
        ["Name", "Value"],
        ["Revenue", 100],
        ["Note", "not a number"],
    ])
    metrics = extract_excel(path)
    path.unlink()

    assert len(metrics) == 1
    assert metrics[0].metric_name == "Revenue"
