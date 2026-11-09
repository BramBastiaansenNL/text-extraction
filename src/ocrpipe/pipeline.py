"""Offline batch runner."""

import hashlib
import logging
import base64
from io import BytesIO
from pathlib import Path

from .config import PipelineConfig
from .extract import key_values, merge_characters
from .models import DocumentResult, FieldResult
from .offline import offline_guard, set_offline_environment
from .output import write_results
from .pdf import pages

log = logging.getLogger(__name__)


def process(input_dir: Path, output_dir: Path, config: PipelineConfig, mode: str = "dump", model_dir: Path | None = None) -> int:
    set_offline_environment()
    if not input_dir.is_dir():
        raise ValueError("Input directory does not exist")
    files = sorted(input_dir.glob("*.pdf"))
    if not files:
        raise ValueError("Input directory has no PDF files")
    guard = offline_guard() if config.offline_guard else __import__("contextlib").nullcontext()
    with guard:
        reader = None
        if model_dir is not None:
            from .readers import LocalReaders
            reader = LocalReaders(model_dir)
        results = []
        for file in files:
            doc_id = hashlib.sha256(str(file.resolve()).encode()).hexdigest()[:16]
            doc = DocumentResult(doc_id=doc_id, source_file=file.name)
            doc.flags.append("unclassified")
            for number, image, text, chars in pages(file, config.dpi):
                page_dir = output_dir / "page-images"
                page_dir.mkdir(parents=True, exist_ok=True)
                image.save(page_dir / f"{doc_id}-p{number}.jpg", format="JPEG", quality=85)
                lines = merge_characters(chars) if len(text.strip()) >= 20 else []
                tables = []
                if reader is not None:
                    ocr_lines, tables = reader.read(image)
                    if not lines:
                        lines = ocr_lines
                if not lines:
                    if reader is None:
                        raise RuntimeError("Page has no usable text layer. Set up local OCR weights and pass --model-dir.")
                    doc.flags.append(f"page_{number}_no_text")
                doc.pages.append({"number": number, "lines": [r.model_dump() for r in lines],
                                  "markdown": "\n".join(r.raw_text for r in lines), "tables": len(tables)})
                fields = key_values(lines, number)
                if not fields:
                    fields = [FieldResult(name=f"line_{number}_{i}", value=line.raw_text,
                                          page=number, box=line.box, readings=[line])
                              for i, line in enumerate(lines, 1)]
                for field in fields:
                    field.flags.append("unclassified")
                    if "[" in str(field.value) or "☐" in str(field.value) or "□" in str(field.value):
                        field.flags.append("checkbox_review")
                    if any("\u3000" <= ch <= "\u9fff" for ch in str(field.value)):
                        field.flags.append("symbol_review")
                    score = field.readings[0].confidence
                    threshold = config.confidence_thresholds.get("default", .85)
                    if score is not None and score < threshold:
                        field.flags.append("low_confidence")
                    if field.box is not None:
                        box = field.box
                        margin = 30
                        crop = image.crop((max(0, int(box.x0) - margin), max(0, int(box.y0) - margin),
                                           min(image.width, int(box.x1) + margin),
                                           min(image.height, int(box.y1) + margin)))
                        buffer = BytesIO()
                        crop.save(buffer, format="PNG")
                        field.crop = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
                    doc.fields.append(field)
            results.append(doc)
            log.info("Processed %s: %d pages, %d fields", file.name, len(doc.pages), len(doc.fields))
        write_results(results, output_dir)
    return len(results)
