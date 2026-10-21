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

Nextgear asks whether a recurrent model predicts assembly and repair events better than counts, and where that improvement fails to transfer. It delivers a reproducible local experiment and an inspectable demonstration.

### 1.2 Background / Problem Statement

The take-home asks for authored discrete events, a separate meaningful simulator, a next-event model developed using Constructor Fabric, a statistical benchmark and runnable repository. The architecture domain connects this exercise to the role's interest in synthetic datasets and consequences of composition decisions. Public gear documentation motivates vocabulary and ordering; the stochastic model is authored. See [Fabric usage and sources](../FABRIC_USAGE.md).

### 1.3 Goals (Business Outcomes)

A reviewer can run a supplied checkpoint, reproduce the experiment, inspect predictions and assess the evidence without mistaking overall accuracy for generalization. A negative result is an acceptable outcome. The recorded GRU gain on IID data and failure on an excluded combination are both retained.

### 1.4 Glossary

| Term | Meaning |
|---|---|
| Gear | Capability unit proposed for an ordered request path |
| Session | Complete event sequence ending admissible or abandoned |
| Prefix | Events observed before a forecast |
| Visible state | Assembly, counters and pending phase reconstructible from events |
| Hidden state | Requirements, budget and agent traits unknown to predictors |
| Oracle | Bayesian prediction using generator equations and priors |
| Intervention | Forced action applied without using it as evidence about hidden values |

## 2. Actors

### 2.1 Human Actors

#### Reviewer

**ID**: `cpt-nextgear-actor-reviewer`

Runs commands, checks results and inspects assumptions.

#### Researcher

**ID**: `cpt-nextgear-actor-researcher`

Changes experimental settings or models and reruns evaluation.

### 2.2 System Actors

#### Simulated agent

**ID**: `cpt-nextgear-actor-agent`

Knows its session requirements and proposes stochastic assembly actions.

#### Checker

**ID**: `cpt-nextgear-actor-checker`

Answers local proposals and whole assemblies with deterministic rules.

### 2.3 Actor Permissions

Reviewers and researchers may inspect all saved artifacts. Predictors receive events only; the oracle receives equations and priors, and evaluation reads hidden fields to compute truth.

## 3. Operational Concept & Environment

### 3.1 Module-Specific Environment Constraints

Python 3.12, CPU, local files. No service, GPU or API key is required after dependency installation. CI targets Windows and Linux. TeX is needed only to rebuild TikZ diagrams; prediction and statistical figures do not require it.

## 4. Scope

### 4.1 In Scope

Twenty-four events, ten gears, seeded sessions, count baselines, GRU, Bayesian reference, probability scoring, clustered intervals, overlap/shift/group probes, one-step what-if queries and a demonstration.

### 4.2 Out of Scope

Production Fabric gears, GearSpec/AppGraph, real code mining, deployments and planning gains. Multi-step Monte Carlo rollouts were removed to keep the experiment small and its evidence interpretable.

## 5. Functional Requirements

### 5.1 Experiment and delivery

#### Event vocabulary

- [x] `p1` - **ID**: `cpt-nextgear-fr-event-vocabulary`

The system **MUST** define 24 event names, each with a short text description, and represent a session as an ordered sequence of these events.

#### Session generator

- [x] `p1` - **ID**: `cpt-nextgear-fr-session-generator`

The system **MUST** generate complete seeded sessions separately from predictors; retain hidden fields only as evaluation ground truth.

#### Composition checks

- [x] `p1` - **ID**: `cpt-nextgear-fr-checks`

The system **MUST** compute local and whole-system verdicts from explicit rules and label domain-inspired rules separately from authored assumptions.

#### Prediction contract

- [x] `p1` - **ID**: `cpt-nextgear-fr-next-event-prediction`

The system **MUST** return a distribution over the whole vocabulary for each unfinished valid event prefix.

#### Count baselines

- [x] `p1` - **ID**: `cpt-nextgear-fr-baselines`

The system **MUST** compare frequency, interpolated n-grams and counts over engineered visible state, fitted on the same training split.

#### Learned model

- [x] `p1` - **ID**: `cpt-nextgear-fr-learned-model`

The system **MUST** train a one-layer GRU on event IDs alone with validation early stopping; report all configured seeds without selecting the best test seed.

#### Bayes reference

- [x] `p1` - **ID**: `cpt-nextgear-fr-oracle`

The system **MUST** infer hidden values from the prefix using generator equations and priors. State when those priors match an evaluation distribution and when the oracle is a common reference only.

#### Probability benchmark

- [x] `p1` - **ID**: `cpt-nextgear-fr-benchmark`

