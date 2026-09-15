"""Render docs/retailpulse-report.pdf from ARCHITECTURE.md.

Used by the day-7 close-out; kept as a standalone script so it can also be
re-run any time the architecture doc changes.
"""
from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

DOCS_DIR = Path(__file__).parent

# The core Helvetica/Courier fonts only support latin-1 -- ARCHITECTURE.md's
# em/en dashes, curly quotes, and arrows all fall outside that range.
_UNSUPPORTED = {
    "→": "->", "←": "<-", "↔": "<->",
    "—": "--", "–": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
}


def _sanitize(text: str) -> str:
    for char, replacement in _UNSUPPORTED.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _add_markdown(pdf: FPDF, text: str) -> None:
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not stripped:
            pdf.ln(2)
            continue
        if in_code_block:
            # cell() clips instead of wrapping -- code/diagram lines are
            # meant to stay on one line, and some (box-drawing ASCII) have no
            # safe wrap point that multi_cell can break on.
            pdf.set_font("Courier", "", 7)
            pdf.cell(0, 4, line[:180], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            continue
        if stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.ln(2)
            pdf.multi_cell(0, 7, stripped[4:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.ln(3)
            pdf.multi_cell(0, 8, stripped[3:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 10, stripped[2:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(
                0, 6, re.sub(r"[`*_]", "", stripped), new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )


def build_report(output_path: Path | None = None) -> Path:
    output_path = output_path or DOCS_DIR / "retailpulse-report.pdf"
    architecture = _sanitize((DOCS_DIR / "ARCHITECTURE.md").read_text(encoding="utf-8"))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.multi_cell(0, 14, "RetailPulse", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0,
        7,
        "Week 01 - Data Engineering - github.com/SaurabhMastud/retailpulse",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(6)

    _add_markdown(pdf, architecture)

    pdf.output(str(output_path))
    return output_path


if __name__ == "__main__":
    path = build_report()
    print(f"wrote {path}")
