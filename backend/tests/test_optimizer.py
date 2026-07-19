"""Unit tests for the native token optimizer (ponytail + graphify techniques)."""
from types import SimpleNamespace

from app.token_optimizer import (
    build_context,
    compress_text,
    dependency_ids,
    estimate_tokens,
    walk_dependency_graph,
)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 400) == 100


def test_compress_normalizes_and_dedupes():
    text = "Hello   world\n\nHello   world\nSecond    line"
    out = compress_text(text)
    assert out == "Hello world\nSecond line"


def test_compress_respects_budget_on_sentence_boundary():
    text = ("First sentence is here. " * 100).strip()
    out = compress_text(text, budget_chars=200)
    assert len(out) <= 205
    assert out.endswith("…")


def test_dependency_ids_parsing():
    assert dependency_ids("1,2, 7") == [1, 2, 7]
    assert dependency_ids("") == []
    assert dependency_ids("abc,3") == [3]


def _task(task_id, depends_on=""):
    return SimpleNamespace(id=task_id, title=f"T{task_id}", depends_on=depends_on)


def test_walk_graph_transitive_and_cycle_safe():
    tasks = {
        1: _task(1, "2"),
        2: _task(2, "3"),
        3: _task(3, "1"),  # cycle back to 1
    }
    ordered = walk_dependency_graph(tasks[1], tasks.get)
    assert [t.id for t in ordered] == [2, 3]


def test_build_context_compresses_and_reports_savings():
    tasks = {1: _task(1, "2"), 2: _task(2)}
    long_output = "Useful fact. " * 500  # ~6500 chars raw
    context, saved = build_context(tasks[1], tasks.get, lambda _tid: long_output)
    assert "[T2]" in context
    assert len(context) < len(long_output)
    assert saved > 0


def test_build_context_empty_without_deps():
    context, saved = build_context(_task(1), lambda _tid: None, lambda _tid: "")
    assert context == ""
    assert saved == 0
