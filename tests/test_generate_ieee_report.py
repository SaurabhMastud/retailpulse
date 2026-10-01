"""Covers the IEEE-style project report.

Split across two kinds of check. The structural ones read the *committed* PDF
and run everywhere, so a clone without LaTeX still verifies the artifact it was
shipped. The build ones need pdflatex and skip when it is absent, the same way
the Airflow DAG check skips where Airflow cannot be installed.
"""
import re

import pypdf
import pytest

from docs import generate_ieee_report as ieee

needs_pdflatex = pytest.mark.skipif(
    not ieee.pdflatex_available(), reason="pdflatex not installed; cannot rebuild the paper"
)


def _flat(path):
    text = "\n".join(page.extract_text() for page in pypdf.PdfReader(str(path)).pages)
    # pypdf drops the spaces between IEEEtran's small-caps runs, so section
    # headings extract as "BACKGROUND ANDRELATEDWORK". Compare without spaces.
    return re.sub(r"\s+", "", text)


def test_committed_report_is_three_to_four_pages():
    pages = len(pypdf.PdfReader(str(ieee.OUTPUT)).pages)
    assert 3 <= pages <= 4, f"the paper is {pages} pages; it is specified as 3-4"


def test_committed_report_has_the_expected_paper_structure():
    flat = _flat(ieee.OUTPUT)

    for section in (
        "Abstract",
        "INTRODUCTION",
        "BACKGROUNDANDRELATEDWORK",
        "SYSTEMARCHITECTURE",
        "IMPLEMENTATION",
        "DATA-QUALITYSTRATEGY",
        "EVALUATION",
        "DISCUSSION",
        "CONCLUSION",
        "REFERENCES",
    ):
        assert section in flat, f"{section} missing from the paper"


def test_committed_report_has_no_unresolved_cross_references():
    # LaTeX prints "??" for a \ref whose \label it never found.
    assert "??" not in _flat(ieee.OUTPUT)


def test_committed_report_states_the_unexercised_dag():
    """The paper's threats-to-validity section is the honest-scope part; if it
    ever gets trimmed, the report starts implying a running Airflow DAG."""
    flat = _flat(ieee.OUTPUT)

    assert "threatstovalidity" in flat.lower()
    assert "neverbeenexecuted" in flat.lower()


@needs_pdflatex
def test_report_builds_from_source(tmp_path):
    built = ieee.build_report(tmp_path / "paper.pdf")

    assert built.read_bytes().startswith(b"%PDF")
    assert 3 <= len(pypdf.PdfReader(str(built)).pages) <= 4


@needs_pdflatex
def test_report_is_byte_reproducible(tmp_path):
    """pdfTeX stamps the build time in unless SOURCE_DATE_EPOCH pins it, which
    would make the committed PDF byte-different on every rebuild."""
    first = ieee.build_report(tmp_path / "a.pdf").read_bytes()
    second = ieee.build_report(tmp_path / "b.pdf").read_bytes()

    assert first == second
