from __future__ import annotations

from pathlib import Path

from src.extractors.csv_extractor import extract_csv
from src.extractors.excel_extractor import extract_excel
from src.extractors.ocr_extractor import extract_image
from src.extractors.pdf_extractor import extract_pdf
from src.models import Metric

# Map file extensions to extractors
_EXTRACTORS: dict[str, callable] = {
    ".xlsx": extract_excel,
    ".xls": extract_excel,
    ".csv": extract_csv,
    ".pdf": extract_pdf,
    ".png": extract_image,
    ".jpg": extract_image,
    ".jpeg": extract_image,
    ".tiff": extract_image,
    ".tif": extract_image,
    ".bmp": extract_image,
}


def route_extraction(file_path: Path) -> list[Metric]:
    """Dispatch to the appropriate extractor based on file extension."""
    ext = file_path.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {ext}")
    return extractor(file_path)


def supported_extensions() -> list[str]:
    return list(_EXTRACTORS.keys())
