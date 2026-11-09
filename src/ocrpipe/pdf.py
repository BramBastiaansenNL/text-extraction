"""PDF rendering and embedded text extraction."""

from pathlib import Path

import pypdfium2 as pdfium

from .models import Box, Reading


def pages(path: Path, dpi: int):
    pdf = pdfium.PdfDocument(path)
    scale = dpi / 72
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            image = page.render(scale=scale).to_pil().convert("RGB")
            text_page = page.get_textpage()
            count = text_page.count_chars()
            text = text_page.get_text_range() if count else ""
            lines = []
            # PDFium coordinates use a bottom-left origin; image boxes use top-left.
            for i in range(count):
                char = text_page.get_text_range(i, 1)
                if not char or char.isspace():
                    continue
                left, bottom, right, top = text_page.get_charbox(i)
                box = Box(x0=left * scale, y0=(page.get_height() - top) * scale,
                          x1=right * scale, y1=(page.get_height() - bottom) * scale)
                lines.append(Reading(reader="text-layer", raw_text=char, confidence=1, box=box))
            yield index + 1, image, text, lines
    finally:
        pdf.close()
