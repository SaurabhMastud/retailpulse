"""Guards the dbt project against breaking silently as the Python side evolves.

Runs `dbt parse` (Jinja/YAML/ref-graph validation, no warehouse queries) rather
than `dbt run`/`dbt test` -- keeps this fast and independent of warehouse state.
"""
import subprocess
from pathlib import Path

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"


def test_dbt_project_parses_cleanly():
    result = subprocess.run(
        ["dbt", "parse", "--profiles-dir", "."],
        cwd=DBT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
