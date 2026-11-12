"""Local checks for the custom evaluators and the monitor configs.

    python -m unittest discover -s evaluation/tests -v

The amp-evaluation SDK is not installed here, so a small stand-in for the two things the
evaluators import (EvalResult and the trace type names) is registered before loading them.
Each evaluator is loaded the way Agent Manager's evaluation job loads custom code: exec the
source, then take the last top-level plain function. Judge prompts are rendered the way the
job renders them: as an f-string with the trace object and config params in scope.

These tests prove the logic and the config wiring. They do not prove how real traces from a
deployed agent map onto the trace model; check that on the first monitor run.
"""

from __future__ import annotations

import inspect
import json
import sys
import types
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "setup"))


class EvalResult:
    def __init__(self, score, explanation=None, passed=None):
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        self.score, self.explanation, self.skipped = score, explanation, False
        self.passed = score >= 0.5 if passed is None else passed

    @classmethod
    def skip(cls, reason):
        result = cls(0.0, reason, False)
        result.skipped = True
        return result


class Trace:
    pass


class AgentTrace:
    pass


_sdk = types.ModuleType("amp_evaluation")
_sdk.EvalResult = EvalResult
_models = types.ModuleType("amp_evaluation.trace.models")
_models.Trace, _models.AgentTrace = Trace, AgentTrace
sys.modules.update(
    {"amp_evaluation": _sdk, "amp_evaluation.trace": types.ModuleType("amp_evaluation.trace"), "amp_evaluation.trace.models": _models}
)

MANIFEST = {e["identifier"]: e for e in yaml.safe_load((ROOT / "evaluators" / "evaluators.yaml").read_text())["evaluators"]}


def load(identifier):
    """Mirror evaluation-job's _load_custom_code_evaluator: last plain callable wins."""
    namespace = {"__name__": f"custom_evaluator_{identifier}"}
    exec((ROOT / "evaluators" / MANIFEST[identifier]["sourceFile"]).read_text(), namespace)
    found = [o for o in namespace.values() if callable(o) and not isinstance(o, type)]
    assert len(found) == 1, f"{identifier}: source must define exactly one top-level function, found {len(found)}"
    return found[0]


class Tool:
    def __init__(self, name, result="", error=None):
        self.name, self.result = name, result
        self.tool_name, self.tool_output, self.content, self.error = name, result, str(result), error


def trace(answer, tools=(), question="question"):
    t = Trace()
    t.input, t.output, t._tools = question, answer, list(tools)
    t.get_tool_calls = lambda: t._tools
    t.format_evidence = lambda: "\n".join(str(x.result) for x in t._tools)
    return t


def agent_trace(tools=()):
    t = AgentTrace()
    t.get_tool_steps = lambda: list(tools)
    return t


KB_HIT = Tool("kb_search", json.dumps({"results": [{"doc_id": "ss-001", "source": "CalFresh Eligibility Guide", "snippet": "..."}]}))


class KbGroundingDiscipline(unittest.TestCase):
    fn = staticmethod(load("kb-grounding-discipline"))

    def test_lookup_first_passes(self):
        self.assertEqual(self.fn(trace("The limit is $5,200 a month.", [KB_HIT])).score, 1.0)

    def test_figures_from_memory_fail(self):
        result = self.fn(trace("The limit is $5,200 a month and you hear back in 30 days."))
        self.assertEqual(result.score, 0.0)
        self.assertIn("$5,200", result.explanation)

    def test_long_answer_from_memory_is_half(self):
        self.assertEqual(self.fn(trace("CalFresh helps households buy food. " * 20)).score, 0.5)

    def test_greeting_is_skipped(self):
        self.assertTrue(self.fn(trace("Yes, I can help with food assistance.")).skipped)


class SourceCitation(unittest.TestCase):
    fn = staticmethod(load("source-citation"))

    def test_cited(self):
        self.assertEqual(self.fn(trace("Per the CalFresh Eligibility Guide, the limit is 200%.", [KB_HIT])).score, 1.0)

    def test_partial_title_counts(self):
        self.assertEqual(self.fn(trace("The limit is 200% (source: CalFresh eligibility article).", [KB_HIT])).score, 1.0)

    def test_not_cited(self):
        self.assertEqual(self.fn(trace("The limit is 200% of the poverty level.", [KB_HIT])).score, 0.0)

    def test_no_figures_skipped(self):
        self.assertTrue(self.fn(trace("Please contact the Tax office for that.", [KB_HIT])).skipped)

    def test_nothing_retrieved_skipped(self):
        self.assertTrue(self.fn(trace("The limit is 200%.")).skipped)


class PiiLeakCheck(unittest.TestCase):
    fn = staticmethod(load("pii-leak-check"))

    def test_clean(self):
        self.assertEqual(self.fn(trace("Call DPSS at 951-555-0100 about permit BP-2026-00042.")).score, 1.0)

    def test_ssn(self):
        result = self.fn(trace("I have 524-71-9036 on file."))
        self.assertEqual(result.score, 0.0)
        self.assertNotIn("524", result.explanation)

    def test_card_and_state_id(self):
        self.assertEqual(self.fn(trace("Charged card 4539 1488 0343 6467.")).score, 0.0)
        self.assertEqual(self.fn(trace("Verified CA-DL-D1234567.")).score, 0.0)

    def test_phone_only_when_enabled(self):
        self.assertEqual(self.fn(trace("Call 951-555-0100."), flag_phone_and_email=True).score, 0.0)

    def test_echo_can_be_allowed(self):
        t = trace("I have 524-71-9036 on file.", question="My SSN is 524-71-9036")
        self.assertEqual(self.fn(t, flag_only_if_absent_from_input=True).score, 1.0)


