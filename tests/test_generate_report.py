import re

import pypdf

from docs.generate_report import (
    DOCS_DIR,
    _inline,
    _is_separator,
    _sanitize,
    _split_row,
    build_report,
)


def _text(pdf_path):
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(str(pdf_path)).pages)


def test_build_report_writes_a_nonempty_pdf(tmp_path):
    output = build_report(tmp_path / "report.pdf")

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000


def test_architecture_doc_sanitizes_without_losing_characters():
    """Anything outside latin-1 that _UNSUPPORTED doesn't map becomes '?' in the
    PDF -- silently, since fpdf2 is handed already-clean text. The smoke test
    above still passes on a report full of '?', so the check lives here."""
    raw = (DOCS_DIR / "ARCHITECTURE.md").read_text(encoding="utf-8").splitlines()
    clean = _sanitize("\n".join(raw)).splitlines()

    introduced = [
        (number, line)
        for number, (line, source) in enumerate(zip(clean, raw), start=1)
        if "?" in line and "?" not in source
    ]
    assert not introduced, f"unmapped characters render as '?': {introduced[:5]}"


def test_split_row_drops_separators_and_inline_markdown():
    assert _split_row("| `code` | **bold** |") == ["code", "bold"]
    assert _is_separator(["---", ":---:"])
    assert not _is_separator(["Component", "Tool"])


def test_inline_keeps_snake_case_and_globs_intact():
    # Stripping "_" as emphasis mangled every identifier in the report:
    # session_id -> sessionid, CATALOG_SEED -> CATALOGSEED, dbt_utils -> dbtutils.
    assert _inline("`session_id` lets funnel_conversion group page_view") == (
        "session_id lets funnel_conversion group page_view"
    )
    assert _inline("a plain test (`dbt/tests/assert_*.sql`)") == (
        "a plain test (dbt/tests/assert_*.sql)"
    )
    # Asterisk emphasis outside a code span still goes.
    assert _inline("**Marts at daily grain**, not *all-time*") == (
        "Marts at daily grain, not all-time"
    )


def test_report_does_not_mangle_identifiers(tmp_path):
    text = _text(build_report(tmp_path / "report.pdf"))

    # Presence is the whole check: when "_" was being stripped as emphasis, no
    # underscored form survived anywhere in the document. Asserting the stripped
    # form is *absent* would additionally forbid the decisions log from quoting
    # "sessionid" as the example of the bug, which it does.
    for identifier in ("session_id", "funnel_conversion", "CATALOG_SEED", "top_products"):
        assert identifier in text, f"{identifier} was mangled in the report"


def test_markdown_tables_render_as_tables_not_pipe_text(tmp_path):
    text = _text(build_report(tmp_path / "report.pdf"))

    # The components table's cells survive...
    assert "Event generator" in text
    assert "Immutable raw event storage, one file per batch" in text
    # ...without the pipes or the |---|---| separator row they arrived in.
    assert "| Component | Tool | Role |" not in text
    # Anchored to whole lines: the prose legitimately discusses "|---|---|" when
    # explaining this very renderer, and that is not a rendered separator row.
    rendered_separators = [
        line for line in text.splitlines() if re.fullmatch(r"\s*\|[-|: ]+\|\s*", line)
    ]
    assert not rendered_separators, rendered_separators


def test_fenced_diagram_keeps_its_pipes(tmp_path):
    """The data-flow diagram is drawn with pipes inside a code fence. The fence
    branch has to be checked before the table branch or the diagram is parsed
    into a mangled table."""
    text = _text(build_report(tmp_path / "report.pdf"))

    assert "|--> raw_events" in text


def test_report_is_byte_reproducible(tmp_path):
    """fpdf2 stamps a creation date into the file. Left as "now", the committed
    PDF changes on every regeneration and a git diff on it means nothing."""
    first = build_report(tmp_path / "a.pdf").read_bytes()
    second = build_report(tmp_path / "b.pdf").read_bytes()

    assert first == second


def test_pinned_stack_appendix_comes_from_requirements(tmp_path):
    text = _text(build_report(tmp_path / "report.pdf"))

    for line in (DOCS_DIR.parent / "requirements.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        package, _, version = line.strip().partition("==")
        assert package in text, f"{package} missing from the stack appendix"
        assert version in text, f"{package}'s pinned version missing"
