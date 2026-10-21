# Nextgear

A simulated agent builds a request pipeline from ten gears, one proposal at a time. A local check accepts or rejects each gear. When the agent submits, a system check compares the assembly with a specification the agent was given: which gears are required, whether external calls need an outbound gateway, and a latency budget. The agent makes mistakes, withdraws rejected gears, rolls back and tries again. A one-layer GRU sees only the resulting stream of events and predicts what comes next.

The generator is fully specified, so the best possible score is known. An exact Bayes oracle averages over all 384 combinations of hidden requirements and agent traits. Under the generator's priors, its log loss is the lowest that any predictor seeing only the events can expect. Each model's score can therefore be read as a distance from that floor.

On 2,000 held-out sessions, the GRU closes **73% of the gap** between the best n-gram and the oracle. The largest gain is on system checks. Whether a submitted assembly passes depends on gears accepted many events earlier, which a six-event window cannot see. The GRU predicts 82.4% of those verdicts correctly, the n-gram 65.7% and the oracle 84.7%. The gain does not transfer to a requirement combination removed from training: there the retrained GRU **shows no advantage over the n-gram** and gets far fewer system verdicts right.

![A held-out session replayed event by event: the request path, forecasts made before each event, and the oracle's belief about the hidden specification.](assets/session.svg)

*A held-out test session, one frame per event. (a) The events so far. (b) The forecast for the next event, made before it happened: filled bars are the GRU, outlines the oracle. (c) The oracle's belief about the hidden specification after the event. This session was chosen rather than sampled. Among short test sessions with a rejected gear and a failed system check that end admissible, this is the one where the GRU forecast the failure most confidently.*

## Results

| Predictor | Log loss per event ↓ | Accuracy | System-check accuracy |
|---|---:|---:|---:|
| Best n-gram (6 events) | 0.7117 | 78.6% | 65.7% |
| Counts over engineered visible state | 0.6593 | 80.3% | 82.4% |
| GRU, seed 0 | **0.6196** | **81.1%** | 82.4% |
| Bayes oracle | 0.5850 | 82.3% | 84.7% |

The GRU's paired log-loss difference from the n-gram is −0.0921 nats per event, with a 95% session-bootstrap interval of [−0.0983, −0.0860]. Three training seeds give 0.6168–0.6199. The state-count model is told what the visible assembly is and matches the GRU on system checks. The GRU has to learn that assembly from raw events, and its overall difference from the state counts is still −0.0397 [−0.0440, −0.0355].

![Excess log loss over the Bayes reference in four test conditions.](results/figures/gap.svg)

*Excess log loss over the oracle. In (a)–(c) the oracle uses the priors that generated the test sessions. In (d) it keeps the base prior and is not told which requirement group was selected, so it is a common reference rather than the best achievable score.*

Three harder tests check what the headline number hides:

- **Repeated traces.** The simulator is small enough to repeat itself: 966 of the 2,000 test sessions match a training session event for event. On the other 1,034 the GRU's difference from the n-gram is −0.1165 [−0.1248, −0.1085]. This rules out recall of whole traces, not reuse of familiar prefixes.
- **Changed agent.** With a different requirement mix and a sloppier agent, and no retraining, the GRU's excess loss rises from 0.0346 to 0.0790. It still beats both count models.
- **Excluded combination.** Sessions needing the Chat Engine with both the Policy Manager and the License Resolver were removed from training and validation, and the models were refit. On 600 new sessions of that kind, the retrained GRU's difference from the n-gram is +0.0068 [−0.0092, +0.0233]. It predicts 34.8% of system verdicts correctly, against 59.4% for the n-gram and 70.9% for the GRU that saw such sessions. Whatever the GRU learns about system checks does not carry over to a combination it has not seen. This is one excluded group and one training seed.

**What if the agent had done something else?** At 4,320 decision points in 400 test sessions, every model was asked what the checks would say to each of the ten gears and to a submission. Local verdicts depend only on the visible assembly, and the GRU gets 99.87% of them right for gears the agent did not propose. Submissions are different. An agent that chooses to submit believes it is ready, and a model trained on logs learns to treat the choice as evidence. Forcing a submission removes that evidence. Forced submissions pass 9.3% of the time. The GRU predicts 13.1%, and the oracle predicts 12.7% when it reads the submission as an observation. When the oracle treats the forced submission as an intervention, it predicts 9.5%. Predicting the next logged event is not the same as predicting the consequence of an action.

[Full benchmark and intervals](results/REPORT.md) · [Machine-readable results](results/report.json) · [Constructor Fabric usage](FABRIC_USAGE.md)

## Run it

Use Python 3.12. From this directory, run `python -m venv .venv`, then activate with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux/macOS:

```sh
python -m pip install -e .
python -m nextgear demo
```

The demo uses the checked-in checkpoints, so nothing is trained. Missing datasets regenerate from fixed seeds in a few seconds. It prints each forecast before revealing the event. At one decision point it then compares the GRU's verdict for every gear, and its chance that a forced submission passes, with the checks.

```sh
python -m unittest discover -s tests -v
python -m nextgear --config configs/quick.toml --data-dir runs/quick/data --models-dir runs/quick/models --results-dir runs/quick/results all
```

The second command runs the whole pipeline at toy sizes; its numbers mean nothing. `python -m nextgear all` reproduces the recorded experiment. That run took **503 seconds** with 16 CPU threads on Windows 11, and runtime depends on hardware. `--threads 4` limits CPU use. Global options go before the command. `train`, `evaluate`, `demo --session 12` and `hero --out assets/session.svg` also run on their own. `all` overwrites datasets, checkpoints and results in the selected directories, so point it at `runs/` paths to keep the reference artifacts.

`requirements-lock.txt` records the Windows CPU environment. To reproduce that environment, install it before `pip install -e .`; other platforms can resolve dependencies from `pyproject.toml`. Floating-point results can vary across hardware and PyTorch versions. The settings stamp catches configuration mismatches; it is not a file-integrity manifest. After editing dataset contents by hand, retrain with `python -m nextgear train` before evaluating. After changing generator logic, delete `data/stamp.txt` so the splits regenerate, then retrain.

## How it works

Each session draws hidden requirements and agent traits. The requirements are one of three execution gears, four optional gears and a tight or loose latency budget. The agent is either careful or sloppy, and may or may not know that external calls need the outbound gateway. At each decision the agent intends the next gear its specification requires. A careful agent picks some other action 5% of the time; a sloppy one 25%. Local checks reject duplicates, gears out of pipeline order and execution gears placed before the Auth Resolver. System checks report the first failure among missing capability, unguarded external calls, unneeded gears and latency over budget. The agent rolls back, adds the gateway or enables a resolver cache in response, and gives up if the cache does not fix latency or after 40 proposals or 4 submissions. The [24 event descriptions](src/nextgear/events.py) are the prediction vocabulary, and the [state machine](assets/states.svg) shows every transition.

![Modules, information boundaries and evaluation flow.](assets/architecture.svg)

The predictors are a frequency model, interpolated n-grams with context chosen on validation data, counts over the visible state reconstructed from events, and the GRU. The GRU sees event IDs only, never requirements or session IDs, and the generator imports no predictor. The state-count model is domain-informed: it is told how to rebuild the assembly. The oracle knows the generator's equations and priors and reuses its transition function. It is exact within the simulator, but it is not independent evidence that the simulator is right.

A fixed window forgets accepted gears once later rejections and rollbacks push them out of view. One recurrent layer can carry that history without hand-built features, and it trains on a CPU. The n-grams test whether that memory helps, and the state counts test whether a model given the assembly does just as well. A transformer or graph model would add tuning before this simpler model is understood.

The public [Constructor Fabric gear documentation](https://github.com/constructorfabric/gears-rust/blob/60db50e2482d9eae1a78da6a4f6372579eb9d8e3/docs/GEARS.md) motivates the ordering, no-bypass and outbound-adapter rules. The probabilities, requirement distribution, error policy, latency values, budgets and cache effects are this project's assumptions. No production gear or internal Fabric system runs here; this is a controlled sequence-prediction experiment. Diagram sources are TikZ in `assets/*.tex`.

## How the evaluation works, and its limits

Splits use separate random streams and whole sessions. N-gram context and GRU early stopping use the validation split, and the model settings were also chosen on validation data during development. Probabilities are scored with log loss and Brier score as well as accuracy, and separately for decisions, local checks and system checks, so the many routine steps cannot hide failures on the uncertain ones. Model differences use a paired bootstrap over whole sessions (10,000 resamples), which keeps events from one session together and recomputes the event-weighted difference each time.

The intervals are conditional on the fitted models and on the simulator. They cover neither simulator misspecification nor every source of training variation. The analyses are exploratory, with no preregistration or multiple-comparison correction. Every model learns an authored simulator and may exploit its regularities. The novel-trace, changed-agent and excluded-combination tests probe this, and the excluded-combination result limits what can be claimed. The next steps would start with those failed system checks: vary the excluded combination and the training seed, sample boundary cases, and try a state-aware probabilistic model. After that, independent or real composition traces are the external test. A larger network is worth adding only if it improves on those tests.

## Repository

`src/nextgear/` holds the generator, the check rules, the count models, the GRU, the oracle, the evaluation and the CLI. `configs/` fixes the experiment, `models/` holds four small checkpoints, and `results/` holds the report and two figures. Generated datasets stay out of Git. Requirements, decisions and four feature specifications are in [architecture/](architecture/). The Constructor Studio SDLC kit and its license are vendored under `.cf-studio/`.

[FABRIC_USAGE.md](FABRIC_USAGE.md) covers how Constructor Studio was used, the pinned version, the validation command and what traceability does and does not show. GitHub Actions runs lint, tests, the small pipeline, Studio validation and packaging on Windows and Linux.
