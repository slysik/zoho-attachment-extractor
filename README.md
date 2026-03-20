# Zoho Email Attachment Extractor

A FastAPI service that extracts report metrics from email attachments (Excel, CSV, PDF, images) and writes them to Zoho Sheet. Designed to be called by **Zoho Flow** via webhook.

---

## Architecture

```
Zoho Flow  →  POST /extract        (multipart upload — attachment + email metadata)
           →  POST /extract/url    (JSON body with a direct download URL)
           →  POST /extract/workdrive  (JSON body with a WorkDrive file ID)
                     ↓
           Extractor (Excel / CSV / PDF / OCR)
                     ↓
           Normalizer (applies template hints)
                     ↓
           Zoho Sheet (append rows)  +  WorkDrive (move to processed/failed)
```

---

## Setup

### 1. Python environment

Requires **Python 3.11+**.

```bash
python3.11 -m pip install -e ".[dev]"
```

### 2. Zoho OAuth credentials

1. Go to [https://api-console.zoho.com](https://api-console.zoho.com) and create a **Self Client**.
2. Copy the **Client ID** and **Client Secret**.
3. Generate a refresh token with the required scopes:

   ```
   WorkDrive.files.READ
   WorkDrive.files.UPDATE
   ZohoSheet.dataAPI.UPDATE
   ```

   In the Self Client console choose **Generate Code**, paste the scopes, then exchange the code for a refresh token:

   ```bash
   curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
     -d "code=<authorization_code>" \
     -d "client_id=<CLIENT_ID>" \
     -d "client_secret=<CLIENT_SECRET>" \
     -d "redirect_uri=https://www.zoho.com/crm/oauth-redirect.html" \
     -d "grant_type=authorization_code"
   ```

   Save the `refresh_token` from the response.

### 3. Environment variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ZOHO_CLIENT_ID` | OAuth Self Client ID |
| `ZOHO_CLIENT_SECRET` | OAuth Self Client Secret |
| `ZOHO_REFRESH_TOKEN` | Long-lived refresh token |
| `ZOHO_SHEET_ID` | ID from the Zoho Sheet URL (`/sheet/open/<ID>/`) |
| `ZOHO_SHEET_NAME` | Worksheet tab name (default: `Sheet1`) |
| `WORKDRIVE_INCOMING_FOLDER_ID` | WorkDrive folder ID where Flow drops files |
| `WORKDRIVE_PROCESSED_FOLDER_ID` | Destination for successfully processed files |
| `WORKDRIVE_FAILED_FOLDER_ID` | Destination for files that failed extraction |
| `WEBHOOK_SECRET` | Optional shared secret for request verification |

#### Getting WorkDrive folder IDs

Open the folder in WorkDrive and copy the ID from the URL:
`https://workdrive.zoho.com/folder/<FOLDER_ID>`

---

## Running locally

```bash
uvicorn src.main:app --reload --port 8000
```

The API is available at [http://localhost:8000](http://localhost:8000).  
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Running with Docker

```bash
docker compose up --build
```

The service starts on port 8000 with a health check at `/health`.

---

## API Endpoints

### `GET /health`
Returns `{"status": "ok"}`. Used by Docker health check and load balancers.

---

### `POST /extract`
Primary endpoint for Zoho Flow. Accepts a **multipart form** with the file attachment.

**Form fields:**

| Field | Type | Description |
|---|---|---|
| `file` | file | The attachment |
| `source_email` | string | Sender email address |
| `source_subject` | string | Email subject |
| `source_date` | string | Email date (ISO format) |

**Headers:**
- `X-Zoho-Signature` — required if `WEBHOOK_SECRET` is set

**Supported file types:** `.xlsx`, `.xls`, `.csv`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`

---

### `POST /extract/url`
Download and extract from a direct URL (e.g., Zoho Flow pre-signed link).

**JSON body:**
```json
{
  "filename": "report.xlsx",
  "file_url": "https://...",
  "source_email": "sender@example.com",
  "source_subject": "Monthly Sales Report",
  "source_date": "2026-02-28"
}
```

---

### `POST /extract/workdrive`
Download, extract, write to Sheet, and move the file — all in one call.

**JSON body:**
```json
{
  "filename": "report.xlsx",
  "workdrive_file_id": "abc123xyz",
  "source_email": "sender@example.com",
  "source_subject": "Monthly Sales Report",
  "source_date": "2026-02-28"
}
```

On success the file is moved to `WORKDRIVE_PROCESSED_FOLDER_ID`.  
On failure it is moved to `WORKDRIVE_FAILED_FOLDER_ID`.

---

### Response shape

All extract endpoints return the same schema:

```json
{
  "source_email": "sender@example.com",
  "source_subject": "Monthly Sales Report",
  "source_date": "2026-02-28",
  "source_filename": "report.xlsx",
  "metrics": [
    {
      "metric_name": "Total Revenue",
      "metric_value": 1250000.0,
      "metric_unit": "USD",
      "period": "2026-02",
      "category": "Sales"
    }
  ],
  "confidence": 1.0,
  "errors": []
}
```

`confidence` is `1.0` for full extraction, `0.7` for partial (< 3 metrics), `0.0` for no metrics.

---

## Report Templates

`src/templates/templates.yaml` maps email subject / filename patterns to extraction hints.  
When a template matches, its `default_category` and `default_unit` are applied to any metric that doesn't already have those fields.

```yaml
templates:
  - name: "Monthly Sales Report"
    match_pattern: "monthly.*sales|sales.*report"
    default_category: "Sales"
    default_unit: "USD"
    expected_metrics:
      - "Total Revenue"
      - "Units Sold"
      - "Average Order Value"
```

Add new templates to `templates.yaml` — no code changes required.

---

## Zoho Flow Configuration

1. Create a new **Flow** triggered by an **Email** event.
2. Add a **Webhook** action:
   - **URL:** `https://<your-host>/extract`
   - **Method:** `POST`
   - **Body type:** `multipart/form-data`
   - Map the attachment to the `file` field and email metadata to `source_email`, `source_subject`, `source_date`.
   - Add header `X-Zoho-Signature: <WEBHOOK_SECRET>` if you set one.
3. Optionally parse the JSON response in Flow to trigger further actions based on `confidence` or `errors`.

---

## Running tests

```bash
python3.11 -m pytest
```

OCR tests require `tesseract` to be installed (`brew install tesseract` on macOS).

---

## Project layout

```
src/
  main.py              # FastAPI app & endpoints
  config.py            # Pydantic settings (reads .env)
  models.py            # Request / response / metric schemas
  normalizer.py        # Builds ExtractionResponse, applies template hints
  zoho_client.py       # OAuth2, WorkDrive, Sheet API client
  extractors/
    router.py          # Dispatches to the right extractor by file extension
    excel_extractor.py
    csv_extractor.py
    pdf_extractor.py
    ocr_extractor.py
  templates/
    registry.py        # Loads and matches templates.yaml
    templates.yaml     # Report template definitions
tests/
  test_api.py
  test_csv_extractor.py
  test_excel_extractor.py
  test_pdf_extractor.py
  test_ocr_extractor.py
```