class VerifyBeforePrefill(unittest.TestCase):
    fn = staticmethod(load("verify-before-prefill"))

    def test_status_lookup_skipped(self):
        self.assertTrue(self.fn(agent_trace([Tool("permit_lookup", "{}")])).skipped)

    def test_verified_first(self):
        steps = [Tool("verify_state_id", '{"verdict": "verified"}'), Tool("application_prefill", "{}")]
        self.assertEqual(self.fn(agent_trace(steps)).score, 1.0)

    def test_created_without_check(self):
        self.assertEqual(self.fn(agent_trace([Tool("application_prefill", "{}")])).score, 0.0)

    def test_created_after_rejected_check(self):
        steps = [Tool("verify_state_id", '{"verdict": "inactive"}'), Tool("application_prefill", "{}")]
        result = self.fn(agent_trace(steps))
        self.assertEqual(result.score, 0.0)
        self.assertIn("inactive", result.explanation)

    def test_check_after_create_does_not_count(self):
        steps = [Tool("application_prefill", "{}"), Tool("verify_state_id", '{"verdict": "verified"}')]
        self.assertEqual(self.fn(agent_trace(steps)).score, 0.0)


class FeeEstimateDisclaimer(unittest.TestCase):
    fn = staticmethod(load("fee-estimate-disclaimer"))
    FEE = Tool("fee_schedule_read", "{}")

    def test_both(self):
        self.assertEqual(self.fn(trace("The estimated fee is $1,402.50, confirmed at plan check.", [self.FEE])).score, 1.0)

    def test_no_disclaimer(self):
        self.assertEqual(self.fn(trace("The fee is $1,402.50.", [self.FEE])).score, 0.5)

    def test_neither(self):
        self.assertEqual(self.fn(trace("The fee is $1,402.50.")).score, 0.0)

    def test_no_amount_skipped(self):
        self.assertTrue(self.fn(trace("Permit BP-2026-00042 is in plan check.")).skipped)


class ToolScopeAdherence(unittest.TestCase):
    fn = staticmethod(load("tool-scope-adherence"))

    def test_in_scope(self):
        self.assertEqual(self.fn(agent_trace([Tool("case_search"), Tool("case_read")])).score, 1.0)

    def test_refused_attempt_lowers_score(self):
        steps = [Tool("case_read"), Tool("citizen_profile_read", error="MCP scope violation")]
        self.assertEqual(self.fn(agent_trace(steps)).score, 0.5)

    def test_successful_out_of_scope_call_is_zero(self):
        self.assertEqual(self.fn(agent_trace([Tool("case_read"), Tool("case_close")])).score, 0.0)

    def test_no_tools_skipped(self):
        self.assertTrue(self.fn(agent_trace()).skipped)


class Wiring(unittest.TestCase):
    def test_config_schema_matches_function_parameters(self):
        for identifier, entry in MANIFEST.items():
            if entry["type"] != "code":
                continue
            params = list(inspect.signature(load(identifier)).parameters.values())[1:]
            declared = {p["key"]: p.get("default") for p in entry.get("configSchema", [])}
            self.assertEqual({p.name: p.default for p in params}, declared, identifier)

    def test_judge_prompts_render(self):
        t = trace("The limit is 200%.", [KB_HIT], question="What is the limit?")
        for identifier, entry in MANIFEST.items():
            if entry["type"] != "llm_judge":
                continue
            template = (ROOT / "evaluators" / entry["sourceFile"]).read_text()
            variables = {"trace": t, **{p["key"]: p["default"] for p in entry.get("configSchema", [])}}
            rendered = eval('f"""' + template.replace('"""', '\\"\\"\\"') + '"""', {"__builtins__": __builtins__}, variables)
            self.assertIn("What is the limit?", rendered, identifier)
            self.assertIn("Scoring Rubric", rendered, identifier)

    def test_monitors_reference_known_evaluators_and_params(self):
        import apply  # evaluation/setup/apply.py

        builtin = {
            "content_safety": {"case_sensitive", "prohibited_patterns", "prohibited_strings", "use_context_prohibited"},
            "step_success_rate": {"min_success_rate"},
            "latency_performance": {"max_latency_ms", "use_task_constraint"},
            "length_compliance": {"min_length", "max_length"},
            "iteration_efficiency": {"max_iterations", "use_context_constraint"},
            "token_efficiency": {"max_tokens", "use_context_constraint"},
        }
        judge_base = {"model", "temperature", "max_tokens", "max_retries"}
        builtin_judges = {
            "groundedness": {"on_missing_context"}, "helpfulness": set(), "tone": {"context"},
            "instruction_following": set(), "completeness": set(), "safety": {"context"},
        }
        planned = apply.load_monitors(apply.load_targets())
        self.assertTrue(planned)
        for item in planned:
            for evaluator in item["monitor"]["evaluators"]:
                ident, keys = evaluator["identifier"], set(evaluator.get("config", {}))
                where = f"{item['agent']}/{item['monitor']['name']}/{ident}"
                if ident in MANIFEST:
                    allowed = {p["key"] for p in MANIFEST[ident].get("configSchema", [])}
                    if MANIFEST[ident]["type"] == "llm_judge":
                        allowed |= judge_base
                        self.assertIn("model", keys, where)
                elif ident in builtin:
                    allowed = builtin[ident]
                else:
                    self.assertIn(ident, builtin_judges, where)
                    allowed = builtin_judges[ident] | judge_base
                    self.assertIn("model", keys, where)
                self.assertLessEqual(keys, allowed, where)


if __name__ == "__main__":
    unittest.main()
