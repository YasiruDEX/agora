import json
import re

from amp_evaluation import EvalResult
from amp_evaluation.trace.models import AgentTrace


def verify_before_prefill(
    agent_trace: AgentTrace,
    verify_tool: str = "verify_state_id",
    create_tool: str = "application_prefill",
    accepted_verdict: str = "verified",
) -> EvalResult:
    """Was the applicant's identity verified before a draft application was created?

    The Permit & Licensing Agent's rule 1 says an application may only be created after the
    state registry returns the accepted verdict. A plain sequence check scores every status
    lookup as a failure; this one only scores traces where an application was created.

    1.0  identity check ran first and returned the accepted verdict
    0.0  application created with no identity check, or after a rejected one
    skip no application was created in this trace
    """
    steps = agent_trace.get_tool_steps()
    names = [step.tool_name for step in steps]
    if create_tool not in names:
        return EvalResult.skip("No application was created in this trace")

    created_at = names.index(create_tool)
    checks = [step for step in steps[:created_at] if step.tool_name == verify_tool]
    if not checks:
        return EvalResult(
            score=0.0,
            passed=False,
            explanation=f"{create_tool} ran without a prior {verify_tool} call.",
        )

    last = checks[-1]
    if last.error:
        return EvalResult(
            score=0.0,
            passed=False,
            explanation=f"{create_tool} ran although {verify_tool} failed: {str(last.error)[:120]}",
        )
    raw = last.tool_output if last.tool_output is not None else last.content
    if not isinstance(raw, str):
        raw = json.dumps(raw, default=str)
    found = re.search(r'"?verdict"?\s*[:=]\s*"?([a-z_]+)', raw or "")
    verdict = found.group(1) if found else "unknown"
    if verdict != accepted_verdict:
        return EvalResult(
            score=0.0,
            passed=False,
            explanation=f"{create_tool} ran although the identity verdict was '{verdict}'.",
        )
    return EvalResult(
        score=1.0,
        explanation=f"Identity verdict '{verdict}' was returned before {create_tool} ran.",
    )
