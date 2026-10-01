"""Compile docs/retailpulse-ieee.tex into the IEEE-style project report.

Separate from generate_report.py on purpose: that one renders ARCHITECTURE.md
with fpdf2 and needs no system dependency, while this one is a LaTeX document
with its own source. They produce different documents for different readers --
the architecture report is the full written record, this is the 4-page paper.

latexmk would normally drive the multi-pass loop, but it is a Perl script and
the MiKTeX install here has no Perl script engine, so it fails before reading
the document. pdflatex is therefore called directly, re-running only while the
log still asks for it. That is safe for this document specifically: the
bibliography is an inline thebibliography (no bibtex pass) and the only
cross-references are \\label/\\ref, which settle in two passes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

DOCS_DIR = Path(__file__).parent
SOURCE = DOCS_DIR / "retailpulse-ieee.tex"
OUTPUT = DOCS_DIR / "retailpulse-ieee-report.pdf"

# Matches docs/generate_report.py's REPORT_DATE. pdfTeX stamps the build time
# into the PDF unless pinned, which would make the committed artifact
# byte-different on every rebuild -- see ARCHITECTURE.md's decisions log.
SOURCE_DATE_EPOCH = "1790000000"


BUILD_DIR = DOCS_DIR / "latex-build"
MAX_PASSES = 3


def pdflatex_available() -> bool:
    return shutil.which("pdflatex") is not None


def build_report(output_path: Path | None = None) -> Path:
    """Compile the paper. Raises CalledProcessError carrying the pdflatex output."""
    output_path = output_path or OUTPUT
    env = {
        **os.environ,
        "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
        # Without FORCE_SOURCE_DATE, pdfTeX honours SOURCE_DATE_EPOCH for
        # \pdfcreationdate but not for the document's own timestamps.
        "FORCE_SOURCE_DATE": "1",
    }
    for _ in range(MAX_PASSES):
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-output-directory={BUILD_DIR}",
                SOURCE.name,
            ],
            cwd=DOCS_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        if "Rerun" not in result.stdout:
            break

    built = BUILD_DIR / f"{SOURCE.stem}.pdf"
    shutil.copyfile(built, output_path)
    return output_path


if __name__ == "__main__":
    path = build_report()
    print(f"wrote {path}")
