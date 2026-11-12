import json
import re

from amp_evaluation import EvalResult
from amp_evaluation.trace.models import Trace


def source_citation(
    trace: Trace,
    kb_tools: str = "kb_search,kb_read",
    min_title_words_matched: int = 2,
) -> EvalResult:
    """When the answer gives a figure, deadline or rule, does it name the article it came from?

    The agent's rule 3 (CITE) requires the source title next to any specific figure. The
    titles are read from the knowledge-base tool results in the same trace, so the check
    needs no list of articles in its config.

    1.0  a retrieved article is named in the answer
    0.0  specifics given, articles were retrieved, none is named
    skip no specifics in the answer, or nothing was retrieved to cite
    """
    answer = (trace.output or "").strip()
    if not answer:
        return EvalResult.skip("No answer to evaluate")
    if not re.search(r"\$\s?\d|\b\d+(?:\.\d+)?\s?%|\b\d+\s+(?:business |calendar )?(?:days?|weeks?|months?)\b", answer, re.I):
        return EvalResult.skip("Answer has no figure or deadline that needs a citation")

    wanted = {t.strip() for t in kb_tools.split(",") if t.strip()}
    titles = []
    for span in trace.get_tool_calls():
        if span.name not in wanted:
            continue
        raw = span.result
        if not isinstance(raw, str):
            raw = json.dumps(raw, default=str)
        titles.extend(re.findall(r'"source"\s*:\s*"([^"]+)"', raw))
    titles = list(dict.fromkeys(titles))
    if not titles:
        return EvalResult.skip("No knowledge-base article was retrieved, so there is nothing to cite")

    answer_lower = answer.lower()
    for title in titles:
        if title.lower() in answer_lower:
            return EvalResult(score=1.0, explanation=f"Answer cites '{title}'.")
        words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 3]
        hits = [w for w in words if w in answer_lower]
        if words and len(hits) >= min(min_title_words_matched, len(words)):
            return EvalResult(score=1.0, explanation=f"Answer refers to '{title}'.")

    return EvalResult(
        score=0.0,
        passed=False,
        explanation=f"Answer gives specifics but names none of the {len(titles)} retrieved article(s): "
        + "; ".join(titles[:3]),
    )
