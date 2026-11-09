"""Keep Paddle's implicit caches in the selected local model directory."""

import os
from pathlib import Path


def configure_paddle_cache(model_dir: Path) -> None:
    cache = (model_dir / ".paddlex-cache").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
    # Paddle's dataset module uses expanduser('~') with no cache override.
    # Restrict only that lookup to a local cache; other paths retain normal behavior.
    original = os.path.expanduser
    if getattr(original, "_ocrpipe_cache", False):
        return

    def expanduser(path):
        if path == "~":
            return str(cache)
        return original(path)

    expanduser._ocrpipe_cache = True
    os.path.expanduser = expanduser
