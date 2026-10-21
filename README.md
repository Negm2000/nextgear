# Nextgear

A small neural network watches a simulated agent assemble an application from Constructor Fabric's gears and predicts every next event. That includes whether the final checks will accept the assembly, which depends on requirements the network never sees. Which gear depends on which is not invented. It comes from the `deps` each gear declares in Fabric's gears-rust repository, and the toolkit's own registry agrees with the simulator on all 24,910 assemblies tested. The simulator is fully specified, so an exact Bayes oracle can compute the best possible prediction for its sessions. The benchmark measures how close the network gets to that limit, and where it breaks.

![A held-out session replayed event by event: the request path, the platform gears, forecasts made before each event, and the oracle's belief about the hidden specification.](assets/session.svg)

*One held-out session, frame by frame. A sloppy agent builds a Billing Ledger application and submits it without three platform gears. The dependency check rejects it, the agent adds the Types Registry, the Account Manager and the Resource Group, and the assembly passes. Gears-rust's `bss-ledger` needs the first two directly and the third through `account-management`. (a) The events so far. (b) The forecast of the next event, made before it happened: filled bars are the GRU, outlines the oracle. (c) The oracle's belief about the hidden specification. The session was chosen, not sampled. Among test sessions of at most 32 events that have a rejected gear and a failed dependency check and still end admissible, this is the one where the GRU forecast its system-check failures most confidently.*

## What it shows

1. **It predicts verdicts that depend on information it never sees.** Whether a submitted assembly passes depends on the hidden specification and on whether every declared dependency is present. The GRU is trained on raw event IDs alone and gets 89.4% of these verdicts right. A six-event n-gram gets 66.1%, a count model given the reconstructed assembly 82.4%, and the exact oracle 91.5%.
2. **It gets most of the way to the best possible score.** Over 87,696 predicted events in 2,000 held-out sessions, it closes **86% of the log-loss gap** between the best n-gram and the oracle. The other two training seeds close 82% and 83%.
3. **In one test, it transfers to a requirement combination it has never seen.** When the Chat Engine with both the Policy Manager and the License Resolver is removed from training, the retrained GRU still beats the n-gram on new sessions of that kind. It gets 76.3% of their system verdicts right, against 58.5% for the n-gram and 82.0% for the GRU that saw such sessions. This is one excluded group and one seed, and the same test failed in an earlier version of the simulator (see the limits below).
4. **It degrades when the agent changes.** With a sloppier agent and a different requirement mix, and no retraining, its excess loss over the oracle triples, from 0.035 to 0.105 nats per event. It stays far ahead of both count models.

## Try it

With Python 3.12, from a fresh virtual environment (setup below):

```sh
python -m pip install -e .
python -m nextgear demo
```

The demo uses the checked-in models, so nothing is trained. It replays a test session and prints each forecast before revealing the event. An excerpt:

```text
    what happened              GRU top guess, before it happened   P(what happened):
                                                                      GRU  n-gram  oracle
 22 SUBMIT_ASSEMBLY            ✓ SUBMIT_ASSEMBLY            0.81     0.81    0.03    0.77
 23 EXTERNAL_CALL_VIOLATION    ✓ EXTERNAL_CALL_VIOLATION    0.99     0.99    0.37    0.92
 24 ADD_API_GATEWAY            ✗ ADD_OUTBOUND_API_GATEWAY   0.82     0.01    0.01    0.01
 25 ORDER_VIOLATION            ✓ ORDER_VIOLATION            1.00     1.00    1.00    1.00
 26 STEP_REVERTED              (routine step)
 27 ADD_OUTBOUND_API_GATEWAY   ✓ ADD_OUTBOUND_API_GATEWAY   0.92     0.92    0.96    0.76
 28 STEP_ACCEPTED              ✓ STEP_ACCEPTED              1.00     1.00    1.00    1.00
 29 ADD_CREDENTIALS_STORE      ✓ ADD_CREDENTIALS_STORE      0.81     0.81    0.61    0.76
 30 STEP_ACCEPTED              ✓ STEP_ACCEPTED              1.00     1.00    0.96    1.00
 31 SUBMIT_ASSEMBLY            ✓ SUBMIT_ASSEMBLY            0.77     0.77    0.71    0.76
 32 ASSEMBLY_ADMISSIBLE        ✓ ASSEMBLY_ADMISSIBLE        0.97     0.97    0.45    0.96
```

- **Event 22.** The GRU expects the agent to submit; the n-gram cannot see that the assembly is complete and gives 0.03.
- **Event 23.** The agent's Serverless Runtime makes external calls without the outbound gateway, and the GRU gives the resulting failure 0.99.
- **Event 24.** One of the agent's random mistakes; no model, the oracle included, saw it coming.
- **Event 29.** Once the outbound gateway is accepted, the GRU expects the Credentials Store, which `oagw` declares as a dependency in gears-rust.

The demo then picks a decision point and asks what the checks would have said to every gear the agent could have proposed instead.

## How it works

Each session draws hidden requirements and agent traits:

- **Requirements:** one of three execution gears, any of three optional gears (Policy Manager, License Resolver, Usage Collector), and a tight or loose latency budget.
- **Agent traits:** careful or sloppy, and whether it knows two things about the platform: that external calls need the outbound gateway, and which platform gears the others depend on.

At each decision the agent intends the next gear it needs: request-path gears in the documented order, then the outbound gateway, then any missing dependencies. A careful agent picks some other action 5% of the time; a sloppy one 25%.

- **Local checks** reject duplicates, gears out of request order, and execution gears placed before the Auth Resolver.
- **System checks** report the first failure among:
  1. a missing request-path gear;
  2. a missing declared dependency;
  3. unguarded external calls;
  4. unneeded gears;
  5. latency over budget.
- **In response** the agent rolls back, adds what was missing, or enables a resolver cache. It gives up if the cache does not fix latency, or after 60 proposals or 5 submissions.

The [31 event descriptions](src/nextgear/events.py) are the prediction vocabulary, and the [state machine](assets/states.svg) shows every transition.

![Modules, information boundaries and evaluation flow.](assets/architecture.svg)

**Where the rules come from.** The rules come from Constructor Fabric wherever it has them:

- **From Fabric:** the request order, the no-bypass rule and adapters for external calls come from [gears-rust's `docs/GEARS.md`](https://github.com/constructorfabric/gears-rust/blob/fc765feb8e328ae31c44bfb3a0c981b42e32a105/docs/GEARS.md). The sixteen gears and every dependency between them come from the gears' own declarations at the same commit, extracted by [`tools/extract_gears.py`](tools/extract_gears.py). A Rust harness asks the real registry about each assembly and confirms the dependency rule ([details](FABRIC_USAGE.md)).
- **This project's assumptions:** the agent's probabilities, the requirement frequencies, the check order, latency values, budgets and cache effects.

No production gear runs here; this is a controlled sequence-prediction experiment. Diagram sources are TikZ in `assets/*.tex`.

**The predictors.**

- a frequency model;
- interpolated n-grams, with the context length chosen on validation data;
- counts over the visible state reconstructed from events;
- the GRU.

The GRU sees event IDs only, never requirements or session IDs, and the generator imports no predictor. The state-count model is domain-informed: it is told how to rebuild the assembly. With sixteen gears that state space is large, so its counts are sparse. The oracle averages over all 384 combinations of hidden requirements and agent traits. It uses the generator's own equations and priors and reuses its transition function. That makes it exact within the simulator, but it is not independent evidence that the simulator is right.

A fixed window forgets accepted gears once later rejections and rollbacks push them out of view. One recurrent layer can carry that history without hand-built features, and it trains on a CPU. The n-grams test whether that memory helps; the state counts test whether a model given the assembly does just as well. A transformer or graph model would add tuning before this simpler model is understood.

## Results

| Predictor | Log loss per event ↓ | Accuracy | System-check accuracy |
|---|---:|---:|---:|
| Best n-gram (6 events) | 0.7988 | 79.2% | 66.1% |
| Counts over engineered visible state | 0.7350 | 81.4% | 82.4% |
| GRU, seed 0 | **0.5786** | **86.0%** | **89.4%** |
| Bayes oracle | 0.5434 | 86.9% | 91.5% |

The GRU's paired log-loss difference from the n-gram is −0.2202 nats per event, with a 95% session-bootstrap interval of [−0.2273, −0.2128]. Its difference from the state counts is −0.1565 [−0.1634, −0.1490]. Three training seeds give 0.5786–0.5884; seed 0 is the first configured seed, not the best one chosen afterwards.

![Excess log loss over the Bayes reference in four test conditions.](results/figures/gap.svg)

*Excess log loss over the oracle. In (a) and (c) the oracle uses the priors that generated the sessions, so each bar is a distance from the best achievable score. Panels (b) and (d) use sessions selected after generation, as novel traces and as one requirement group. The oracle is not told about the selection, so in those panels it is a common reference rather than the optimum for the subset.*

- **Repeated traces.** The simulator still repeats itself: 628 of the 2,000 test sessions match a training session event for event. On the other 1,372, the GRU's difference from the n-gram is −0.2476 [−0.2555, −0.2398]. This rules out recall of whole traces, not reuse of familiar prefixes.
- **Changed agent.** The GRU's difference from the n-gram is −0.4207 [−0.4310, −0.4105], and from the state counts −0.3028 [−0.3106, −0.2951].
- **Excluded combination.** Removing the group took 688 sessions out of training. On 600 new sessions of that kind, the retrained GRU's difference from the n-gram is −0.2283 [−0.2413, −0.2152]. Its difference from the GRU that saw such sessions is +0.0653 [+0.0620, +0.0687].
- **Untaken actions.** At 7,990 decision points in 400 test sessions, every model was asked what the checks would say to each of the sixteen gears and to a submission. Local verdicts depend only on the visible assembly, and the GRU gets 99.76% of them right for gears the agent did not propose.
- **Forced submissions.** These pass 4.7% of the time, and the GRU predicts 4.8% on average. A submission the agent chose to make is evidence that it thought the assembly was ready, and a forced one is not. Here that evidence shows mainly in the log loss. The oracle scores 0.1174 when it treats forced submissions as observations and 0.0885 when it treats them as interventions; the GRU, trained on logs, scores 0.1776. Predicting the next logged event is not the same as predicting the consequence of an action.

[Full benchmark and intervals](results/REPORT.md) · [Machine-readable results](results/report.json) · [Constructor Fabric usage](FABRIC_USAGE.md)

## How the evaluation works, and its limits

Splits use separate random streams and whole sessions. N-gram context and GRU early stopping use the validation split. The GRU's settings were chosen on validation data for the first version of the simulator and were not re-tuned after its rules changed. Probabilities are scored with log loss and Brier score as well as accuracy. Scores are also broken down into decisions, local checks and system checks, so the many routine steps cannot hide failures on the uncertain ones. Model differences use a paired bootstrap over whole sessions with 10,000 resamples. It keeps events from one session together and recomputes the event-weighted difference each time.

The intervals are conditional on the fitted models and on the simulator. They cover neither simulator misspecification nor every source of training variation. The analyses are exploratory, with no preregistration or multiple-comparison correction. Every model learns a simulator whose dependencies are Fabric's but whose agent and probabilities are authored, and it may exploit their regularities.

The excluded-combination result needs particular care. In the first version of this simulator, whose composition rules were hand-written, the same test failed. There the retrained GRU's difference from the n-gram was +0.0068 [−0.0092, +0.0233], and it got 34.8% of system verdicts right. The rules were replaced with the gears-rust dependencies, and committed, before the run reported here. A plausible reading is that the real dependency graph gives combinations more shared structure to learn from, but one group and one seed cannot establish that.

The next steps would be:

1. Vary the excluded combination and the training seed.
2. Sample boundary cases.
3. Try a state-aware probabilistic model.
4. Test on independent or real composition traces.

A larger network is worth adding only if it improves on those tests.

## Reproduce

To set up the environment, run `python -m venv .venv` in this directory. Then activate it with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux/macOS, and install as above. Missing datasets regenerate from fixed seeds in a few seconds.

```sh
python -m unittest discover -s tests -v
python -m nextgear --config configs/quick.toml --data-dir runs/quick/data --models-dir runs/quick/models --results-dir runs/quick/results all
```

The second command runs the whole pipeline at toy sizes, so its numbers mean nothing. `python -m nextgear all` reproduces the recorded experiment. That run took **1,422 seconds** with 4 CPU threads on Linux (Python 3.12.3, PyTorch 2.14.1); runtime depends on hardware.

- `--threads 4` limits CPU use. Global options go before the command.
- `train`, `evaluate`, `demo --session 12` and `hero --out assets/session.svg` also run on their own.
- `all` overwrites datasets, checkpoints and results in the selected directories, so point it at `runs/` paths to keep the reference artifacts.

`requirements-lock.txt` pins the library versions of the recorded run. To reproduce that environment, install it before `pip install -e .`; otherwise dependencies resolve from `pyproject.toml`. Floating-point results can vary across hardware and PyTorch versions. The settings stamp catches configuration mismatches; it is not a file-integrity manifest. After editing dataset contents by hand, retrain with `python -m nextgear train` before evaluating. After changing generator logic, delete `data/stamp.txt` so the splits regenerate, then retrain.

## Repository

| Path | Contents |
|---|---|
| `src/nextgear/` | Generator, check rules, the extracted gear dependencies, count models, GRU, oracle, evaluation, CLI |
| `tools/` | Dependency extraction from gears-rust and the Rust cross-check against its registry |
| `configs/` | Experiment settings |
| `models/` | Four small checkpoints |
| `results/` | The report and two figures |
| `architecture/` | [Requirements, decisions and four feature specifications](architecture/) |
| `.cf-studio/` | Vendored Constructor Studio SDLC kit and its license |

Generated datasets stay out of Git. [FABRIC_USAGE.md](FABRIC_USAGE.md) covers how Gears and Studio were used, the pinned versions, the validation commands, and what traceability does and does not show. GitHub Actions runs lint, tests, the small pipeline, Studio validation and packaging on Windows and Linux, and reruns the registry cross-check on Linux.
