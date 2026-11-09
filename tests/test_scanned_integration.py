"""Synthetic scanned-PDF integration check; requires local setup weights."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from ocrpipe.config import PipelineConfig
from ocrpipe.models import DocumentResult
from ocrpipe.pipeline import process


MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / ".paddlex-cache" / "official_models" / "PP-OCRv5_mobile_rec").is_dir(),
    reason="Run setup to download local OCR models first",
)


def test_scanned_pdf_offline(tmp_path):
    source = tmp_path / "input"
    output = tmp_path / "output"
    source.mkdir()
    image = Image.new("RGB", (1200, 300), "white")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 54)
    ImageDraw.Draw(image).text((60, 70), "Total: 123.45", font=font, fill="black")
    image.save(source / "synthetic.pdf", resolution=150)

    assert process(source, output, PipelineConfig(), model_dir=MODEL_DIR) == 1
    document = DocumentResult.model_validate_json(next((output / "documents").glob("*.json")).read_text())
    assert document.fields
    assert any(field.value == "123.45" for field in document.fields)
    assert all("unclassified" in field.flags for field in document.fields)
    assert (output / "review.html").exists()
    assert list((output / "markdown").glob("*.md"))
