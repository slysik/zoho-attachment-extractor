import tempfile
from pathlib import Path

from src.extractors.csv_extractor import extract_csv


def _create_test_csv(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def test_basic_csv():
    path = _create_test_csv("Name,Value,Unit\nRevenue,500000,USD\nCost,200000,USD\n")
    metrics = extract_csv(path)
    path.unlink()

    assert len(metrics) == 2
    assert metrics[0].metric_name == "Revenue"
    assert metrics[0].metric_value == 500000
    assert metrics[1].metric_name == "Cost"


def test_csv_fallback_columns():
    path = _create_test_csv("Stuff,Numbers\nClicks,9999\n")
    metrics = extract_csv(path)
    path.unlink()

    assert len(metrics) == 1
    assert metrics[0].metric_value == 9999
