# Nextgear

A small neural network watches a simulated agent assemble a software pipeline and predicts every next event. That includes whether the final checks will accept the assembly, which depends on requirements the network never sees. The simulator is fully specified, so an exact Bayes oracle can compute the best possible prediction for its sessions. The benchmark measures how close the network gets to that limit, and where it breaks.

![A held-out session replayed event by event: the request path, forecasts made before each event, and the oracle's belief about the hidden specification.](assets/session.svg)

*One held-out session, frame by frame. (a) The events so far. (b) The forecast of the next event, made before it happened: filled bars are the GRU, outlines the oracle. (c) The oracle's belief about the hidden specification. The session was chosen, not sampled. Among short test sessions that have a rejected gear and a failed system check and still end admissible, this is the one where the GRU forecast the failure most confidently.*

## What it shows

1. **It predicts verdicts that depend on information it never sees.** Whether a submitted assembly passes depends on the hidden specification and on gears accepted many events earlier. The GRU is trained on raw event IDs alone and gets 82.4% of these verdicts right. A six-event n-gram gets 65.7%; the exact oracle gets 84.7%.
2. **It gets most of the way to the best possible score.** Over 46,208 predicted events in 2,000 held-out sessions, it closes **73% of the log-loss gap** between the best n-gram and the oracle. It also beats a count model that is given the visible assembly directly.
3. **It does not transfer to a requirement combination it has never seen.** When one combination is removed from training, the retrained GRU **shows no advantage over the n-gram** on new sessions of that kind. It gets 34.8% of their system verdicts right, against 70.9% for the GRU that saw such sessions.
4. **It predicts logs, not consequences.** In the logs, an agent submits when it thinks the assembly is ready, so a model learns to read a submission as good news. If a submission is forced instead, it passes 9.3% of the time. The GRU predicts 13.1%. Even the exact oracle predicts 12.7% when it treats the submission as an observation. Treated as an intervention, the oracle predicts 9.5%.

Overall accuracy hides the last two findings. The benchmark is built to find them.

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
  9 SUBMIT_ASSEMBLY            ✗ ADD_OUTBOUND_API_GATEWAY   0.59     0.26    0.38    0.27
 10 EXTERNAL_CALL_VIOLATION    ✓ EXTERNAL_CALL_VIOLATION    0.79     0.79    0.62    0.70
 11 ADD_OUTBOUND_API_GATEWAY   ✓ ADD_OUTBOUND_API_GATEWAY   0.81     0.81    0.75    0.81
 12 STEP_ACCEPTED              ✓ STEP_ACCEPTED              1.00     1.00    1.00    1.00
 13 ADD_BILLING_LEDGER         ✗ SUBMIT_ASSEMBLY            0.83     0.01    0.02    0.02
 14 ORDER_VIOLATION            ✓ ORDER_VIOLATION            1.00     1.00    1.00    1.00
 15 STEP_REVERTED              (routine step)
 16 SUBMIT_ASSEMBLY            ✓ SUBMIT_ASSEMBLY            0.76     0.76    0.77    0.77
 17 ASSEMBLY_ADMISSIBLE        ✓ ASSEMBLY_ADMISSIBLE        0.90     0.90    0.64    0.97
```

At event 9 the agent submits a Serverless Runtime assembly without the outbound gateway its external calls need. The GRU gives the resulting failure 0.79, against 0.62 for the n-gram. Event 13 is one of the agent's random mistakes, and no model, the oracle included, saw it coming. The demo then picks a decision point and asks what the checks would have said to every gear the agent could have proposed instead.

## How it works

Each session draws hidden requirements and agent traits. The requirements are one of three execution gears, four optional gears and a tight or loose latency budget. The agent is either careful or sloppy, and may or may not know that external calls need the outbound gateway. At each decision the agent intends the next gear its specification requires. A careful agent picks some other action 5% of the time, and a sloppy one 25%. Local checks reject duplicates, gears out of pipeline order, and execution gears placed before the Auth Resolver. System checks report the first failure among missing capability, unguarded external calls, unneeded gears and latency over budget. In response the agent rolls back, adds the gateway or enables a resolver cache. It gives up if the cache does not fix latency, or after 40 proposals or 4 submissions. The [24 event descriptions](src/nextgear/events.py) are the prediction vocabulary, and the [state machine](assets/states.svg) shows every transition.

![Modules, information boundaries and evaluation flow.](assets/architecture.svg)

Four kinds of predictor are compared:

- a frequency model;
- interpolated n-grams, with the context length chosen on validation data;
- counts over the visible state reconstructed from events;
- the GRU.

The GRU sees event IDs only, never requirements or session IDs, and the generator imports no predictor. The state-count model is domain-informed: it is told how to rebuild the assembly. The oracle averages over all 384 combinations of hidden requirements and agent traits. It uses the generator's own equations and priors and reuses its transition function. That makes it exact within the simulator, but it is not independent evidence that the simulator is right.

A fixed window forgets accepted gears once later rejections and rollbacks push them out of view. One recurrent layer can carry that history without hand-built features, and it trains on a CPU. The n-grams test whether that memory helps. The state counts test whether a model given the assembly does just as well. A transformer or graph model would add tuning before this simpler model is understood.

The public [Constructor Fabric gear documentation](https://github.com/constructorfabric/gears-rust/blob/60db50e2482d9eae1a78da6a4f6372579eb9d8e3/docs/GEARS.md) motivates the ordering, no-bypass and outbound-adapter rules. The probabilities, requirement distribution, error policy, latency values, budgets and cache effects are this project's assumptions. No production gear or internal Fabric system runs here; this is a controlled sequence-prediction experiment. Diagram sources are TikZ in `assets/*.tex`.

## Results

| Predictor | Log loss per event ↓ | Accuracy | System-check accuracy |
|---|---:|---:|---:|
| Best n-gram (6 events) | 0.7117 | 78.6% | 65.7% |
| Counts over engineered visible state | 0.6593 | 80.3% | 82.4% |
| GRU, seed 0 | **0.6196** | **81.1%** | 82.4% |
| Bayes oracle | 0.5850 | 82.3% | 84.7% |

The GRU's paired log-loss difference from the n-gram is −0.0921 nats per event, with a 95% session-bootstrap interval of [−0.0983, −0.0860]. Three training seeds give 0.6168–0.6199. The state-count model matches the GRU on system checks because it is given the assembly. The GRU has to learn the assembly from raw events, and its overall difference from the state counts is still −0.0397 [−0.0440, −0.0355].

![Excess log loss over the Bayes reference in four test conditions.](results/figures/gap.svg)

*Excess log loss over the oracle. In (a) and (c) the oracle uses the priors that generated the sessions, so each bar is a distance from the best achievable score. Panels (b) and (d) use sessions selected after generation, as novel traces and as one requirement group. The oracle is not told about the selection, so in those panels it is a common reference rather than the optimum for the subset.*

- **Repeated traces.** The simulator is small enough to repeat itself: 966 of the 2,000 test sessions match a training session event for event. On the other 1,034, the GRU's difference from the n-gram is −0.1165 [−0.1248, −0.1085]. This rules out recall of whole traces, not reuse of familiar prefixes.
- **Changed agent.** With a different requirement mix and a sloppier agent, and no retraining, the GRU's excess loss rises from 0.0346 to 0.0790. It still beats both count models.
- **Excluded combination.** Sessions needing the Chat Engine with both the Policy Manager and the License Resolver were removed from training and validation, and the models were refit. That removed 688 training sessions. On 600 new sessions of that kind, the retrained GRU's difference from the n-gram is +0.0068 [−0.0092, +0.0233]. Its system-verdict accuracy is 34.8%, against 59.4% for the n-gram. This is one excluded group and one training seed.
- **Untaken actions.** At 4,320 decision points in 400 test sessions, every model was asked what the checks would say to each of the ten gears and to a submission. Local verdicts depend only on the visible assembly, and the GRU gets 99.87% of them right for gears the agent did not propose. The submission results are finding 4 above.

[Full benchmark and intervals](results/REPORT.md) · [Machine-readable results](results/report.json) · [Constructor Fabric usage](FABRIC_USAGE.md)

## How the evaluation works, and its limits

Splits use separate random streams and whole sessions. N-gram context and GRU early stopping use the validation split, and the model settings were also chosen on validation data during development. Probabilities are scored with log loss and Brier score as well as accuracy. Scores are also broken down into decisions, local checks and system checks, so the many routine steps cannot hide failures on the uncertain ones. Model differences use a paired bootstrap over whole sessions with 10,000 resamples. It keeps events from one session together and recomputes the event-weighted difference each time.

The intervals are conditional on the fitted models and on the simulator. They cover neither simulator misspecification nor every source of training variation. The analyses are exploratory, with no preregistration or multiple-comparison correction. Every model learns an authored simulator and may exploit its regularities. The novel-trace, changed-agent and excluded-combination tests probe this, and the excluded-combination result limits what can be claimed.

The next steps would start with the failed system checks:

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

The second command runs the whole pipeline at toy sizes, so its numbers mean nothing. `python -m nextgear all` reproduces the recorded experiment. That run took **503 seconds** with 16 CPU threads on Windows 11; runtime depends on hardware.

- `--threads 4` limits CPU use. Global options go before the command.
- `train`, `evaluate`, `demo --session 12` and `hero --out assets/session.svg` also run on their own.
- `all` overwrites datasets, checkpoints and results in the selected directories, so point it at `runs/` paths to keep the reference artifacts.

`requirements-lock.txt` records the Windows CPU environment. To reproduce that environment, install it before `pip install -e .`; other platforms can resolve dependencies from `pyproject.toml`. Floating-point results can vary across hardware and PyTorch versions. The settings stamp catches configuration mismatches; it is not a file-integrity manifest. After editing dataset contents by hand, retrain with `python -m nextgear train` before evaluating. After changing generator logic, delete `data/stamp.txt` so the splits regenerate, then retrain.

## Repository

| Path | Contents |
|---|---|
| `src/nextgear/` | Generator, check rules, count models, GRU, oracle, evaluation, CLI |
| `configs/` | Experiment settings |
| `models/` | Four small checkpoints |
| `results/` | The report and two figures |
| `architecture/` | [Requirements, decisions and four feature specifications](architecture/) |
| `.cf-studio/` | Vendored Constructor Studio SDLC kit and its license |

Generated datasets stay out of Git. [FABRIC_USAGE.md](FABRIC_USAGE.md) covers how Constructor Studio was used, the pinned version, the validation command, and what traceability does and does not show. GitHub Actions runs lint, tests, the small pipeline, Studio validation and packaging on Windows and Linux.
