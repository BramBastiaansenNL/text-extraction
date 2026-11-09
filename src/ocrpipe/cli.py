"""Command line entry point."""

from pathlib import Path

import typer

from .config import load_config
from .offline import offline_guard, set_offline_environment
from .pipeline import process
from .output import apply_corrections as merge_corrections

app = typer.Typer(help="Local, privacy-preserving document extraction.")


@app.command()
def review(output_root: Path = typer.Option(Path("review-runs"), help="Local folder for new runs"),
           model_dir: Path | None = typer.Option(None, help="Local OCR weights directory"),
           port: int = typer.Option(8765, min=1, max=65535),
           open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser")) -> None:
    """Open the loopback-only extraction and review interface."""
    from .web import serve
    serve(output_root, model_dir, port, open_browser)


@app.command()
def check_config(config: Path | None = typer.Option(None, exists=True, dir_okay=False), offline_guard_enabled: bool = typer.Option(True, "--offline-guard/--no-offline-guard")) -> None:
    """Validate configuration without reading documents."""
    set_offline_environment()
    guard = offline_guard() if offline_guard_enabled else None
    if guard is None:
        load_config(config)
    else:
        with guard:
            load_config(config)
    typer.echo("Configuration valid")


@app.command()
def run(input_dir: Path, output_dir: Path, config: Path | None = None,
        mode: str = typer.Option("dump", help="Extraction mode"),
        model_dir: Path | None = typer.Option(None, help="Local OCR weights directory"),
        offline_guard_enabled: bool = typer.Option(True, "--offline-guard/--no-offline-guard"),
        debug_content: bool = typer.Option(False, "--debug-content")) -> None:
    """Process a folder of PDFs fully offline."""
    settings = load_config(config)
    settings.offline_guard = offline_guard_enabled
    settings.debug_content = debug_content
    if mode != "dump":
        raise typer.BadParameter("Only dump mode is implemented")
    count = process(input_dir, output_dir, settings, mode, model_dir)
    typer.echo(f"Processed {count} documents")


@app.command("apply-corrections")
def apply_corrections(corrections_csv: Path, output_dir: Path, reviewer: str = "local-user") -> None:
    """Merge accepted review edits and record an audit trail."""
    count = merge_corrections(corrections_csv, output_dir, reviewer)
    typer.echo(f"Applied {count} corrections")
