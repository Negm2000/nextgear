---
version: 2.0
description: Proper scores by step type, a paired session bootstrap, what-if verdicts, and three generalization tests.
---

# Feature: Evaluation

<!-- toc -->

- [1. Feature Context](#1-feature-context)
  - [1.1 Overview](#11-overview)
  - [1.2 Purpose](#12-purpose)
  - [1.3 Actors](#13-actors)
  - [1.4 References](#14-references)
- [2. Actor Flows (CDSL)](#2-actor-flows-cdsl)
  - [Used by the pipeline](#used-by-the-pipeline)
- [3. Processes / Business Logic (CDSL)](#3-processes--business-logic-cdsl)
  - [Score every forecast](#score-every-forecast)
  - [Paired session bootstrap](#paired-session-bootstrap)
  - [What-if verdicts](#what-if-verdicts)
  - [Unseen traces](#unseen-traces)
  - [Shifted agent](#shifted-agent)
  - [Unseen requirement combination](#unseen-requirement-combination)
- [4. States (CDSL)](#4-states-cdsl)
  - [No lifecycle states](#no-lifecycle-states)
- [5. Definitions of Done](#5-definitions-of-done)
  - [Benchmark report](#benchmark-report)
- [6. Acceptance Criteria](#6-acceptance-criteria)

<!-- /toc -->

Proper scores by step type, a paired session bootstrap, what-if verdicts, and three generalization tests.

- [x] `p1` - **ID**: `cpt-nextgear-featstatus-evaluation`
## 1. Feature Context

- [x] `p1` - `cpt-nextgear-feature-evaluation`

### 1.1 Overview

Every predictor forecasts every event of 2,000 held-out sessions. Forecasts are scored with log loss and accuracy, overall and per step type, and every difference between two models gets a 95% interval from resampling whole sessions. Three harder tests follow: test sessions whose exact trace never appears in training, sessions from a changed agent, and a combination of requirements removed from training. A what-if test asks each model about actions the agent did not take.

### 1.2 Purpose

Show that the GRU predicts something, how far it is from the Bayesian reference under declared priors, and where it stops working.

**Requirements**: `cpt-nextgear-fr-benchmark`, `cpt-nextgear-fr-statistics`, `cpt-nextgear-fr-unseen-traces`, `cpt-nextgear-fr-what-if`, `cpt-nextgear-fr-shift`, `cpt-nextgear-fr-unseen-combination`, `cpt-nextgear-nfr-runtime`

**Principles**: `cpt-nextgear-principle-absolute-reference`, `cpt-nextgear-principle-events-only`

### 1.3 Actors

| Actor | Role in Feature |
|-------|-----------------|
| `cpt-nextgear-actor-reviewer` | Reads the report and figures |
| `cpt-nextgear-actor-checker` | Supplies the true verdict for every what-if query |

### 1.4 References

- **PRD**: [PRD.md](../PRD.md)
- **Design**: [DESIGN.md](../DESIGN.md)
- **Dependencies**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`

## 2. Actor Flows (CDSL)

### Used by the pipeline

This feature has no user-facing flow; it runs inside `cpt-nextgear-flow-pipeline-reproduce`.

## 3. Processes / Business Logic (CDSL)

### Score every forecast

- [x] `p1` - **ID**: `cpt-nextgear-algo-evaluation-score`

**Input**: Held-out sessions and one predictor's probability matrices

**Output**: Per-event log loss, top-1 correctness, Brier score and confidence, labelled by step type

**Steps**:
1. [x] - `p1` - Replay each session to label every event as a decision, local check, system check or bookkeeping step - `inst-label`
2. [x] - `p1` - Score the probability each forecast gave the event that happened, after rejecting missing or invalid matrices - `inst-score`

### Paired session bootstrap

- [x] `p1` - **ID**: `cpt-nextgear-algo-evaluation-bootstrap`

**Input**: Scores of two predictors on the same events, a resample count, a seed and a step type

**Output**: The mean log-loss difference per event and its 95% interval

**Steps**:
1. [x] - `p1` - Sum the per-event differences and count events within each session, after checking both score sets cover the same events - `inst-collect`
2. [x] - `p1` - **FOR EACH** resample, draw sessions with replacement and divide the summed difference by the summed event count - `inst-resample`
3. [x] - `p1` - **RETURN** the observed difference with the 2.5th and 97.5th percentiles - `inst-interval`

### What-if verdicts

- [x] `p1` - **ID**: `cpt-nextgear-algo-evaluation-what-if`

**Input**: Predictors, held-out sessions, priors and the oracle queried with do()

**Output**: Verdict accuracy and log loss for untaken gears, and the predicted chance that a forced submission passes

**Steps**:
1. [x] - `p1` - **FOR EACH** open decision point, append each of the ten gears and a submission to the prefix, and ask the checks for the true verdict using the session's hidden specification - `inst-queries`
2. [x] - `p1` - Score each predictor's verdict probabilities against the truth; the do() oracle treats the appended action as forced, not as evidence - `inst-score`

### Unseen traces

- [x] `p1` - **ID**: `cpt-nextgear-algo-evaluation-novel`

**Input**: Training sessions and the scored test sessions

**Output**: Scores and paired comparisons on test sessions whose exact event sequence never occurs in training

**Steps**:
1. [x] - `p1` - Split the test set by whether its event sequence appears verbatim in training - `inst-split`
2. [x] - `p1` - Summarise and compare the predictors on the unseen part only - `inst-compare`

### Shifted agent

- [x] `p2` - **ID**: `cpt-nextgear-algo-evaluation-shift`

**Input**: Sessions generated with changed priors, the trained predictors, and oracles with the new and the old priors

**Output**: Gap to the matching oracle and paired comparisons

**Steps**:
1. [x] - `p1` - Score the frozen predictors, the oracle with the new priors and the oracle with the old priors on the shifted sessions - `inst-score`

### Unseen requirement combination

- [x] `p1` - **ID**: `cpt-nextgear-algo-evaluation-holdout`

**Input**: The training data, the holdout group, and a seed for new sessions

**Output**: Scores of models trained without the group on new sessions from it

**Steps**:
1. [x] - `p1` - Draw new sessions from the base priors and keep 600 whose specification needs the Chat Engine with both the Policy Manager and the License Resolver - `inst-sample`
2. [x] - `p1` - Remove that group from training and validation and train a GRU on the rest - `inst-exclude`
3. [x] - `p1` - Refit the count models without the group and compare all of them, and the normal GRU, on the new sessions - `inst-score`

## 4. States (CDSL)

### No lifecycle states

Evaluation computes and writes; session state belongs to `cpt-nextgear-state-simulator-session`.

## 5. Definitions of Done

### Benchmark report

- [x] `p1` - **ID**: `cpt-nextgear-dod-evaluation-report`

The system **MUST** write `results/report.json` with every metric above, paired intervals, all configured GRU seeds and stage timings, and render `results/REPORT.md` and two figures from it without computing anything new.

**Implements**:
- `cpt-nextgear-algo-evaluation-score`
- `cpt-nextgear-algo-evaluation-bootstrap`
- `cpt-nextgear-algo-evaluation-what-if`
- `cpt-nextgear-algo-evaluation-novel`
- `cpt-nextgear-algo-evaluation-shift`
- `cpt-nextgear-algo-evaluation-holdout`

**Constraints**: `cpt-nextgear-constraint-cpu-only`

**Touches**:
- CLI: `evaluate`, `all`
- Files: `results/report.json`, `results/REPORT.md`, `results/figures/`

## 6. Acceptance Criteria

- [x] Identical score sets give a zero difference with a zero-width interval; a clearly better model gets an interval below zero.
- [x] Scores for different events, missing sessions and invalid probabilities are refused.
- [x] The do() oracle answers every what-if gear verdict correctly.
- [x] The holdout group is never in the data used to train the holdout models.
