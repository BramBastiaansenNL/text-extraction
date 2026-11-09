"""Checks for conservative local form suggestions and script-free review pages."""

import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from ocrpipe.models import DocumentResult, FieldResult
from ocrpipe.schema import suggest_types
from ocrpipe.web import ReviewHandler


def test_form_suggestions_need_multiple_labels(tmp_path):
    docs = [DocumentResult(doc_id=f"{n:016x}", source_file=f"{n}.pdf", fields=[
        FieldResult(name="Name", value="A", page=1),
        FieldResult(name="Date", value="2026", page=1),
    ]) for n in range(2)]
    result = suggest_types(docs, tmp_path / "types.json")
    assert result[docs[0].doc_id] == result[docs[1].doc_id] == "proposed_1"
    docs[1].fields = [FieldResult(name="Name", value="A", page=1)]
    assert suggest_types(docs, tmp_path / "types.json")[docs[1].doc_id] == "unclassified"


def test_review_page_has_content_without_javascript(tmp_path):
    run = tmp_path / "run-one"
    (run / "documents").mkdir(parents=True)
    doc = DocumentResult(doc_id="1234567890abcdef", source_file="form.pdf", fields=[
        FieldResult(name="Name", value="Ada", page=1)
    ], pages=[{"number": 1, "lines": [{"raw_text": "Name: Ada"}]}])
    (run / "documents" / "1234567890abcdef.json").write_text(doc.model_dump_json(), encoding="utf-8")
    handler = type("Handler", (ReviewHandler,), {"root": tmp_path, "model_dir": None})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = urlopen(f"http://127.0.0.1:{server.server_port}/review?run=run-one").read().decode()
        assert "form.pdf" in body and "Name: Ada" in body and "Reviewed value" in body
        assert "<script" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_local_upload_creates_reviewable_run(tmp_path, monkeypatch):
    import ocrpipe.web as web

    def fake_process(source, output, config, model_dir):
        assert len(list(source.glob("*.pdf"))) == 1
        assert next(source.glob("*.pdf")).read_bytes() == b"%PDF-1.4\n"
        (output / "documents").mkdir()
        doc = DocumentResult(doc_id="1234567890abcdef", source_file="form.pdf", pages=[])
        (output / "documents" / "1234567890abcdef.json").write_text(doc.model_dump_json(), encoding="utf-8")

    monkeypatch.setattr(web, "process", fake_process)
    handler = type("Handler", (ReviewHandler,), {"root": tmp_path, "model_dir": None})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        boundary = "local-test-boundary"
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"form.pdf\"\r\n"
                   "Content-Type: application/pdf\r\n\r\n").encode() + b"%PDF-1.4\n" + f"\r\n--{boundary}--\r\n".encode()
        request = Request(f"http://127.0.0.1:{server.server_port}/extract", data=payload,
                          headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        body = urlopen(request).read().decode()
        assert "form.pdf" in body and "Run:" in body
        assert len(list(tmp_path.glob("run-*/input/*.pdf"))) == 1
    finally:
        server.shutdown()
        server.server_close()
