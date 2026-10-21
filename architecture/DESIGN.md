---
version: 2.0
status: approved
description: Technical Design - Nextgear
---

# Technical Design - Nextgear

<!-- toc -->

- [1. Architecture Overview](#1-architecture-overview)
  - [1.1 Architectural Vision](#11-architectural-vision)
  - [1.2 Architecture Drivers](#12-architecture-drivers)
  - [1.3 Architecture Layers](#13-architecture-layers)
- [2. Principles & Constraints](#2-principles--constraints)
  - [2.1 Design Principles](#21-design-principles)
  - [2.2 Constraints](#22-constraints)
- [3. Technical Architecture](#3-technical-architecture)
  - [3.1 Domain Model](#31-domain-model)
  - [3.2 Component Model](#32-component-model)
  - [3.3 API Contracts](#33-api-contracts)
  - [3.4 Internal Dependencies](#34-internal-dependencies)
  - [3.5 External Dependencies](#35-external-dependencies)
  - [3.6 Interactions & Sequences](#36-interactions--sequences)
  - [3.7 Database schemas & tables](#37-database-schemas--tables)
  - [3.8 Deployment Topology](#38-deployment-topology)
- [4. Additional context](#4-additional-context)
- [5. Traceability](#5-traceability)

<!-- /toc -->

## 1. Architecture Overview

### 1.1 Architectural Vision

A local Python experiment separates generation, prediction and scoring. Predictors consume histories; evaluation alone reads stored hidden truth. A shared transition function permits an exact Bayesian reference under declared priors.

### 1.2 Architecture Drivers

**ADRs**: `cpt-nextgear-adr-domain`, `cpt-nextgear-adr-bayes-oracle`, `cpt-nextgear-adr-gru`, `cpt-nextgear-adr-session-bootstrap`.

#### Functional Drivers

| Requirement | Allocation |
|---|---|
| `cpt-nextgear-fr-event-vocabulary` | Simulator |
| `cpt-nextgear-fr-session-generator` | Simulator |
| `cpt-nextgear-fr-checks` | Simulator |
| `cpt-nextgear-fr-next-event-prediction` | Predictors |
| `cpt-nextgear-fr-baselines` | Predictors |
| `cpt-nextgear-fr-learned-model` | Predictors |
| `cpt-nextgear-fr-oracle` | Predictors |
| `cpt-nextgear-fr-benchmark` | Evaluation |
| `cpt-nextgear-fr-statistics` | Evaluation |
| `cpt-nextgear-fr-what-if` | Evaluation |
| `cpt-nextgear-fr-unseen-traces` | Evaluation |
| `cpt-nextgear-fr-shift` | Evaluation |
| `cpt-nextgear-fr-unseen-combination` | Evaluation |
| `cpt-nextgear-fr-demo` | Pipeline |
| `cpt-nextgear-fr-traceability` | Pipeline |

#### NFR Allocation

| Requirement | Mechanism and verification |
|---|---|
| `cpt-nextgear-nfr-reproducible` | Reproducibility: Use explicit seeds, configurations and settings stamps. Rebuild missing datasets from seeds, record environment versions, and document that stamps do not hash edited data or generator code. |
| `cpt-nextgear-nfr-information-boundary` | Information boundary: Keep hidden specifications and future events out of the learned predictor and count baselines. Clearly identify engineered state knowledge and the oracle's additional generator knowledge. |
| `cpt-nextgear-nfr-runtime` | Local runtime: Support CPU execution and record stage timings and thread count. Report the measured 503-second Windows run with 16 threads as a measurement, not a universal runtime guarantee. |

### 1.3 Architecture Layers

![Modules and information boundaries](../assets/architecture.svg)

One application component contains domain rules/generation, predictors, reusable metrics, orchestration and rendering. It needs no services or database. Source: [src/nextgear](../src/nextgear/).

## 2. Principles & Constraints

### 2.1 Design Principles

#### One transition function

- [x] `p2` - **ID**: `cpt-nextgear-principle-one-transition-function`

Generator sampling and oracle likelihoods reuse `next_distribution`; tests separately exercise rules. This removes drift at the cost of correlated implementation errors.

#### Events only

- [x] `p2` - **ID**: `cpt-nextgear-principle-events-only`

Forecasts precede targets. Learned and count models never receive hidden session fields. Engineered state counts are labeled as domain-informed.

#### Absolute reference under declared assumptions

- [x] `p2` - **ID**: `cpt-nextgear-principle-absolute-reference`

Compare scores to the matching Bayes oracle where priors match. The group exclusion uses the original base prior as a common reference, without telling the oracle the selected group.

#### Keep the experiment small

- [x] `p2` - **ID**: `cpt-nextgear-principle-small`

One recurrent layer, count baselines, one report and four features. Remove slow outcome rollouts and duplicate audit machinery; preserve statistically useful controls.

### 2.2 Constraints

#### CPU execution

- [x] `p2` - **ID**: `cpt-nextgear-constraint-cpu-only`

Use CPU-only libraries and local files. Bound worker/thread counts; module-level worker functions and a guarded main support Windows spawning. Runtime is measured, not promised across machines.

## 3. Technical Architecture

### 3.1 Domain Model

| Entity | Definition |
|---|---|
| Spec | Execution gear, optional capabilities and latency budget in `rules.py` |
| Hidden | Spec, careful-agent flag and outbound-knowledge flag |
| State | Visible path, cache/outbound flags, counters, phase and pending gear |
| Priors | Requirement probabilities, policy errors and budgets |
| Session | Identifier, event tuple and hidden ground truth |

The state machine in [simulator.py](../src/nextgear/simulator.py) reconstructs visible state. [Its TikZ diagram](../assets/states.svg) distinguishes stochastic/hidden-dependent phases from deterministic bookkeeping.

### 3.2 Component Model

#### Local experiment

- [x] `p2` - **ID**: `cpt-nextgear-component-experiment`

##### Why this component exists

Deliver the complete assignment as a reproducible local program with clear internal module boundaries.

##### Responsibility scope

| Modules | Ownership |
|---|---|
| `events`, `rules`, `simulator` | Vocabulary, deterministic checks, hidden-state sampling and sessions |
| `baselines`, `gru`, `oracle` | Frequency/n-gram/state counts, learned recurrence, exact posterior prediction |
| `evaluation` | Proper scores, step labels, bootstrap, calibration and one-step alternatives |
| `benchmark` | Split generation, training workers, cohort comparisons, settings stamps and timing |
| `report`, `demo`, `hero`, `cli` | Reports, terminal replay, animation and command dispatch |

##### Responsibility boundaries

The generator imports no predictors/evaluation. Predictors see event tuples; the oracle additionally knows equations and configured priors. Only checks and evaluation use true session specifications. Presentation renders recorded results; it does not recompute fitted-model evidence.

##### Related components (by ID)

No external application components. The four features divide ownership inside `cpt-nextgear-component-experiment`; they are modules of one local program, not network services.

### 3.3 API Contracts

**ID**: `cpt-nextgear-interface-predictor`

`predict_many(sequences)` returns a list of `(len(sequence)-1, 24)` matrices. Row t forecasts event t+1 using events through t. `predict_next(prefixes)` returns one 24-way row per valid nonempty prefix. Values are finite, nonnegative and sum to one. The oracle's `intervene=True` skips evidence from the forced final action while advancing visible state.

**ID**: `cpt-nextgear-interface-cli`

`all`, `train`, `evaluate`, `demo`, `hero`; global paths/configuration/thread options precede the command. The demo refuses invalid session/decision indices and exhausted action budgets. Settings mismatches require retraining; stamps do not detect manual data/code edits.

### 3.4 Internal Dependencies

Vocabulary → rules → simulator; baselines/oracle reuse visible transitions, GRU uses event IDs. Evaluation imports simulator truth and the predictor contract. Benchmark combines them; CLI invokes benchmark and rendering. No generator-to-predictor dependency exists.

### 3.5 External Dependencies

NumPy arrays and random resampling; PyTorch GRU/Adam and weight-only checkpoint loading; matplotlib with bundled Computer Modern fonts. Constructor Studio validates engineering artifacts. TeX/dvisvgm rebuild the two optional TikZ diagrams; ordinary execution has no network dependency after install.

### 3.6 Interactions & Sequences

#### Reproduction sequence

**ID**: `cpt-nextgear-seq-reproduce`

**Use cases**: `cpt-nextgear-usecase-reproduce`

Reviewer → CLI → data generation/loading → training/checkpoint stamps → scoring/cohorts → JSON/Markdown/figures. The paired bootstrap shares sampled sessions across models. `evaluate` loads existing checkpoints after checking settings.

#### Inspection sequence

**ID**: `cpt-nextgear-seq-inspect`

**Use cases**: `cpt-nextgear-usecase-inspect`

Reviewer → CLI → events-only forecasts → replay → open-decision alternatives → true checks. Hero generation selects an illustrative session and separately shows pre-event forecasts and post-event beliefs.

### 3.7 Database schemas & tables

**ID**: `cpt-nextgear-db-local-files`

No database service. Dataset, checkpoint and report directories are CLI options.

#### Session records

**ID**: `cpt-nextgear-dbtable-sessions`

One JSON object per line: `session_id`, `events`, `hidden` (nested spec and agent traits). IDs are unique across splits; event sequences need not be. Loading rejects structurally truncated sessions. Hidden fields are persisted for checks/evaluation and stripped from predictor inputs.

Checkpoints store config, tensor state and validation history; the separate model stamp records data and model settings. `report.json` stores scores, intervals, configuration, versions and timings. Stamps are configuration checks, not a cryptographic provenance record.

### 3.8 Deployment Topology

Local CPU process with bounded training/scoring workers. No deployed backend. CI exercises Windows and Linux.

## 4. Additional context

This rewrite documents the reviewed implementation. It does not establish a requirements-first chronology. Shared simulator/oracle code and authored assumptions limit external validity. Holdout settings reuse the main experiment; the exclusion test is exploratory.

## 5. Traceability

[PRD](PRD.md) · [Decisions](ADR/) · [Feature ownership](DECOMPOSITION.md) · [Feature algorithms](features/). Code markers map only the specified algorithms, flows, session machine and definitions of done; they do not certify every line of Python.
