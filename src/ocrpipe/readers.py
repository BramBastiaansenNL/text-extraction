"""Local PaddleOCR adapters. Model initialization never downloads at runtime."""

import json
import tempfile
from pathlib import Path

from .models import Box, Reading
from .paddle_env import configure_paddle_cache


def _data(result):
    data = result.json
    if isinstance(data, str):
        data = json.loads(data)
    return data.get("res", data)


def _box(coords):
    return Box(x0=float(coords[0]), y0=float(coords[1]), x1=float(coords[2]), y1=float(coords[3]))


class LocalReaders:
    def __init__(self, model_dir: Path, device: str = "cpu"):
        configure_paddle_cache(model_dir)
        from paddleocr import PaddleOCR

        det = model_dir / ".paddlex-cache" / "official_models" / "PP-OCRv5_mobile_det"
        rec = model_dir / ".paddlex-cache" / "official_models" / "PP-OCRv5_mobile_rec"
        if not det.is_dir() or not rec.is_dir():
            raise RuntimeError("Local OCR weights missing. Run the explicit setup command first.")
        self.ocr = PaddleOCR(device=device, enable_mkldnn=False,
                             text_detection_model_name="PP-OCRv5_mobile_det",
                             text_recognition_model_name="PP-OCRv5_mobile_rec",
                             text_detection_model_dir=str(det), text_recognition_model_dir=str(rec),
                             use_doc_orientation_classify=False, use_doc_unwarping=False,
                             use_textline_orientation=False)
        self.structure = None

    def read(self, image):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.png"
            image.save(path)
            result = list(self.ocr.predict(str(path)))
            if not result:
                return [], []
            data = _data(result[0])
            readings = [Reading(reader="ocr", raw_text=str(text), confidence=float(score), box=_box(box))
                        for text, score, box in zip(data.get("rec_texts", []), data.get("rec_scores", []), data.get("rec_boxes", []))]
            tables = []
            if self.structure is not None:
                for item in self.structure.predict(str(path)):
                    tables.extend(_data(item).get("table_res_list", []))
            return readings, tables
