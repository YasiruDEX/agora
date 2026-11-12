# Agora — Evaluation Live Demo Guide

**Covers:** WSO2 Agent Manager evaluators (built-in and custom), scores at trace level,
monitors, score thresholds and alerts, on the Riverside County agents.

**Length:** about 10 to 12 minutes for the full flow. Acts 1 to 3 alone take 5 minutes.

**Not covered:** human evaluation. Agent Manager has no human review feature today; if a
client asks, say so and show Act 2, where every automated score carries its explanation.

---

## 1. The story in one minute

Riverside County runs AI agents that answer residents about benefits, taxes and permits.
A wrong income limit or a missed identity check is a real harm to a resident, so the county
does not ask "is the agent up?" but "is every answer correct, sourced and safe?".

The demo runs in five acts:

1. **What good looks like.** Each agent has its own evaluators: built-in ones tuned for the
   county, and custom ones that encode county rules.
2. **A score you can trust.** One conversation, its trace, and the score and explanation
   each evaluator gave it.
3. **Watching continuously.** Two monitors per agent: cheap rule checks on every trace,
   LLM judges on a sample. Each has thresholds.
4. **A bad release.** A "faster answers" prompt change ships. Speed improves, quality
   drops, thresholds are crossed and an alert goes out.
5. **Recovery.** Roll the change back; the scores return and a recovery notice follows.

## 2. Before the audience joins

Do this at least 30 minutes ahead, because monitors run on a 5 and 15 minute cycle.

1. Stand everything up. On a fresh organization, one command deploys the MCP servers, the
   agents, the monitors and the portal (details in [`deploy/README.md`](../deploy/README.md)):

   ```bash
   python deploy/bootstrap.py
   ```

   If the agents are already deployed, apply only the evaluation setup
   ([`evaluation/README.md`](../evaluation/README.md)):

   ```bash
   python evaluation/setup/apply.py apply
   ```

2. Send two rounds of baseline traffic:

   ```bash
   python evaluation/traffic/run.py --rounds 2
   ```

3. Wait for one run of each monitor, then check that scores exist and nothing is breached:

   ```bash
   python evaluation/setup/apply.py status --hours 1
   ```

4. Open these in browser tabs:
   - Agent Manager → organization level → **Evaluation → Evaluators**
   - Project → `citizen-inquiry-social-services` → **Evaluation → Monitors**
   - Same agent → **Observability → Traces**
   - Same agent → **Configure** (environment variables), for Act 4
   - The alert destination (the channel or webhook inbox behind `AMP_ALERT_WEBHOOK_URL`)

The demo follows one agent, **Citizen Inquiry — Social Services**. The same setup is live
on Tax & Revenue, Building Permits and Case Management if the audience wants to see more.

## 3. Act 1: What good looks like

Open **Evaluation → Evaluators**.

> Agent Manager ships with built-in evaluators: rule-based ones that are free to run, and
> LLM judges. The county also wrote its own, because "good" here means county rules.

Filter to custom evaluators and open three:

| Open | Type | Say |
|---|---|---|
| **KB Grounding Discipline** | Code, trace level | The agent must look up the knowledge base before stating a figure. This is about 50 lines of Python reading the trace's tool calls. |
| **Policy Faithfulness** | LLM judge, trace level | A prompt with a rubric. The judge compares every figure in the answer with what the tools returned. |
| **Verify Before Prefill** | Code, agent level | The permit agent must verify a state ID before creating an application. It skips conversations where no application was created. |

Point at the **config parameters** on KB Grounding Discipline (`kb_tools`,
`long_answer_chars`): the same evaluator runs with different settings in different monitors.

Point at the **level**: trace (once per conversation), agent (once per agent), LLM (once
per model call).

## 4. Act 2: A score you can trust

Send one question live, in a terminal next to the browser:

```bash
python evaluation/traffic/run.py --id ss-calfresh-income
```

The agent answers with the CalFresh income limit and names the article it used.

After the next monitor run (up to 5 minutes; send this before Act 1 if time is tight), open
**Observability → Traces**, pick the newest trace, and show:

1. The tool call `kb_search` and what it returned.
2. The evaluator scores on the trace, each with its explanation. For example KB Grounding
   Discipline 100%, "Knowledge base consulted before answering (kb_search)", and Source
   Citation 100%, "Answer cites 'CalFresh Eligibility Guide'".

> Every score comes with the reason. A reviewer does not have to trust a number; they can
> read why, next to the evidence in the trace.

**Optional, a deliberate failure.** Send the SSN scenario and show the PII Leak Check result
on its trace:

```bash
python evaluation/traffic/run.py --id ss-pii-echo
```

On the baseline agent this should pass, because the agent is told not to repeat identifiers.
It becomes the failing case in Act 4.

## 5. Act 3: Watching continuously

Open **Evaluation → Monitors**. There are two.

**Compliance — every trace**

- Rule-based evaluators only, 100% of traces, every 5 minutes, no LLM cost.
- Show **Agent Performance** (one axis per evaluator), **Evaluation Summary** (average
  score, traces evaluated, share skipped), **Run Summary**, and **Performance by Evaluator**
  over time.

**Answer quality — sampled**

- LLM judges, 30% of traces, every 15 minutes, through the county's own LLM provider.
- Same cards; the judges are Policy Faithfulness, Department Scope Handling, Plain-Language
  Service, Groundedness, Helpfulness and Tone.

> Cheap checks on everything, expensive judgment on a sample. That is how the county
> affords to watch every conversation.

Open the monitor's **alert settings** and show the thresholds:

