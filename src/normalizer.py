from __future__ import annotations

from typing import Any

from src.models import ExtractionRequest, ExtractionResponse, Metric


def normalize(
    request: ExtractionRequest,
    metrics: list[Metric],
    errors: list[str] | None = None,
    template: dict[str, Any] | None = None,
) -> ExtractionResponse:
    """Build a standardized response from extraction results.

    If a template is provided its default_category and default_unit are applied
    to any metric that doesn't already have those fields set.
    """
    if template:
        default_category = template.get("default_category", "")
        default_unit = template.get("default_unit", "")
        patched: list[Metric] = []
        for m in metrics:
            patched.append(
                Metric(
                    metric_name=m.metric_name,
                    metric_value=m.metric_value,
                    metric_unit=m.metric_unit or default_unit,
                    period=m.period,
                    category=m.category or default_category,
                )
            )
        metrics = patched

    confidence = 1.0
    if not metrics:
        confidence = 0.0
    elif len(metrics) < 3:
        confidence = 0.7  # low metric count suggests partial extraction

    return ExtractionResponse(
        source_email=request.source_email,
        source_subject=request.source_subject,
        source_date=str(request.source_date) if request.source_date else "",
        source_filename=request.filename,
        metrics=metrics,
        confidence=confidence,
        errors=errors or [],
    )
