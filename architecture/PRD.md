---
version: 2.0
status: approved
description: PRD - Nextgear
---

# PRD - Nextgear

<!-- toc -->

- [1. Overview](#1-overview)
  - [1.1 Purpose](#11-purpose)
  - [1.2 Background / Problem Statement](#12-background--problem-statement)
  - [1.3 Goals (Business Outcomes)](#13-goals-business-outcomes)
  - [1.4 Glossary](#14-glossary)
- [2. Actors](#2-actors)
  - [2.1 Human Actors](#21-human-actors)
  - [2.2 System Actors](#22-system-actors)
  - [2.3 Actor Permissions](#23-actor-permissions)
- [3. Operational Concept & Environment](#3-operational-concept--environment)
  - [3.1 Module-Specific Environment Constraints](#31-module-specific-environment-constraints)
- [4. Scope](#4-scope)
  - [4.1 In Scope](#41-in-scope)
  - [4.2 Out of Scope](#42-out-of-scope)
- [5. Functional Requirements](#5-functional-requirements)
  - [5.1 Experiment and delivery](#51-experiment-and-delivery)
- [6. Non-Functional Requirements](#6-non-functional-requirements)
  - [6.1 NFR Inclusions](#61-nfr-inclusions)
  - [6.2 NFR Exclusions](#62-nfr-exclusions)
- [7. Public Library Interfaces](#7-public-library-interfaces)
  - [7.1 Public API Surface](#71-public-api-surface)
  - [7.2 External Integration Contracts](#72-external-integration-contracts)
- [8. Use Cases](#8-use-cases)
  - [UC-001 Reproduce](#uc-001-reproduce)
  - [UC-002 Inspect](#uc-002-inspect)
- [9. Acceptance Criteria](#9-acceptance-criteria)
- [10. Dependencies](#10-dependencies)
- [11. Assumptions](#11-assumptions)
- [12. Risks](#12-risks)

<!-- /toc -->

## 1. Overview

### 1.1 Purpose

Nextgear tests whether a recurrent model predicts the events of a gear-assembly session better than count models, how close it comes to the best achievable prediction, and where its advantage stops transferring. It ships as a reproducible local experiment with a demonstration that shows individual predictions.

### 1.2 Background / Problem Statement

The take-home assignment asks for a self-chosen sequence of discrete events with short descriptions, a separate generator of meaningful synthetic sequences, a next-event predictor developed using Constructor Fabric, a statistical benchmark and a runnable repository. Assembling a request pipeline from gears ties the exercise to the role's interest in synthetic architecture data and in the consequences of composition decisions. Fabric's gear documentation supplies the request order, and the dependencies each gear declares in constructorfabric/gears-rust supply the composition rules; the stochastic agent is authored. See [Fabric usage and sources](../FABRIC_USAGE.md).

### 1.3 Goals (Business Outcomes)

A reviewer can run a supplied checkpoint, reproduce the experiment, inspect individual predictions and judge the evidence without mistaking overall accuracy for generalization. A negative result counts as an outcome. The excluded-combination test failed under the first, hand-written version of the simulator and passes under the gears-rust dependencies; the README reports both.

### 1.4 Glossary

| Term | Meaning |
|---|---|
| Gear | A capability unit the agent proposes for an ordered request path |
| Platform gear | A gear off the request path that other gears declare as a dependency |
| Session | A complete event sequence that ends admissible or abandoned |
| Prefix | The events observed before a forecast |
| Visible state | The assembly, counters and pending phase, all reconstructible from events |
| Hidden state | Requirements, budget and agent traits that predictors never see |
| Oracle | Bayesian predictor that uses the generator's equations and priors |
| Intervention | A forced action, applied without treating it as evidence about hidden values |

## 2. Actors

### 2.1 Human Actors

#### Reviewer

**ID**: `cpt-nextgear-actor-reviewer`

Runs commands, checks results and inspects assumptions.

#### Researcher

**ID**: `cpt-nextgear-actor-researcher`

Changes experimental settings or models and reruns the evaluation.

### 2.2 System Actors

#### Simulated agent

**ID**: `cpt-nextgear-actor-agent`

Knows its session requirements and proposes stochastic assembly actions.

#### Checker

**ID**: `cpt-nextgear-actor-checker`

Gives deterministic verdicts on proposed gears and on submitted assemblies.

### 2.3 Actor Permissions

Reviewers and researchers can read every saved artifact. Predictors receive events only. The oracle also receives the generator's equations and priors. Evaluation reads hidden fields to compute the true answers.

## 3. Operational Concept & Environment

### 3.1 Module-Specific Environment Constraints

Python 3.12 on a CPU, with local files. Once dependencies are installed, no service, GPU or API key is needed. CI runs on Windows and Linux. TeX is needed only to rebuild the TikZ diagrams; predictions and statistical figures do not use it.

## 4. Scope

### 4.1 In Scope

Thirty-one events, sixteen gears, seeded sessions, count baselines, a GRU, a Bayesian reference, probability scores, session-clustered intervals, tests on novel traces, a changed agent and an excluded requirement group, one-step what-if queries, and a demonstration.

### 4.2 Out of Scope

Production Fabric gears, GearSpec/AppGraph, mining real code, deployment, and measured planning gains. Multi-step Monte Carlo rollouts were removed to keep the experiment small and its evidence easy to interpret.

## 5. Functional Requirements

### 5.1 Experiment and delivery

#### Event vocabulary

- [x] `p1` - **ID**: `cpt-nextgear-fr-event-vocabulary`

The system **MUST** define 31 event names, each with a short text description, and represent a session as an ordered sequence of these events.

#### Session generator

- [x] `p1` - **ID**: `cpt-nextgear-fr-session-generator`

The system **MUST** generate complete seeded sessions in code separate from the predictors, and keep hidden fields only as ground truth for evaluation.

#### Composition checks

- [x] `p1` - **ID**: `cpt-nextgear-fr-checks`

The system **MUST** compute local and whole-system verdicts from explicit rules, take gear dependencies from the gears-rust declarations at a pinned commit, check them against the gears-rust registry, and mark which rules come from Fabric and which are authored assumptions.

#### Prediction contract

- [x] `p1` - **ID**: `cpt-nextgear-fr-next-event-prediction`

The system **MUST** return a distribution over the whole vocabulary for each unfinished valid event prefix.

#### Count baselines

- [x] `p1` - **ID**: `cpt-nextgear-fr-baselines`

The system **MUST** compare a frequency model, interpolated n-grams and counts over engineered visible state, all fitted on the same training split.

#### Learned model

- [x] `p1` - **ID**: `cpt-nextgear-fr-learned-model`

The system **MUST** train a one-layer GRU on event IDs alone, stop early on validation loss, and report every configured seed rather than the one that scores best on test data.

#### Bayes reference

- [x] `p1` - **ID**: `cpt-nextgear-fr-oracle`

The system **MUST** infer hidden values from the prefix using the generator's equations and priors, and state where those priors match the evaluation distribution and where the oracle serves only as a common reference.

#### Probability benchmark

- [x] `p1` - **ID**: `cpt-nextgear-fr-benchmark`

The system **MUST** report log loss, Brier score and accuracy, overall and by step type, plus calibration of the top prediction on decisions and system checks.

#### Statistical comparison

- [x] `p1` - **ID**: `cpt-nextgear-fr-statistics`

The system **MUST** compare models on the same events with a paired session bootstrap of event-weighted log-loss differences, and report the intervals as conditional, with their limits.

#### Alternative actions

- [x] `p1` - **ID**: `cpt-nextgear-fr-what-if`

The system **MUST** query every gear and a submission at open decision points, compare the predicted verdicts with the checks, and distinguish predicting an observed action from forcing one.

#### Novel complete traces

- [x] `p1` - **ID**: `cpt-nextgear-fr-unseen-traces`

The system **MUST** report how many test traces exactly repeat a training trace and score the remaining novel full traces, without claiming that their prefixes or subsequences are novel, and treat the unconditioned oracle there as a common reference.

#### Changed distribution

- [x] `p1` - **ID**: `cpt-nextgear-fr-shift`

The system **MUST** evaluate the trained predictors, without retraining, on a changed requirement mix and agent policy, against oracles with both the new and the old priors.

#### Excluded requirements

- [x] `p1` - **ID**: `cpt-nextgear-fr-unseen-combination`

The system **MUST** exclude sessions needing the Chat Engine with both the Policy Manager and the License Resolver from the training and validation data of retrained models, score new sessions from that group, and report the result whether it is positive or negative.

#### Demonstration

- [x] `p1` - **ID**: `cpt-nextgear-fr-demo`

The system **MUST** offer a terminal replay that prints each forecast before its event and answers valid what-if queries, plus an illustrative SVG animation whose session selection is disclosed.

#### Fabric workflow

- [x] `p1` - **ID**: `cpt-nextgear-fr-traceability`

The system **MUST** maintain Studio requirements, decisions, design and feature-to-code links, and provide a short Fabric usage note with the validation command.

## 6. Non-Functional Requirements

### 6.1 NFR Inclusions

#### Reproducibility

- [x] `p1` - **ID**: `cpt-nextgear-nfr-reproducible`

The system **MUST** use explicit seeds, configurations and settings stamps, rebuild missing datasets from seeds, record environment versions, and document that the stamps do not hash edited data or generator code.

#### Information boundary

- [x] `p1` - **ID**: `cpt-nextgear-nfr-information-boundary`

The system **MUST** keep hidden specifications and future events away from the learned predictor and the count baselines, and state plainly what extra knowledge the engineered state counts and the oracle have.

#### Local runtime

- [x] `p1` - **ID**: `cpt-nextgear-nfr-runtime`

The system **MUST** run on a CPU and record stage timings and the thread count. The measured run, 1,422 seconds on Linux with 4 threads, is reported as a measurement, not a runtime guarantee.

### 6.2 NFR Exclusions

No target is set for production availability, security certification, distributed throughput or bitwise determinism across hardware.

## 7. Public Library Interfaces

### 7.1 Public API Surface

CLI: `python -m nextgear all|train|evaluate|demo|hero`. Predictors provide `predict_session`, `predict_many` and `predict_next`. Their matrices have 31 columns and one row for each predicted event after SESSION_STARTED.

### 7.2 External Integration Contracts

Sessions as local JSON Lines, PyTorch state-dictionary checkpoints, a JSON report, a Markdown summary and SVG figures. The public source documents are motivation, not runtime integrations.

## 8. Use Cases

### UC-001 Reproduce

**ID**: `cpt-nextgear-usecase-reproduce`

The reviewer installs dependencies and runs `all`, which generates datasets, trains, evaluates and writes the report. Invalid settings or mismatched model stamps stop the run with an error.

### UC-002 Inspect

**ID**: `cpt-nextgear-usecase-inspect`

The reviewer runs `demo`, reads the forecasts and picks an open decision position to ask about alternatives. Out-of-range indices and exhausted budgets are refused.

## 9. Acceptance Criteria

The test suite checks rule examples, complete seeded sessions, causal prefixes, valid distributions, checkpoint round trips, that paired scores cover the same events, serial and parallel equivalence, and a small full pipeline. [The report](../results/REPORT.md) records the benchmark itself; no requirement asks for a favourable holdout result.

## 10. Dependencies

NumPy for arrays and statistics, PyTorch for the GRU, matplotlib for figures and Constructor Studio for artifact validation. A Rust toolchain is needed only for the optional registry cross-check. Versions and install commands are in the README and the lock file.

## 11. Assumptions

Requirement frequencies, the mistake policy, verdict precedence, latency values, budgets and cache effects are authored. The dependency graph comes from gears-rust; matching the documented gear names to its crates is this project's reading. Splits come from independent random streams, but identical event sequences can still recur across them. Because the generator and oracle share code, the oracle is an internal reference, not independent validation.

## 12. Risks

Inference is limited by artificial regularities in the simulator, repeated prefixes, exploratory inspection of test results, a single group and seed in the exclusion test, and confounding between observed actions and hidden state. Intervals are conditional on the fitted models and the generator. The animation's session was selected to illustrate, not to be representative.
