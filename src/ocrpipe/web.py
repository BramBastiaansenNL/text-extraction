"""Loopback-only review application. No third-party web assets or services."""

import html
import json
import threading
import webbrowser
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .config import PipelineConfig
from .models import DocumentResult
from .output import write_results
from .pipeline import process
from .schema import labels, suggest_types


CSS = """body{font:16px system-ui;margin:0;color:#172433;background:#f5f7f9}header{background:#153b56;color:white;padding:1rem 2rem}main{max-width:1250px;margin:auto;padding:1.5rem}section,article{background:white;border:1px solid #d1dbe2;border-radius:9px;padding:1rem;margin:1rem 0}button,input,select{font:inherit;padding:.45rem}button{cursor:pointer;background:#17648a;color:white;border:0;border-radius:5px}label{display:block;margin:.5rem 0}.muted{color:#586879}.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.crop{max-width:100%;border:1px solid #ddd}.line{padding:.3rem;border-bottom:1px solid #eee}.field{border-left:4px solid #b1c9d9;padding:.6rem;margin:.6rem 0}.field input[type=text]{width:85%}.warn{color:#8b4500}.ok{color:#17602f}@media(max-width:800px){.grid{grid-template-columns:1fr}}"""


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


class ReviewHandler(BaseHTTPRequestHandler):
    root: Path
    model_dir: Path | None

    def send_html(self, body: str, status: int = 200):
        page = f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Local document review</title><style>{CSS}</style><header><h1>Local document review</h1><div>Files stay on this computer</div></header><main>{body}</main></html>'
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path: str):
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/":
            self.home()
        elif url.path == "/review":
            self.review(parse_qs(url.query).get("run", [""])[0])
        elif url.path == "/page-image":
            args = parse_qs(url.query)
            try:
                run = self._run_path(args.get("run", [""])[0])
                image_name = args.get("name", [""])[0]
                if not image_name.endswith(".jpg") or Path(image_name).name != image_name:
                    raise ValueError("Invalid image")
                data = (run / "page-images" / image_name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (ValueError, OSError):
                self.send_error(404)
        else:
            self.send_error(404)

    def home(self):
        runs = sorted((p for p in self.root.iterdir() if p.is_dir()), reverse=True)
        items = "".join(f'<li><a href="/review?run={esc(p.name)}">{esc(p.name)}</a></li>' for p in runs)
        body = f'''<section><h2>Extract PDFs</h2><p>Select one or more local PDFs. A new dated output folder will be created in <code>{esc(self.root)}</code>.</p>
        <form action="/extract" method="post" enctype="multipart/form-data"><label>PDF files <input name="files" type="file" accept="application/pdf,.pdf" multiple required></label><button>Extract and review</button></form>
        <p class="muted">Processing may take several minutes. This page waits for the local OCR process to finish.</p></section><section><h2>Previous runs</h2><ul>{items or '<li>No runs yet</li>'}</ul></section>'''
        self.send_html(body)

    def _run_path(self, name: str) -> Path:
        if not name or Path(name).name != name or name.startswith("."):
            raise ValueError("Invalid run name")
        path = (self.root / name).resolve()
        if path.parent != self.root.resolve() or not path.is_dir():
            raise ValueError("Run not found")
        return path

    def review(self, name: str, message: str = ""):
        try:
            run = self._run_path(name)
        except ValueError as exc:
            self.send_html(f'<p class="warn">{esc(exc)}</p>', 404)
            return
        docs = [DocumentResult.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted((run / "documents").glob("*.json"))]
        audit_path = run / "audit.jsonl"
        notes = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()] if audit_path.exists() else []
        suggestions = suggest_types(docs, self.root / "form-types.json")
        parts = [f'<p><a href="/">← New extraction</a></p><h2>Run: {esc(name)}</h2><p>Output folder: <code>{esc(run)}</code></p>']
        if message:
            parts.append(f'<p class="ok">{esc(message)}</p>')
        parts.append('<p class="muted">Compare each field and line with the original PDF. Crops show the detected area. Check handwritten ticks, circular stamps, symbols, and letters touching form borders carefully.</p>')
        for doc in docs:
            proposed = suggestions[doc.doc_id]
            parts.append(f'<section><h2>{esc(doc.source_file)}</h2><p>Form type: <strong>{esc(doc.doc_type)}</strong> · Suggested group: <strong>{esc(proposed)}</strong></p>')
            parts.append(f'''<form action="/type" method="post"><input type="hidden" name="run" value="{esc(name)}"><input type="hidden" name="doc_id" value="{esc(doc.doc_id)}"><label>Name or correct this form type <input type="text" name="type" value="{esc(doc.doc_type if doc.doc_type != 'unclassified' else '')}" placeholder="e.g. intake_form_v1" pattern="[A-Za-z0-9_-]+" required></label><button>Save form type</button></form>''')
            for page in doc.pages:
                number = page["number"]
                parts.append(f'<article><h3>Page {number}</h3><div class="grid"><div><h4>Original page</h4><a href="/page-image?run={esc(name)}&name={esc(doc.doc_id)}-p{number}.jpg" target="_blank"><img class="crop" src="/page-image?run={esc(name)}&name={esc(doc.doc_id)}-p{number}.jpg" alt="Rendered original page {number}"></a><h4>Detected text, in reading order</h4>')
                parts.extend(f'<div class="line">{esc(line["raw_text"])}</div>' for line in page["lines"])
                for note in notes:
                    if note.get("action") == "page_note" and note.get("doc_id") == doc.doc_id and note.get("page") == number:
                        parts.append(f'<p class="warn">Review note: {esc(note["note"])}</p>')
                parts.append(f'''<form action="/page-note" method="post"><input type="hidden" name="run" value="{esc(name)}"><input type="hidden" name="doc_id" value="{esc(doc.doc_id)}"><input type="hidden" name="page" value="{number}"><label>Missing text or page issue <input type="text" name="note" placeholder="e.g. circular stamp text missing" required></label><button>Save page note</button></form>''')
                parts.append('</div><div><h4>Fields and evidence</h4>')
                for index, field in enumerate(doc.fields):
                    if field.page != number:
                        continue
                    score = field.readings[0].confidence if field.readings else None
                    parts.append(f'<div class="field"><strong>{esc(field.name)}</strong> <span class="muted">confidence: {esc(f"{score:.2f}" if score is not None else "unknown")}</span>')
                    if field.crop:
                        parts.append(f'<div><img class="crop" src="{esc(field.crop)}" alt="Image crop for {esc(field.name)}"></div>')
                    parts.append(f'''<form action="/correct" method="post"><input type="hidden" name="run" value="{esc(name)}"><input type="hidden" name="doc_id" value="{esc(doc.doc_id)}"><input type="hidden" name="index" value="{index}"><label>Reviewed value <input type="text" name="value" value="{esc(field.value)}"></label><label>Review note <input type="text" name="note" placeholder="e.g. blue tick missed; stamp text curved"></label><button>Save correction</button></form>''')
                    parts.append(f'<small class="muted">{esc(", ".join(field.flags))}</small></div>')
                parts.append('</div></div></article>')
            parts.append('</section>')
        self.send_html("".join(parts))

    def do_POST(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if host not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}") or (origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")):
            self.send_error(403)
            return
        if self.path == "/extract":
            self.extract()
            return
        if self.path not in ("/correct", "/type", "/page-note"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 100_000:
            self.send_error(413)
            return
        values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        get = lambda key: values.get(key, [""])[0]
        try:
            run = self._run_path(get("run"))
            doc_id = get("doc_id")
            if not (len(doc_id) == 16 and all(c in "0123456789abcdef" for c in doc_id)):
                raise ValueError("Invalid document ID")
            file = run / "documents" / f"{doc_id}.json"
            doc = DocumentResult.model_validate_json(file.read_text(encoding="utf-8"))
            if self.path == "/page-note":
                page_number = int(get("page"))
                if not any(page["number"] == page_number for page in doc.pages) or not get("note").strip():
                    raise ValueError("Invalid page note")
                with (run / "audit.jsonl").open("a", encoding="utf-8") as audit:
                    audit.write(json.dumps({"when": datetime.now().isoformat(), "doc_id": doc_id,
                                            "page": page_number, "note": get("note"), "action": "page_note"}, ensure_ascii=False) + "\n")
                message = "Page note saved."
            elif self.path == "/correct":
                index = int(get("index"))
                field = doc.fields[index]
                old = field.value
                field.value = get("value")
                field.flags = [flag for flag in field.flags if flag != "low_confidence"]
                with (run / "audit.jsonl").open("a", encoding="utf-8") as audit:
                    audit.write(json.dumps({"when": datetime.now().isoformat(), "doc_id": doc_id, "page": field.page,
                                            "field": field.name, "old": old, "new": field.value, "note": get("note")}, ensure_ascii=False) + "\n")
                message = "Correction saved."
            else:
                import re
                kind = get("type")
                if not re.fullmatch(r"[A-Za-z0-9_-]+", kind):
                    raise ValueError("Type name may contain only letters, digits, hyphens, and underscores")
                old_kind = doc.doc_type
                doc.doc_type = kind
                doc.flags = [flag for flag in doc.flags if flag != "unclassified"]
                catalog_path = self.root / "form-types.json"
                catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
                catalog[kind] = sorted(labels(doc))
                catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
                message = "Form type saved for this document and future suggestions."
            file.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
            docs = [DocumentResult.model_validate_json(p.read_text(encoding="utf-8")) for p in (run / "documents").glob("*.json")]
            if self.path == "/type" and old_kind != doc.doc_type and not any(item.doc_type == old_kind for item in docs):
                (run / f"{old_kind}.csv").unlink(missing_ok=True)
            write_results(docs, run)
            self.review(get("run"), message)
        except (ValueError, IndexError, OSError) as exc:
            self.send_html(f'<p class="warn">Could not save: {esc(exc)}</p>', 400)

    def extract(self):
        if not self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            self.send_error(400)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 100_000_000:
            self.send_error(413)
            return
        envelope = b"Content-Type: " + self.headers["Content-Type"].encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes(envelope)
        uploads = [part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "files" and part.get_filename()]
        if not uploads:
            self.send_html('<p class="warn">Choose at least one PDF.</p>', 400)
            return
        name = datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")
        run = self.root / name
        source = run / "input"
        source.mkdir(parents=True)
        try:
            for index, item in enumerate(uploads, 1):
                filename = Path(item.get_filename()).name
                if not filename.lower().endswith(".pdf"):
                    raise ValueError("Only PDF files are accepted")
                target = source / f"{index:03d}-{filename}"
                content = item.get_payload(decode=True)
                if not content.startswith(b"%PDF-"):
                    raise ValueError("Selected file is not a PDF")
                target.write_bytes(content)
            process(source, run, PipelineConfig(), model_dir=self.model_dir)
            self.redirect(f"/review?run={name}")
        except Exception as exc:
            self.send_html(f'<p class="warn">Extraction failed: {esc(exc)}</p><p>Files are in <code>{esc(run)}</code>.</p>', 500)


def serve(output_root: Path, model_dir: Path | None, port: int = 8765, open_browser: bool = True):
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    handler = type("LocalReviewHandler", (ReviewHandler,), {"root": output_root, "model_dir": model_dir})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Local review interface: {url}\nOutput root: {output_root}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
