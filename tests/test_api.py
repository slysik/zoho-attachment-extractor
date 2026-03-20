import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def _make_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Value", "Unit"])
    ws.append(["Revenue", 100000, "USD"])
    ws.append(["Cost", 50000, "USD"])
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tmp.name)
    tmp.close()
    data = Path(tmp.name).read_bytes()
    Path(tmp.name).unlink()
    return data


def test_extract_upload_xlsx():
    xlsx_bytes = _make_xlsx_bytes()
    resp = client.post(
        "/extract",
        files={"file": ("report.xlsx", io.BytesIO(xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"source_email": "test@example.com", "source_subject": "Test Report"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["metrics"]) == 2
    assert body["source_email"] == "test@example.com"
    assert body["source_filename"] == "report.xlsx"


def test_extract_upload_csv():
    csv_content = b"Name,Value\nMetricA,42\nMetricB,99\n"
    resp = client.post(
        "/extract",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    assert len(resp.json()["metrics"]) == 2


def test_unsupported_type():
    resp = client.post(
        "/extract",
        files={"file": ("doc.docx", io.BytesIO(b"fake"), "application/octet-stream")},
    )
    assert resp.status_code == 400
