"""Validated user configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class LocaleConfig(BaseModel):
    decimal_separator: str = "."
    thousands_separator: str = ","
    date_formats: list[str] = Field(default_factory=lambda: ["%Y-%m-%d"])

    @model_validator(mode="after")
    def distinct_separators(self):
        if self.decimal_separator == self.thousands_separator:
            raise ValueError("Decimal and thousands separators must differ")
        return self


class ReaderConfig(BaseModel):
    use_ollama: bool = False
    ollama_model: str = "qwen2.5vl:7b"
    ollama_url: str = "http://127.0.0.1:11434"
    use_trocr: bool = False

    @field_validator("ollama_model")
    @classmethod
    def local_model(cls, value: str) -> str:
        if "cloud" in value.lower():
            raise ValueError("Cloud models are forbidden")
        return value

    @field_validator("ollama_url")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        if value != "http://127.0.0.1:11434":
            raise ValueError("Ollama must use http://127.0.0.1:11434")
        return value


class PipelineConfig(BaseModel):
    dpi: int = Field(default=300, ge=72, le=1200)
    offline_guard: bool = True
    debug_content: bool = False
    locale: LocaleConfig = Field(default_factory=LocaleConfig)
    readers: ReaderConfig = Field(default_factory=ReaderConfig)
    confidence_thresholds: dict[str, float] = Field(default_factory=lambda: {"default": 0.85, "integer": 0.95, "decimal": 0.95})

    @field_validator("confidence_thresholds")
    @classmethod
    def valid_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError("Confidence thresholds must be between 0 and 1")
        return value


def load_config(path: Path | None = None) -> PipelineConfig:
    if path is None:
        return PipelineConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping")
    return PipelineConfig.model_validate(data)
