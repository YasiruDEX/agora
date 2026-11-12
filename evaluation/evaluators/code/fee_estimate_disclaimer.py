import re

from amp_evaluation import EvalResult
from amp_evaluation.trace.models import Trace


def fee_estimate_disclaimer(
    trace: Trace,
    fee_tool: str = "fee_schedule_read",
    required_words: str = "estimate,estimated,approximate,approximately",
) -> EvalResult:
    """When a fee is quoted, did it come from the fee schedule and is it called an estimate?

    The Permit & Licensing Agent's rule 2: every quoted fee is an estimate confirmed at plan
    check, read from the fee schedule.

    1.0  fee schedule was read and the answer calls the amount an estimate
    0.5  only one of the two
    0.0  a dollar amount is quoted with neither
    skip no dollar amount in the answer
    """
    answer = trace.output or ""
    amounts = re.findall(r"\$\s?\d[\d,]*(?:\.\d+)?", answer)
    if not amounts:
        return EvalResult.skip("No fee quoted in the answer")

    read_schedule = any(span.name == fee_tool for span in trace.get_tool_calls())
    words = [w.strip().lower() for w in required_words.split(",") if w.strip()]
    lowered = answer.lower()
    says_estimate = any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in words)

    score = (0.5 if read_schedule else 0.0) + (0.5 if says_estimate else 0.0)
    problems = []
    if not read_schedule:
        problems.append(f"{fee_tool} was not called")
    if not says_estimate:
        problems.append("the amount is not described as an estimate")
    if problems:
        return EvalResult(
            score=score,
            passed=False,
            explanation=f"Quoted {amounts[0]}, but " + " and ".join(problems) + ".",
        )
    return EvalResult(
        score=1.0,
        explanation=f"Quoted {amounts[0]} from the fee schedule and described it as an estimate.",
    )
