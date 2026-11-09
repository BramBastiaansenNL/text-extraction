"""Write structured results and a self-contained review page."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .models import DocumentResult


def write_results(results: list[DocumentResult], output: Path) -> None:
    (output / "documents").mkdir(parents=True, exist_ok=True)
    (output / "tables").mkdir(exist_ok=True)
    (output / "markdown").mkdir(exist_ok=True)
    by_type = defaultdict(list)
    for doc in results:
        (output / "documents" / f"{doc.doc_id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        for page in doc.pages:
            (output / "markdown" / f"{doc.doc_id}-p{page['number']}.md").write_text(page["markdown"] + "\n", encoding="utf-8")
        by_type[doc.doc_type].append(doc)
    for kind, docs in by_type.items():
        names = sorted({field.name for doc in docs for field in doc.fields})
        with (output / f"{kind}.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=["doc_id", *names, "flagged_count"])
            writer.writeheader()
            for doc in docs:
                row = {"doc_id": doc.doc_id, "flagged_count": sum(bool(f.flags) for f in doc.fields)}
                row.update({field.name: field.value for field in doc.fields})
                writer.writerow(row)
    write_review(results, output / "review.html")


def write_review(results: list[DocumentResult], path: Path) -> None:
    entries = []
    for doc in results:
        for field in doc.fields:
            if field.flags:
                entries.append({"doc_id": doc.doc_id, "page": field.page, "field": field.name,
                                "value": field.value, "flags": field.flags,
                                "crop": field.crop,
                                "readings": [{"reader": r.reader, "raw_text": r.raw_text} for r in field.readings]})
    payload = json.dumps(entries).replace("<", "\\u003c")
    page = """<!doctype html><meta charset=utf-8><title>OCR review</title>
<style>body{font:16px system-ui;max-width:900px;margin:2em auto;padding:0 1em}article{border:1px solid #aaa;padding:1em;margin:1em 0}input[type=text]{width:95%;padding:.5em}button{padding:.6em}</style>
<h1>Flagged fields</h1><main id=items></main><button id=export>Export corrections</button>
<script>const data=PAYLOAD;const root=document.getElementById('items');
for(const e of data){let a=document.createElement('article');let h=document.createElement('h2');h.textContent=e.doc_id+' · page '+e.page+' · '+e.field;a.append(h);
if(e.crop){let im=document.createElement('img');im.src=e.crop;im.style.maxWidth='100%';im.alt='Field crop';a.append(im)}
let p=document.createElement('p');p.textContent='Flags: '+e.flags.join(', ');a.append(p);
for(const r of e.readings){let q=document.createElement('p');q.textContent=r.reader+': '+r.raw_text;a.append(q)}
let input=document.createElement('input');input.type='text';input.value=e.value??'';a.append(input);
let label=document.createElement('label');let check=document.createElement('input');check.type='checkbox';label.append(check,' Accept');a.append(label);e.input=input;e.check=check;
input.addEventListener('keydown',ev=>{if(ev.key==='Enter'){check.checked=true;let next=a.nextElementSibling;if(next)next.querySelector('input[type=text]').focus()}});root.append(a)}
function csv(v){return '"'+String(v??'').replaceAll('"','""')+'"'}
document.getElementById('export').onclick=()=>{let rows=[['doc_id','page','field','value','reviewer_action']];for(const e of data)if(e.check.checked)rows.push([e.doc_id,e.page,e.field,e.input.value,'accept']);let blob=new Blob([rows.map(r=>r.map(csv).join(',')).join('\r\n')],{type:'text/csv'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='corrections.csv';a.click();URL.revokeObjectURL(a.href)};</script>""".replace("PAYLOAD", payload)
    path.write_text(page, encoding="utf-8")


def apply_corrections(path: Path, output: Path, reviewer: str) -> int:
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if row.get("reviewer_action") != "accept":
            continue
        if not re.fullmatch(r"[0-9a-f]{16}", row.get("doc_id", "")):
            raise ValueError("Invalid document ID in corrections")
        doc_path = output / "documents" / f"{row['doc_id']}.json"
        doc = DocumentResult.model_validate_json(doc_path.read_text(encoding="utf-8"))
        for field in doc.fields:
            if field.page == int(row["page"]) and field.name == row["field"]:
                old = field.value
                field.value = row["value"]
                field.flags = []
                with (output / "audit.jsonl").open("a", encoding="utf-8") as audit:
                    from datetime import datetime, timezone
                    audit.write(json.dumps({"who": reviewer, "when": datetime.now(timezone.utc).isoformat(),
                                            "doc_id": doc.doc_id, "page": field.page, "field": field.name,
                                            "old": old, "new": field.value}) + "\n")
                count += 1
                break
        doc_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    docs = [DocumentResult.model_validate_json(p.read_text(encoding="utf-8")) for p in (output / "documents").glob("*.json")]
    write_results(docs, output)
    return count
