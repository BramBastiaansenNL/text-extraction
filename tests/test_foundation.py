import os
import socket

import pytest
from pydantic import ValidationError

from ocrpipe.config import PipelineConfig, ReaderConfig
from ocrpipe.offline import offline_guard


def test_offline_guard_blocks_external_connect_and_restores_socket():
    original = socket.socket.connect
    with offline_guard():
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
        assert os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] == "True"
        with socket.socket() as sock:
            with pytest.raises(OSError, match="Offline guard blocked"):
                sock.connect(("8.8.8.8", 443))
            with pytest.raises(OSError, match="Offline guard blocked"):
                sock.connect_ex(("8.8.8.8", 443))
        with pytest.raises(OSError, match="Offline guard blocked"):
            socket.create_connection(("8.8.8.8", 443))
        with pytest.raises(OSError, match="Offline guard blocked"):
            socket.getaddrinfo("example.com", 443)
    assert socket.socket.connect is original


def test_cloud_model_and_remote_ollama_rejected():
    with pytest.raises(ValidationError):
        ReaderConfig(ollama_model="example-cloud")
    with pytest.raises(ValidationError):
        ReaderConfig(ollama_url="http://example.com:11434")


def test_threshold_validation():
    with pytest.raises(ValidationError):
        PipelineConfig(confidence_thresholds={"integer": 1.1})
