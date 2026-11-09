"""Conservative, local form grouping based on recurring field labels."""

import json
import re
from pathlib import Path

from .models import DocumentResult


def labels(doc: DocumentResult) -> set[str]:
    return {re.sub(r"[^\w]+", " ", field.name.casefold()).strip()
            for field in doc.fields if not field.name.startswith("line_")}


def suggest_types(docs: list[DocumentResult], catalog_path: Path) -> dict[str, str]:
    """Assign a saved type only for a strong label match; otherwise propose a group."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    groups: list[tuple[set[str], str]] = []
    result = {}
    for doc in docs:
        observed = labels(doc)
        best_name, best_score = "unclassified", 0.0
        for name, expected in catalog.items():
            expected_set = set(expected)
            score = len(observed & expected_set) / len(observed | expected_set) if observed | expected_set else 0
            if score > best_score:
                best_name, best_score = name, score
        if best_score >= 0.8 and len(observed) >= 2:
            result[doc.doc_id] = best_name
            continue
        for group_labels, group_name in groups:
            overlap = len(observed & group_labels) / len(observed | group_labels) if observed | group_labels else 0
            if overlap >= 0.8 and len(observed) >= 2:
                result[doc.doc_id] = group_name
                break
        else:
            group_name = f"proposed_{len(groups) + 1}"
            groups.append((observed, group_name))
            result[doc.doc_id] = group_name if len(observed) >= 2 else "unclassified"
    return result
