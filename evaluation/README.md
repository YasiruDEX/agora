# Agora evaluation layer

Everything needed to test and demo Agent Manager's evaluation features on the Agora agents:
custom evaluators, monitors, score thresholds, alerts, and traffic that makes the scores move.

The presenter's script is [`docs/evaluation-demo-guide.md`](../docs/evaluation-demo-guide.md).
This file is for whoever sets the environment up.

```
evaluation/
├── evaluators/
│   ├── evaluators.yaml        # 9 custom evaluators: identifier, level, config params
│   ├── code/                  # 6 rule-based evaluators (Python, no LLM cost)
│   └── judge/                 # 3 LLM-judge prompt templates
├── monitors/                  # monitors + alert thresholds, one file per agent kind
├── setup/
│   ├── targets.yaml           # org, project, environment, agents, judge model
│   └── apply.py               # plan | apply | status | backfill | teardown
├── traffic/
│   ├── scenarios/             # 40 resident questions, tagged by category
│   └── run.py                 # sends them to the agents
└── tests/                     # local checks for evaluator logic and config wiring
```

## What gets created

| Agent kind | Every trace (rule-based, 5 min) | Sampled (LLM judge, 15 min) |
|---|---|---|
| Citizen Inquiry | KB Grounding Discipline\*, Source Citation\*, PII Leak Check\*, Content Safety, Step Success Rate, Latency Performance, Length Compliance | Policy Faithfulness\*, Department Scope Handling\*, Plain-Language Service\*, Groundedness, Helpfulness, Tone (30%) |
| Permit & Licensing | Verify Before Prefill\*, Fee Estimate Disclaimer\*, PII Leak Check\*, Step Success Rate, Iteration Efficiency, Token Efficiency, Latency Performance | Instruction Following, Policy Faithfulness\*, Completeness, Plain-Language Service\* (30%) |
| Case Management | Tool Scope Adherence\*, PII Leak Check\*, Step Success Rate, Latency Performance | Groundedness, Completeness, Safety (50%) |

\* custom evaluator from this folder. The rest are Agent Manager built-ins with tuned config.

Each monitor carries 2 to 5 score thresholds (see `monitors/*.yaml`). With the default
`targets.yaml` that is 9 custom evaluators, 8 monitors and 8 alert configurations across 4
agent instances.

## Set up

1. Edit `setup/targets.yaml`: organization, project, environment, the agents' names as they
   appear in Agent Manager, the LLM provider handle for judges, and each agent's invoke URL.
2. Export credentials:

   ```bash
   export AMP_API_URL="https://<agent-manager-host>/api/v1"
   export AMP_TOKEN="<bearer token>"   # or AMP_TOKEN_URL + AMP_CLIENT_ID + AMP_CLIENT_SECRET
   export AMP_ALERT_WEBHOOK_URL="https://<where alerts should go>"   # optional
   ```

   The identity needs `amp:evaluator:create/read/update`, `amp:monitor:create/read/update`
   and, to create the alert destination, the events-manage permission.
3. Review, then apply:

   ```bash
   python evaluation/setup/apply.py plan
   ```

   ```bash
   python evaluation/setup/apply.py apply
   ```

   `apply` is safe to re-run. It updates evaluators and monitors in place.
4. Send traffic and read the scores back:

   ```bash
   python evaluation/traffic/run.py --rounds 2
   ```

   ```bash
   python evaluation/setup/apply.py status --hours 1
   ```

Other commands: `backfill --hours 6` creates one-off historical monitors over past traces
(for a before/after comparison), `teardown` deletes the monitors and custom evaluators.

## Things worth knowing before you tune

- **Thresholds act on the mean of one monitor run.** Operator is `below` or `above`, value
  is 0 to 1, at most 20 per monitor. Agent Manager notifies when a threshold is first
  crossed and again when the score recovers, not on every run.
- **`below 1.0` means zero tolerance.** One failing trace in a run pulls the mean under 1.
  Used for PII Leak Check and Verify Before Prefill.
- **Skipped traces are left out of the mean.** An evaluator that skips when it has nothing
  to check stays meaningful, but one that skips the failure case hides it. Built-in
  Groundedness skips answers that used no tool, so an agent answering from memory does not
  lower it. KB Grounding Discipline and Policy Faithfulness score exactly those traces.
- **A threshold names an evaluator by its display name in that monitor.** Rename one and the
  threshold must change with it; `apply.py` checks this before sending anything.
- **LLM judges need a provider.** Any monitor with a judge must reference an org-level LLM
  provider (`llmProvider` in `targets.yaml`) and each judge gets `model` in its config.
- **Custom code evaluators must define exactly one top-level function.** The evaluation job
  takes the last plain callable in the file, so a helper function or an imported function
  would be picked up instead. Keep helpers inside the function body.
- **Monitor limits.** Interval at least 5 minutes; sampling rate above 0 and at most 1;
  historical monitors reach back at most 30 days.

## Tests

```bash
python -m unittest discover -s evaluation/tests -v
```

The tests load each evaluator the way the evaluation job does and render each judge prompt,
using a small stand-in for the amp-evaluation SDK. They cover the scoring logic and the
config wiring. They do not cover how traces from a deployed agent map onto the SDK's trace
model, so check the first real monitor run: every evaluator should show scores, not only
skips.

## Not covered: human evaluation

Agent Manager has no human review or annotation feature today, so this setup has none.
Scores come from rule-based evaluators and LLM judges only.
