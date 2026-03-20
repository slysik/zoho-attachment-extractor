from src.extractors.pdf_extractor import _parse_text_kpis


def test_regex_kpi_extraction():
    text = """
    Monthly Sales Report - February 2026

    Total Revenue: $1,250,000.00
    Units Sold: 3,400
    Average Order Value: $367.65
    Customer Satisfaction: 92%
    """
    metrics = _parse_text_kpis(text)

    names = {m.metric_name for m in metrics}
    assert "Total Revenue" in names
    assert "Units Sold" in names
    assert "Average Order Value" in names

    revenue = next(m for m in metrics if m.metric_name == "Total Revenue")
    assert revenue.metric_value == 1250000.00


def test_regex_no_matches():
    metrics = _parse_text_kpis("No numbers here, just plain text.")
    assert len(metrics) == 0
