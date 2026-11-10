# Local PDF extraction and review

An early-stage, Windows-first tool for extracting text from PDFs and reviewing the results entirely on your computer. It is intended for varied forms, including scanned pages. The current schema suggestions require human confirmation.

## Contents

- [Quick start](#quick-start-windows)
- [Local browser review](#local-browser-review)
- [How extraction works](#how-extraction-works)
- [Current capabilities and limits](#current-capabilities-and-limits)
- [Privacy and output files](#privacy-and-output-files)
- [Command-line use](#process-one-pdf-folder)
- [Developer checks](#checks)

## Quick start (Windows)

1. Install **64-bit Python 3.11 or 3.12** and enable **Add Python to PATH** during installation.
2. Double-click **Setup.cmd** in this folder. It creates a virtual environment, installs dependencies, and downloads the local OCR weights. Internet access is needed for this one-time step.
3. Double-click **Start Review.cmd**. Keep its terminal window open. The browser interface opens at `http://127.0.0.1:8765/`; copy that address into a browser if it does not open automatically.
4. Choose one or more PDFs and select **Extract and review**. The app creates a dated folder under `review-runs` automatically. Previous runs can be reopened from the home page. Press Ctrl+C in the terminal when finished.

If Python is not on PATH, run `./setup.ps1 -Python 'C:\path\to\python.exe'` in PowerShell. If port 8765 is in use, run `./start-review.ps1 -Port 8766`. The app and browser communicate only over your computer's loopback address. Setup downloads Python packages and OCR weights; extraction and review do not send PDFs to external providers.

Compare each page image with the extracted lines and fields. Save corrections in the browser; the JSON and CSV are regenerated and changes go into `audit.jsonl`. Save a page note when text is missing entirely. Name a form type to make future local suggestions from its labels. A suggestion is provisional and does not identify blank fields.

**Privacy:** `review-runs` contains copies of selected PDFs and extracted content. Do not share it unless those documents may be shared. Git ignores runs, PDFs, local model weights, and the virtual environment.

Local PDF extraction. The current testable path is **dump mode**: it renders pages, uses an embedded text layer when usable, runs local PP-OCRv5 on scanned pages, and writes line-level JSON, page Markdown, detected `label: value` fields, CSV, and a self-contained review page. Unclassified fields are flagged for review. The local browser interface adds provisional form grouping from completed examples. Full schema inference, table extraction, checkbox interpretation, and second-reader verification are not yet implemented.

## Local browser review

The double-click launcher runs this command from the project directory:

```powershell
.\.venv\Scripts\ocrpipe.exe review --model-dir .\models --output-root .\review-runs
```

It opens `http://127.0.0.1:8765/` and accepts PDFs selected in the browser. The server binds to your computer's loopback address only, uses no external web assets, and the extraction network guard remains enabled. It creates a dated run folder under `review-runs` containing the input PDFs, page images, JSON, Markdown, CSV, and an audit log. Stop it with Ctrl+C in the terminal.

Review each page image beside its detected text and fields. Save corrections and optional notes directly in the interface; the JSON and CSV are updated, and the old and new values are appended to `audit.jsonl`. Page notes record text that was missed entirely, including curved stamps. The interface suggests groups from recurring field labels. Name a form type to save its label set in `review-runs/form-types.json` for future suggestions. A type remains `unclassified` until you name it. Suggestions with fewer than two labels or weak overlap stay unclassified. These label-based groups are provisional and do not detect missing blank fields.

The interface flags bracket-like checkbox text and unexpected CJK symbols for inspection. It does not yet read handwritten ticks, curved stamp text, or separate letters from intersecting form borders reliably; inspect the page image and record a review note for these cases.

## One-time setup

From this project directory in PowerShell, run:

```powershell
.\setup.ps1 -Python 'C:\path\to\python.exe' -ModelDir '.\models'
```

Use Python 3.11 or 3.12. Setup creates `.venv` and downloads open PP-OCRv5 weights into `models`. This is the only step intended to use the network.

## Process one PDF folder

```powershell
.\.venv\Scripts\ocrpipe.exe run 'D:\Private\PDFs' 'D:\Private\OCR-output' --model-dir '.\models'
```

The input folder is read at its top level only; each PDF is processed separately. Choose a different output folder for each run. Runtime network access is blocked by default.

The local browser interface is the recommended review workflow. The command-line mode also writes a legacy `review.html`. After exporting accepted corrections from that file, apply them with:

```powershell
.\.venv\Scripts\ocrpipe.exe apply-corrections 'D:\Private\corrections.csv' 'D:\Private\OCR-output' --reviewer 'Your name'
```

Outputs: `documents/*.json`, `markdown/*.md`, `unclassified.csv`, `review.html`, and `audit.jsonl` after applying corrections. JSON includes every detected line with its page, box, source, and confidence. Logs show file names and counts, not extracted content.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

All project tests and the end-to-end OCR smoke test use synthetic data.

## How extraction works

1. Each PDF page is rendered to an image at 300 DPI by default. Page images are retained in the run for review.
2. If the page has a usable embedded text layer, characters are grouped into lines. Otherwise, the local PP-OCRv5 model detects and reads text in the page image. The original reading, page, coordinates, and available confidence are retained.
3. A line matching `label: value` becomes a field. If no fields are found on a page, the detected lines are retained as generic line fields. The page Markdown contains the complete detected line sequence.
4. Fields are marked for review. Low OCR confidence adds a separate flag; confidence is a model estimate, not a measured guarantee of correctness. Bracket-like text and unexpected CJK characters receive review flags.
5. Form grouping compares normalized field labels. Groups proposed in a run and labels saved under a user-confirmed form type support future suggestions. There is no trained document classifier or complete expected-field schema yet.
6. The local web server renders the review page. Corrections update the document JSON and CSV, while an append-only audit log records changes and notes.

The source code is in `src/ocrpipe/`: `pdf.py` renders pages, `readers.py` runs local OCR, `extract.py` identifies lines and fields, `pipeline.py` coordinates processing, `schema.py` proposes form groups, `output.py` writes results, and `web.py` serves the local interface. `cli.py` defines the commands.

## Current capabilities and limits

| Area | Current version |
| --- | --- |
| Embedded PDF text | Extracts text and coordinates when the text layer is usable. A text layer can still contain errors. |
| Scanned text | Uses local PP-OCRv5; it has handled some sideways content, but rotation and reading order are not guaranteed. |
| Fields | Recognizes simple `label: value` lines and keeps other lines for review. It cannot infer every field from arbitrary form layouts. |
| Form types | Proposes groups from recurring labels and lets a user confirm a type. `unclassified` means no type has been confirmed. Blank and missing expected fields are not detected. |
| Checkboxes | Flags some bracket-like text for review. Thin handwritten ticks are not reliably classified as checked or unchecked. |
| Stamps and borders | Sideways text may be captured. Circular text, letters touching solid borders, and similar image artifacts can be missed or misread. |
| Tables | Table structure extraction is not implemented. |
| Review | Shows rendered pages, extracted lines, field crops, corrections, and notes. Corrections are local and audited. |

## Privacy and output files

The web server listens on `127.0.0.1`, so the review interface is accessible from the local computer. It does not load remote scripts or send document content to an external OCR service. **One-time setup downloads dependencies and model weights.** Runtime extraction has a network guard enabled by default.

The `review-runs` folder is created next to this project by default. Each dated run stores copies of the input PDFs, rendered page images, JSON with line positions and field crops, page Markdown, CSV summaries, and `audit.jsonl`. `form-types.json` in the output root stores labels from confirmed form types. These files can contain sensitive information. Git excludes them through `.gitignore`; verify the contents before sharing any archive or output folder.
