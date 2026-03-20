from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Metric(BaseModel):
    metric_name: str
    metric_value: float
    metric_unit: str = ""
    period: str = ""
    category: str = ""


class ExtractionRequest(BaseModel):
    """Incoming webhook payload from Zoho Flow."""

    source_email: str = ""
    source_subject: str = ""
    source_date: date | None = None
    filename: str
    file_url: str = ""
    workdrive_file_id: str = ""


class ExtractionResponse(BaseModel):
    """Standardized output returned to Zoho Flow."""

    source_email: str = ""
    source_subject: str = ""
    source_date: str = ""
    source_filename: str = ""
    metrics: list[Metric] = Field(default_factory=list)
    confidence: float = 1.0
    errors: list[str] = Field(default_factory=list)
