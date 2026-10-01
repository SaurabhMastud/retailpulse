from docs.generate_report import DOCS_DIR, _sanitize, build_report


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
