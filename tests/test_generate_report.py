from docs.generate_report import build_report


def test_build_report_writes_a_nonempty_pdf(tmp_path):
    output = build_report(tmp_path / "report.pdf")

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
