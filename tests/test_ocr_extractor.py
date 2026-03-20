# OCR tests require tesseract installed. Mark as integration tests.
import shutil

import pytest
from pathlib import Path

from src.extractors.ocr_extractor import extract_image


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a simple test image with text (requires Pillow)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Total Revenue: $1,250,000", fill="black")
    draw.text((10, 50), "Units Sold: 3,400", fill="black")
    path = tmp_path / "test_report.png"
    img.save(path)
    return path


@pytest.mark.skipif(
    not _tesseract_available(),
    reason="tesseract not installed",
)
def test_ocr_extraction(sample_image: Path):
    metrics = extract_image(sample_image)
    # OCR quality varies, so just check we got something
    assert len(metrics) >= 1
