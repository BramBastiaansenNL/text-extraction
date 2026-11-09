"""Shared output and provenance schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class Box(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Reading(BaseModel):
    reader: Literal["text-layer", "ocr", "vlm", "trocr"]
    raw_text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    box: Box | None = None


class FieldResult(BaseModel):
    name: str
    value: str | int | float | bool | None = None
    page: int = Field(ge=1)
    box: Box | None = None
    readings: list[Reading] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    crop: str | None = None


class DocumentResult(BaseModel):
    doc_id: str
    source_file: str
    doc_type: str = "unclassified"
    fields: list[FieldResult] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    pages: list[dict] = Field(default_factory=list)
