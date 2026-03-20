from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter

from src.extractors.pdf_extractor import _parse_text_kpis
from src.models import Metric


def extract_image(file_path: Path) -> list[Metric]:
    """Extract metrics from an image using OCR.

    Preprocessing: grayscale → sharpen → threshold for better OCR accuracy.
    Then reuse the PDF text regex extractor on the OCR output.
    """
    img = Image.open(file_path)

    # Preprocessing for better OCR
    img = img.convert("L")  # grayscale
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 0 if x < 140 else 255)  # binary threshold

    text = pytesseract.image_to_string(img)

    return _parse_text_kpis(text)
