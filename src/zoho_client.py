from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# Zoho access tokens live for 3600 s; refresh 60 s early to be safe.
_TOKEN_TTL = 3540


class ZohoClient:
    """Handles Zoho OAuth2 token refresh, WorkDrive file ops, and Sheet writes."""

    def __init__(self) -> None:
        self._access_token: str = ""
        self._token_expiry: float = 0.0
        self._http = httpx.AsyncClient(timeout=30)

    async def _ensure_token(self) -> str:
        """Refresh the OAuth2 access token using the stored refresh token."""
        if self._access_token and time.monotonic() < self._token_expiry:
            return self._access_token

        if not settings.zoho_client_id or not settings.zoho_refresh_token:
            raise RuntimeError("Zoho OAuth credentials not configured — check .env")

        resp = await self._http.post(
            f"{settings.zoho_accounts_url}/oauth/v2/token",
            params={
                "refresh_token": settings.zoho_refresh_token,
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.monotonic() + _TOKEN_TTL
        return self._access_token

    def _invalidate_token(self) -> None:
        self._access_token = ""
        self._token_expiry = 0.0

    async def _headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {"Authorization": f"Zoho-oauthtoken {token}"}

    # ── WorkDrive ──

    async def download_file(self, file_id: str, dest: Path) -> Path:
        """Download a file from Zoho WorkDrive by ID."""
        headers = await self._headers()
        resp = await self._http.get(
            f"https://www.zohoapis.com/workdrive/api/v1/download/{file_id}",
            headers=headers,
            follow_redirects=True,
        )
        if resp.status_code == 401:
            self._invalidate_token()
            headers = await self._headers()
            resp = await self._http.get(
                f"https://www.zohoapis.com/workdrive/api/v1/download/{file_id}",
                headers=headers,
                follow_redirects=True,
            )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    async def download_url(self, url: str, dest: Path) -> Path:
        """Download a file from an arbitrary URL (e.g. a Zoho Flow pre-signed URL)."""
        resp = await self._http.get(url, follow_redirects=True)
        if resp.status_code == 401:
            # Try with auth headers in case it's a Zoho-hosted URL
            headers = await self._headers()
            resp = await self._http.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    async def move_file(self, file_id: str, dest_folder_id: str) -> None:
        """Move a file to a different WorkDrive folder (e.g., processed/failed)."""
        headers = await self._headers()
        headers["Content-Type"] = "application/json"
        body = {
            "data": {
                "attributes": {"parent_id": dest_folder_id},
                "id": file_id,
                "type": "files",
            }
        }
        resp = await self._http.patch(
            f"https://www.zohoapis.com/workdrive/api/v1/files/{file_id}",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()

    async def upload_file(self, folder_id: str, file_path: Path) -> str:
        """Upload a file to a WorkDrive folder. Returns the new file ID."""
        headers = await self._headers()
        with file_path.open("rb") as f:
            resp = await self._http.post(
                "https://www.zohoapis.com/workdrive/api/v1/upload",
                headers=headers,
                params={"parent_id": folder_id, "override-name-exist": "true"},
                files={"content": (file_path.name, f)},
            )
        resp.raise_for_status()
        return resp.json()["data"][0]["attributes"]["resource_id"]

    # ── Sheet ──

    async def append_sheet_rows(self, rows: list[dict]) -> None:
        """Append rows to the configured Zoho Sheet."""
        if not settings.zoho_sheet_id:
            logger.warning("ZOHO_SHEET_ID not set — skipping sheet write")
            return

        headers = await self._headers()
        headers["Content-Type"] = "application/json"

        for row in rows:
            resp = await self._http.post(
                f"https://sheet.zoho.com/api/v2/{settings.zoho_sheet_id}",
                headers=headers,
                params={
                    "method": "worksheet.records.add",
                    "worksheet_name": settings.zoho_sheet_name,
                },
                json={"data": row},
            )
            resp.raise_for_status()

    async def close(self) -> None:
        await self._http.aclose()


# Singleton for the app lifecycle
zoho_client = ZohoClient()
