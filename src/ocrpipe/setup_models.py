"""Explicit, one-time network-enabled model setup only."""

import sys
from pathlib import Path

from .paddle_env import configure_paddle_cache


def main() -> None:
    directory = Path(sys.argv[1]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    configure_paddle_cache(directory)
    from paddleocr import PaddleOCR
    PaddleOCR(device="cpu", enable_mkldnn=False,
              text_detection_model_name="PP-OCRv5_mobile_det",
              text_recognition_model_name="PP-OCRv5_mobile_rec",
              use_doc_orientation_classify=False, use_doc_unwarping=False,
              use_textline_orientation=False)
    print("Local OCR model setup complete")


if __name__ == "__main__":
    main()
