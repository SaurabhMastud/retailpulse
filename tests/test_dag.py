"""Structure checks for the Airflow DAG.

Two layers, because Airflow has no native Windows support and isn't installed
on the development machine:

- the AST checks run everywhere and catch the failure this DAG is actually
  prone to -- task wiring drifting from the documented order, or a task
  calling a pipeline function that no longer exists
- the import check runs only where Airflow is installed, and validates the
  real DAG object

Without the AST layer this file would be a single always-skipped test, which
is the same as no test at all.
"""
import ast
from pathlib import Path

import pytest

from src import pipeline

DAG_PATH = Path(__file__).resolve().parent.parent / "dags" / "retailpulse_pipeline.py"
EXPECTED_TASKS = ["generate_events", "ingest_events", "dbt_seed", "dbt_run", "dbt_test"]


@pytest.fixture(scope="module")
def dag_ast() -> ast.Module:
    return ast.parse(DAG_PATH.read_text(encoding="utf-8"))


def test_dag_defines_the_expected_tasks(dag_ast):
    task_ids = [
        kw.value.value
        for node in ast.walk(dag_ast)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "task_id" and isinstance(kw.value, ast.Constant)
    ]
    assert task_ids == EXPECTED_TASKS


def test_dag_wires_tasks_in_pipeline_order(dag_ast):
    # `a >> b >> c >> d` parses as nested BinOp(RShift); flattening the
    # left spine recovers the declared order
    chains = [
        node
        for node in ast.walk(dag_ast)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift)
    ]
    assert chains, "no >> dependency chain found in the DAG"

    longest = max(chains, key=lambda n: len(ast.dump(n)))
    order = []
    while isinstance(longest, ast.BinOp) and isinstance(longest.op, ast.RShift):
        order.insert(0, longest.right.id)
        longest = longest.left
    order.insert(0, longest.id)

    assert order == EXPECTED_TASKS


def test_dag_only_calls_pipeline_functions_that_exist(dag_ast):
    called = {
        node.func.attr
        for node in ast.walk(dag_ast)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pipeline"
    }
    assert called, "DAG should delegate to src.pipeline"
    for name in called:
        assert hasattr(pipeline, name), f"DAG calls pipeline.{name}(), which does not exist"


def test_dag_imports_and_has_the_right_shape():
    pytest.importorskip("airflow", reason="Airflow has no native Windows support")
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder=str(DAG_PATH.parent), include_examples=False)
    assert not dagbag.import_errors, dagbag.import_errors

    dag = dagbag.get_dag("retailpulse_pipeline")
    assert dag is not None
    assert sorted(t.task_id for t in dag.tasks) == sorted(EXPECTED_TASKS)
    assert dag.get_task("ingest_events").upstream_task_ids == {"generate_events"}
    assert dag.get_task("dbt_run").upstream_task_ids == {"dbt_seed"}
    assert dag.get_task("dbt_test").upstream_task_ids == {"dbt_run"}
