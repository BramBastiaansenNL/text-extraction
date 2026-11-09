"""Layout-independent line and key/value extraction."""

import re

from .models import FieldResult, Reading


def merge_characters(characters: list[Reading]) -> list[Reading]:
    if not characters:
        return []
    ordered = sorted(characters, key=lambda item: (round(item.box.y0 / 8), item.box.x0))
    lines = []
    current = []
    for char in ordered:
        if current and abs(char.box.y0 - current[0].box.y0) > max(4, (current[0].box.y1 - current[0].box.y0) * .65):
            lines.append(current)
            current = []
        current.append(char)
    if current:
        lines.append(current)
    merged = []
    for line in lines:
        line.sort(key=lambda item: item.box.x0)
        height = max(item.box.y1 - item.box.y0 for item in line)
        text = ""
        last = None
        for item in line:
            if last and item.box.x0 - last.box.x1 > height * .45:
                text += " "
            text += item.raw_text
            last = item
        merged.append(Reading(reader="text-layer", raw_text=text, confidence=1,
                              box={"x0": min(x.box.x0 for x in line), "y0": min(x.box.y0 for x in line),
                                   "x1": max(x.box.x1 for x in line), "y1": max(x.box.y1 for x in line)}))
    return merged


def key_values(lines: list[Reading], page: int) -> list[FieldResult]:
    fields = []
    for line in lines:
        match = re.match(r"^\s*([^:]{2,60}):\s*(.+?)\s*$", line.raw_text)
        if match:
            fields.append(FieldResult(name=match.group(1).strip(), value=match.group(2).strip(),
                                      page=page, box=line.box, readings=[line], flags=[]))
    return fields