The system **MUST** report log loss, Brier score and accuracy overall and by step type, plus top-prediction calibration on decisions and system checks.

#### Statistical comparison

- [x] `p1` - **ID**: `cpt-nextgear-fr-statistics`

The system **MUST** compare models on the same events with a paired session bootstrap of event-weighted log-loss differences, reporting conditional intervals and their limits.

#### Alternative actions

- [x] `p1` - **ID**: `cpt-nextgear-fr-what-if`

The system **MUST** query every gear and submission at open decision points, compare verdicts to checks, and distinguish observational action evidence from a forced action.

#### Novel complete traces

- [x] `p1` - **ID**: `cpt-nextgear-fr-unseen-traces`

The system **MUST** report exact train/test trace overlap and score the novel full-trace subset, without claiming that its prefixes or subsequences are novel.

#### Changed distribution

- [x] `p1` - **ID**: `cpt-nextgear-fr-shift`

The system **MUST** evaluate fixed predictors on a changed requirement mix and agent policy; compare against both matching and stale-prior oracle predictions.

#### Excluded requirements

- [x] `p1` - **ID**: `cpt-nextgear-fr-unseen-combination`

The system **MUST** exclude Chat Engine with Policy Manager and License Resolver from training and validation for retrained models; score new sessions from that group and report negative findings.

#### Demonstration

- [x] `p1` - **ID**: `cpt-nextgear-fr-demo`

The system **MUST** offer a terminal replay with pre-event forecasts and valid what-if queries, plus an illustrative SVG animation whose selection is disclosed.

#### Fabric workflow

- [x] `p1` - **ID**: `cpt-nextgear-fr-traceability`

The system **MUST** maintain Studio requirements, decisions, design and feature-to-code links; provide a short Fabric usage note and validation command.

## 6. Non-Functional Requirements

### 6.1 NFR Inclusions

#### Reproducibility

- [x] `p1` - **ID**: `cpt-nextgear-nfr-reproducible`

The system **MUST** use explicit seeds, configurations and settings stamps. Rebuild missing datasets from seeds, record environment versions, and document that stamps do not hash edited data or generator code.

#### Information boundary

- [x] `p1` - **ID**: `cpt-nextgear-nfr-information-boundary`

The system **MUST** keep hidden specifications and future events out of the learned predictor and count baselines. Clearly identify engineered state knowledge and the oracle's additional generator knowledge.

#### Local runtime

- [x] `p1` - **ID**: `cpt-nextgear-nfr-runtime`

The system **MUST** support CPU execution and record stage timings and thread count. Report the measured 503-second Windows run with 16 threads as a measurement, not a universal runtime guarantee.

### 6.2 NFR Exclusions

No production availability, security certification, distributed throughput or cross-hardware bitwise determinism target is claimed.

## 7. Public Library Interfaces

### 7.1 Public API Surface

CLI: `python -m nextgear all|train|evaluate|demo|hero`. Predictors provide `predict_session`, `predict_many` and `predict_next`; matrices have 24 columns and one row per predicted event after SESSION_STARTED.

### 7.2 External Integration Contracts

Local JSON Lines sessions, PyTorch state-dictionary checkpoints, a JSON report, Markdown summary and SVG figures. Public source documents are motivation, not runtime integrations.

## 8. Use Cases

### UC-001 Reproduce

**ID**: `cpt-nextgear-usecase-reproduce`

Reviewer installs dependencies and runs `all`: datasets, training, evaluation, report. Invalid settings or mismatched model stamps fail visibly.

### UC-002 Inspect

**ID**: `cpt-nextgear-usecase-inspect`

Reviewer runs `demo`, reads forecasts and selects an open decision position for alternatives. Out-of-range indices and exhausted budgets are refused.

## 9. Acceptance Criteria

The test suite checks rule examples, complete seeded sessions, causal prefixes, valid distributions, checkpoint round trips, paired-event identity, process equivalence and a small full pipeline. [The report](../results/REPORT.md) records the actual benchmark; no requirement mandates a favorable holdout result.

## 10. Dependencies

NumPy for arrays/statistics, PyTorch for the GRU, matplotlib for figures and Constructor Studio for artifact validation. Versions and install commands are in the README and lock file.

## 11. Assumptions

Requirement frequencies, mistake policy, verdict precedence, latency values, budgets and cache effects are authored. Splits are independent random streams, but identical event sequences can recur. Shared generator/oracle code is an internal reference, not independent validation.

## 12. Risks

Artificial regularities, repeated prefixes, exploratory test inspection, one group/seed in the exclusion test and observational action confounding limit inference. Intervals condition on fitted models and the generator. The animation is selected for illustration, not representativeness.
