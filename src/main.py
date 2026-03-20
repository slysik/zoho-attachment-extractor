from __future__ import annotations

import hashlib
import hmac
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

from src.config import settings
from src.extractors.router import route_extraction, supported_extensions
from src.models import ExtractionRequest, ExtractionResponse
from src.normalizer import normalize
from src.templates.registry import registry
from src.zoho_client import zoho_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await zoho_client.close()


app = FastAPI(title="Zoho Email Attachment Extractor", version="0.1.0", lifespan=lifespan)


def _verify_webhook_secret(x_zoho_signature: str | None) -> None:
    """Validate the X-Zoho-Signature header if WEBHOOK_SECRET is configured."""
    if not settings.webhook_secret:
        return  # secret not configured — open access (dev mode)
    if not x_zoho_signature:
        raise HTTPException(status_code=401, detail="Missing X-Zoho-Signature header")
    # Zoho Flow sends HMAC-SHA256(secret, secret) as a shared-secret token check.
    expected = hmac.new(
        settings.webhook_secret.encode(),
        settings.webhook_secret.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(x_zoho_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract_from_upload(
    file: UploadFile = File(...),
    source_email: str = Form(""),
    source_subject: str = Form(""),
    source_date: str = Form(""),
    x_zoho_signature: str | None = Header(default=None),
):
    """Extract metrics from an uploaded file (multipart form).

    This is the primary endpoint called by Zoho Flow via webhook.
    Flow uploads the attachment directly along with email metadata.
    """
    _verify_webhook_secret(x_zoho_signature)

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    if ext not in supported_extensions():
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    request = ExtractionRequest(
        source_email=source_email,
        source_subject=source_subject,
        source_date=source_date if source_date else None,
        filename=filename,
    )

    # Apply template hints (default category/unit) if a template matches
    template = registry.match(subject=source_subject, filename=filename)

    # Save upload to temp file for extraction
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    errors: list[str] = []
    try:
        metrics = route_extraction(tmp_path)
    except Exception as e:
        logger.exception("Extraction failed for %s", filename)
        errors.append(str(e))
        metrics = []
    finally:
        tmp_path.unlink(missing_ok=True)

    return normalize(request, metrics, errors, template=template)


@app.post("/extract/url", response_model=ExtractionResponse)
async def extract_from_url(
    request: ExtractionRequest,
    x_zoho_signature: str | None = Header(default=None),
):
    """Extract metrics from a file reachable via a direct download URL.

    Zoho Flow can call this when it has a public/pre-signed URL for the attachment.
    """
    _verify_webhook_secret(x_zoho_signature)

    if not request.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    ext = Path(request.filename).suffix.lower()
    if ext not in supported_extensions():
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    template = registry.match(subject=request.source_subject, filename=request.filename)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    errors: list[str] = []
    try:
        await zoho_client.download_url(request.file_url, tmp_path)
        metrics = route_extraction(tmp_path)
    except Exception as e:
        logger.exception("URL extraction failed for %s", request.filename)
        errors.append(str(e))
        metrics = []
    finally:
        tmp_path.unlink(missing_ok=True)

    return normalize(request, metrics, errors, template=template)


@app.post("/extract/workdrive", response_model=ExtractionResponse)
async def extract_from_workdrive(
    request: ExtractionRequest,
    x_zoho_signature: str | None = Header(default=None),
):
    """Extract metrics from a file already in Zoho WorkDrive.

    Zoho Flow can call this with the WorkDrive file ID instead of uploading.
    The service downloads the file, extracts metrics, and moves it to processed/failed.
    """
    _verify_webhook_secret(x_zoho_signature)

    if not request.workdrive_file_id:
        raise HTTPException(status_code=400, detail="workdrive_file_id is required")

    ext = Path(request.filename).suffix.lower()
    if ext not in supported_extensions():
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    template = registry.match(subject=request.source_subject, filename=request.filename)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    errors: list[str] = []
    metrics = []
    try:
        await zoho_client.download_file(request.workdrive_file_id, tmp_path)
        metrics = route_extraction(tmp_path)

        # Write to Zoho Sheet
        response = normalize(request, metrics, errors, template=template)
        if response.metrics:
            rows = [
                {
                    "Source Email": response.source_email,
                    "Subject": response.source_subject,
                    "Date": response.source_date,
                    "Filename": response.source_filename,
                    "Metric": m.metric_name,
                    "Value": m.metric_value,
                    "Unit": m.metric_unit,
                    "Period": m.period,
                    "Category": m.category,
                }
                for m in response.metrics
            ]
            await zoho_client.append_sheet_rows(rows)

        # Move to processed
        if settings.workdrive_processed_folder_id:
            await zoho_client.move_file(
                request.workdrive_file_id, settings.workdrive_processed_folder_id
            )

        return response

    except Exception as e:
        logger.exception("WorkDrive extraction failed for %s", request.filename)
        errors.append(str(e))
        metrics = []
        # Move to failed
        if settings.workdrive_failed_folder_id:
            try:
                await zoho_client.move_file(
                    request.workdrive_file_id, settings.workdrive_failed_folder_id
                )
            except Exception:
                logger.exception("Failed to move file to failed folder")
        return normalize(request, metrics, errors, template=template)
    finally:
        tmp_path.unlink(missing_ok=True)
