"""Guard the test counts the README states in prose.

The README advertises "N tests" and "N dbt data tests". Both numbers went stale
and were hand-corrected on four separate days, which is the same generated-value-
stated-in-two-places problem tests/test_catalog.py guards for the product seed.

Collection runs in a subprocess rather than reading request.session.items, so the
check gives the same answer whether the full suite or a single file is invoked.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
README = PROJECT_ROOT / "README.md"


def _stated(pattern: str) -> int:
    match = re.search(pattern, README.read_text(encoding="utf-8"))
    assert match, f"README no longer states a count matching {pattern!r}"
    return int(match.group(1))


def test_readme_pytest_count_matches_collection():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    collected = int(re.search(r"(\d+) tests? collected", result.stdout).group(1))

    # The README counts the Airflow-only DagBag test separately ("plus one
    # that's skipped"), but collection counts it like any other test.
    assert _stated(r"(\d+) tests plus one that's skipped") == collected - 1


def test_readme_dbt_test_count_matches_the_project():
    # `dbt list` is asked rather than the schema YAML parsed: a regex over the
    # yml files has to hardcode which generic test names to look for, so adding
    # one dbt knows about and the regex doesn't would under-count silently --
    # exactly the drift this test exists to catch.
    result = subprocess.run(
        ["dbt", "list", "--profiles-dir", ".", "--resource-type", "test", "--output", "name"],
        cwd=PROJECT_ROOT / "dbt",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    names = [
        line for line in result.stdout.splitlines()
        if line.strip() and not re.match(r"^\d\d:\d\d:\d\d", line)
    ]

    assert _stated(r"(\d+) dbt data tests") == len(names)
