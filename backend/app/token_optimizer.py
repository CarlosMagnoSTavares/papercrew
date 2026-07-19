"""Native token optimization.

Two techniques applied to every crew run:

1. "Ponytail" prompt discipline — terse-mode instructions, deduplicated and
   whitespace-normalized context, hard max_tokens cap on completions.
2. "Graphify" context graph — dependency outputs are never injected verbatim;
   each dependency contributes a sentence-aware compressed summary within a
   fixed budget, walking the dependency graph breadth-first without cycles.

Everything here is deterministic (no LLM calls), so savings are measurable
and unit-testable. Token estimates use the ~4 chars/token heuristic.
"""
import re

TERSE_SUFFIX = (
    "\n\nStyle rules: be maximally concise. No preamble, no filler, no repetition. "
    "Dense plain prose. Answer only what is asked."
)
MAX_COMPLETION_TOKENS = 2048
DEP_SUMMARY_BUDGET_CHARS = 600
CONTEXT_BUDGET_CHARS = 2400


def estimate_tokens(text: str) -> int:
    return max(0, len(text)) // 4


def compress_text(text: str, budget_chars: int = DEP_SUMMARY_BUDGET_CHARS) -> str:
    """Deterministic compression: normalize whitespace, drop duplicate lines,
    then truncate on a sentence boundary within budget."""
    lines = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    collapsed = "\n".join(lines)
    if len(collapsed) <= budget_chars:
        return collapsed
    cut = collapsed[:budget_chars]
    boundary = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("\n"))
    if boundary > budget_chars // 2:
        cut = cut[: boundary + 1]
    return cut.rstrip() + " …"


def dependency_ids(depends_on: str) -> list[int]:
    return [int(part) for part in depends_on.split(",") if part.strip().isdigit()]


def walk_dependency_graph(task, get_task) -> list:
    """BFS over the dependency graph, cycle-safe, returns dep tasks in order."""
    ordered, queue, visited = [], dependency_ids(task.depends_on), {task.id}
    while queue:
        dep_id = queue.pop(0)
        if dep_id in visited:
            continue
        visited.add(dep_id)
        dep = get_task(dep_id)
        if dep is None:
            continue
        ordered.append(dep)
        queue.extend(dependency_ids(dep.depends_on))
    return ordered


def build_context(task, get_task, get_latest_output) -> tuple[str, int]:
    """Compressed context from the dependency graph.

    Returns (context, tokens_saved) where tokens_saved compares the compressed
    context against injecting every dependency output verbatim.
    """
    deps = walk_dependency_graph(task, get_task)
    raw_total = 0
    parts: list[str] = []
    for dep in deps:
        output = get_latest_output(dep.id)
        if not output:
            continue
        raw = f"Result of '{dep.title}':\n{output}"
        raw_total += len(raw)
        parts.append(f"[{dep.title}] {compress_text(output)}")
    context = compress_text("\n".join(parts), CONTEXT_BUDGET_CHARS) if parts else ""
    saved_chars = max(0, raw_total - len(context))
    return context, saved_chars // 4