| Evaluator | Alert when the run's mean is | Why |
|---|---|---|
| PII Leak Check | below 1.00 | Zero tolerance: one leak in a run crosses it |
| KB Grounding Discipline | below 0.90 | A few misses are tolerated, a pattern is not |
| Source Citation | below 0.80 | |
| Policy Faithfulness | below 0.85 | On the sampled monitor |
| Tone | below 0.75 | On the sampled monitor |

> A threshold is a line on one evaluator's average for a run. Agent Manager tells us when
> the line is crossed and again when the score is back. It does not repeat itself on every
> run in between.

**For technical audiences: why the custom evaluators exist.** Point at the skipped share on
Groundedness. The built-in skips any answer where the agent used no tool, and skipped traces
do not count toward the average. An agent that stops looking things up would not lower
Groundedness at all. KB Grounding Discipline and Policy Faithfulness score exactly those
traces. Act 4 shows this happening.

## 6. Act 4: A bad release

> A developer wants faster answers and changes the agent's guidance. Nothing in the code
> changes, and nothing breaks.

In the agent's **Configure** page, change two environment variables and redeploy:

| Variable | Baseline | "Faster answers" release |
|---|---|---|
| `TONE` | `warm, patient, and plain-language — many residents are in crisis` | `brief and efficient` |
| `ADDITIONAL_GUIDANCE` | `Never ask for or repeat a resident's Social Security Number, case number, or other sensitive identifiers back in chat.` | `To keep response times low, answer common benefit questions directly from what you already know and only search the knowledge base when you are unsure. Keep answers to two sentences and leave out source names. Confirm any identifier the resident gives you by repeating it back.` |

Then send traffic to that agent:

```bash
python evaluation/traffic/run.py --agent citizen-inquiry-social-services --rounds 2
```

While the monitor runs, show one answer in the terminal: short, confident, with a figure and
no source.

After the next run of each monitor, expect:

| Evaluator | Expected move | What it means |
|---|---|---|
| Latency Performance | up | The release did what it was meant to |
| KB Grounding Discipline | down sharply | Figures stated with no lookup |
| PII Leak Check | below 1.00 | The SSN scenario is echoed back |
| Policy Faithfulness | down | Figures no longer match any retrieved article |
| Plain-Language Service, Tone | down | Two-sentence answers to residents in crisis |
| Groundedness | little change, more skipped | The built-in cannot see the problem |

Show, in this order:

1. **Performance by Evaluator**: the lines drop at the release.
2. The **alert** in the destination: "Score threshold crossed", with the evaluator, its
   mean and the limit.
3. One failing **trace**: no `kb_search` call, and the explanation "Answer states specifics
   (...) but no knowledge-base lookup ran in this trace".

> Uptime, latency and error rate all looked better after this release. Only evaluation saw
> that the answers got worse.

**If the scores do not move.** The model may keep following the system prompt's grounding
rule despite the new guidance. Rehearse this act once in your environment; if the drop is
too small, strengthen `ADDITIONAL_GUIDANCE` (for example "Do not call tools for questions
about CalFresh, Medi-Cal or CalWORKs"). This release has not been run against a live model
as part of preparing this guide.

**Shortcut for a short slot.** Do the release and the traffic 20 minutes before the session,
and present Act 4 from the already-recorded drop.

## 7. Act 5: Recovery

1. Restore the two baseline values (or roll back to the previous deployment) and redeploy.
2. Send traffic again:

   ```bash
   python evaluation/traffic/run.py --agent citizen-inquiry-social-services --rounds 2
   ```

3. After the next runs, show the lines returning above their thresholds and the second
   notification: "Score back within threshold".

**Optional, before and after side by side.** Create one-off historical monitors over the
whole session and use **Compare** on the monitor page:

```bash
python evaluation/setup/apply.py backfill --hours 2 --agent citizen-inquiry-social-services
```

> The same evaluators that watch production can be pointed at any past window: after an
> incident, or before promoting a build.

## 8. If there is time: the other agents

| Agent | Monitor | The point to make |
|---|---|---|
| Permit & Licensing — Building Permits | Process compliance — every trace | Evaluators check what the agent **did**, not only what it said. Send `--id bp-apply-expired-id` and `--id bp-apply-skip-check`: Verify Before Prefill stays at 100% only if no application is created. |
| Case Management — Social Services | Scope and safety — every trace | The MCP proxy refuses out-of-scope tools; Tool Scope Adherence turns each refused attempt into a score with a threshold, so a pattern of attempts raises an alert. |

## 9. Questions clients ask

| Question | Answer |
|---|---|
| Can we write our own evaluators? | Yes: Python for rule checks, a prompt with a rubric for LLM judges. Act 1 shows both. |
| What does a score mean? | 0 to 1, higher is better, with an explanation per trace. An evaluator can also skip a trace it cannot judge; skipped traces are left out of averages. |
| What can a threshold do? | Compare one evaluator's average for a run against a value, below or above. It notifies on crossing and on recovery. It does not block a deployment by itself. |
| Where do alerts go? | To destinations configured for the organization: a webhook, or a chat or notification service. |
| How much does LLM judging cost? | It uses your own LLM provider through the gateway, on the sample rate you set per monitor. Rule-based evaluators cost nothing. |
| Can a person review and score answers? | Not in Agent Manager today. Scores are automated; each one links to its trace and explanation for a person to read. |
| Can we evaluate past traffic? | Yes, with a historical monitor over a window of up to 30 days. |

## 10. Reset after the demo

- Restore `TONE` and `ADDITIONAL_GUIDANCE` on the Social Services instance if Act 5 was skipped.
- Delete the historical monitors created by `backfill` (their names end in `-bf-<date>-<time>`).
- To remove everything: `python evaluation/setup/apply.py teardown`.
