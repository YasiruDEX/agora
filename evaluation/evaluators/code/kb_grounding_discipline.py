import re

from amp_evaluation import EvalResult
from amp_evaluation.trace.models import Trace


def kb_grounding_discipline(
    trace: Trace,
    kb_tools: str = "kb_search,kb_read",
    long_answer_chars: int = 400,
) -> EvalResult:
    """Did the agent consult the knowledge base before stating policy facts?

    1.0  a KB lookup ran before the answer
    0.5  no KB lookup, long answer but no figures, dates or amounts
    0.0  no KB lookup and the answer states figures, dates or amounts
    skip no answer, or a short answer with nothing checkable (greeting, hand-off)
    """
    answer = (trace.output or "").strip()
    if not answer:
        return EvalResult.skip("No answer to evaluate")

    wanted = {t.strip() for t in kb_tools.split(",") if t.strip()}
    called = [span.name for span in trace.get_tool_calls()]
    lookups = [name for name in called if name in wanted]
    if lookups:
        return EvalResult(
            score=1.0,
            explanation=f"Knowledge base consulted before answering ({', '.join(lookups)}).",
        )

    specifics = re.findall(
        r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\s?%|\b\d+\s+(?:business |calendar )?(?:days?|weeks?|months?|years?)\b"
        r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b",
        answer,
        flags=re.IGNORECASE,
    )
    if specifics:
        shown = ", ".join(dict.fromkeys(s.strip() for s in specifics[:4]))
        return EvalResult(
            score=0.0,
            passed=False,
            explanation=f"Answer states specifics ({shown}) but no knowledge-base lookup ran in this trace.",
        )
    if len(answer) >= long_answer_chars:
        return EvalResult(
            score=0.5,
            passed=False,
            explanation="Long answer given from model memory: no knowledge-base lookup ran in this trace.",
        )
    return EvalResult.skip("Short answer with no policy facts to ground")
