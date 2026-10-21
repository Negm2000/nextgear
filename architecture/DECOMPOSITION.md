---
version: 2.0
description: Decomposition - Nextgear
---

# Decomposition - Nextgear

<!-- toc -->

- [1. Overview](#1-overview)
- [2. Entries](#2-entries)
  - [2.1 Simulator - HIGH](#21-simulator---high)
  - [2.2 Predictors - HIGH](#22-predictors---high)
  - [2.3 Evaluation - HIGH](#23-evaluation---high)
  - [2.4 Pipeline - HIGH](#24-pipeline---high)
- [3. Feature Dependencies](#3-feature-dependencies)

<!-- /toc -->

## 1. Overview

The four features follow the data: generation, prediction, evaluation, then the commands and presentation that tie them together. They share one design component because they are modules of one local program, each owning its own files. There is no separate audit layer.

## 2. Entries

- [x] `p1` - **ID**: `cpt-nextgear-status-overall`

### 2.1 [Simulator](features/simulator.md) - HIGH

- [x] `p1` - **ID**: `cpt-nextgear-feature-simulator`

- **Purpose**: Define the events and the checks, and generate sessions whose visible transitions every other feature reuses.
- **Depends On**: None
- **Scope**: Event vocabulary, local and system checks, hidden-value sampling, session generation and storage, visible state transitions.
- **Out of scope**: Production gear services and multi-step planning.
- **Requirements Covered**:

  - [x] `p1` - `cpt-nextgear-fr-event-vocabulary`
  - [x] `p1` - `cpt-nextgear-fr-session-generator`
  - [x] `p1` - `cpt-nextgear-fr-checks`
  - [x] `p1` - `cpt-nextgear-nfr-reproducible`

- **Design Principles Covered**:

  - [x] `p2` - `cpt-nextgear-principle-one-transition-function`
  - [x] `p2` - `cpt-nextgear-principle-small`

- **Design Constraints Covered**: `cpt-nextgear-constraint-cpu-only`
- **Domain Model Entities**: Session, Spec, Hidden, State, Priors.
- **Design Components**: `cpt-nextgear-component-experiment`
- **API**: `cpt-nextgear-interface-cli`
- **Sequences**: `cpt-nextgear-seq-reproduce`, `cpt-nextgear-seq-inspect`
- **Data**: `cpt-nextgear-db-local-files`, `cpt-nextgear-dbtable-sessions`

### 2.2 [Predictors](features/predictors.md) - HIGH

- [x] `p1` - **ID**: `cpt-nextgear-feature-predictors`

- **Purpose**: Predict the next event from a prefix of events.
- **Depends On**: `cpt-nextgear-feature-simulator`
- **Scope**: Frequency, n-gram and state-count models, the GRU and the Bayesian reference, all behind one prediction contract.
- **Out of scope**: Production services, multi-step planning and predictors that read hidden values.
- **Requirements Covered**:

  - [x] `p1` - `cpt-nextgear-fr-next-event-prediction`
  - [x] `p1` - `cpt-nextgear-fr-baselines`
  - [x] `p1` - `cpt-nextgear-fr-learned-model`
  - [x] `p1` - `cpt-nextgear-fr-oracle`
  - [x] `p1` - `cpt-nextgear-nfr-information-boundary`

- **Design Principles Covered**:

  - [x] `p2` - `cpt-nextgear-principle-events-only`
  - [x] `p2` - `cpt-nextgear-principle-one-transition-function`

- **Design Constraints Covered**: `cpt-nextgear-constraint-cpu-only`
- **Domain Model Entities**: Event prefixes and distributions.
- **Design Components**: `cpt-nextgear-component-experiment`
- **API**: `cpt-nextgear-interface-predictor`
- **Sequences**: `cpt-nextgear-seq-reproduce`, `cpt-nextgear-seq-inspect`
- **Data**: `cpt-nextgear-db-local-files`, `cpt-nextgear-dbtable-sessions`

### 2.3 [Evaluation](features/evaluation.md) - HIGH

- [x] `p1` - **ID**: `cpt-nextgear-feature-evaluation`

- **Purpose**: Turn predictions into evidence about what the models have learned.
- **Depends On**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`
- **Scope**: Per-event scores, paired intervals, the novel-trace, changed-agent and excluded-combination tests, what-if verdicts and the benchmark report.
- **Out of scope**: Production services and multi-step planning.
- **Requirements Covered**:

  - [x] `p1` - `cpt-nextgear-fr-benchmark`
  - [x] `p1` - `cpt-nextgear-fr-statistics`
  - [x] `p1` - `cpt-nextgear-fr-what-if`
  - [x] `p1` - `cpt-nextgear-fr-unseen-traces`
  - [x] `p1` - `cpt-nextgear-fr-shift`
  - [x] `p1` - `cpt-nextgear-fr-unseen-combination`
  - [x] `p1` - `cpt-nextgear-nfr-runtime`

- **Design Principles Covered**:

  - [x] `p2` - `cpt-nextgear-principle-absolute-reference`
  - [x] `p2` - `cpt-nextgear-principle-events-only`

- **Design Constraints Covered**: `cpt-nextgear-constraint-cpu-only`
- **Domain Model Entities**: Sessions and per-event score matrices.
- **Design Components**: `cpt-nextgear-component-experiment`
- **API**: `cpt-nextgear-interface-cli`
- **Sequences**: `cpt-nextgear-seq-reproduce`, `cpt-nextgear-seq-inspect`
- **Data**: `cpt-nextgear-db-local-files`, `cpt-nextgear-dbtable-sessions`

### 2.4 [Pipeline](features/pipeline.md) - HIGH

- [x] `p1` - **ID**: `cpt-nextgear-feature-pipeline`

- **Purpose**: Make the experiment runnable and its predictions inspectable.
- **Depends On**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`, `cpt-nextgear-feature-evaluation`
- **Scope**: Configuration, commands, settings stamps, the terminal replay and the animation.
- **Out of scope**: Production services and multi-step planning.
- **Requirements Covered**:

  - [x] `p1` - `cpt-nextgear-fr-demo`
  - [x] `p1` - `cpt-nextgear-fr-traceability`
  - [x] `p1` - `cpt-nextgear-nfr-reproducible`
  - [x] `p1` - `cpt-nextgear-nfr-runtime`

- **Design Principles Covered**:

  - [x] `p2` - `cpt-nextgear-principle-small`

- **Design Constraints Covered**: `cpt-nextgear-constraint-cpu-only`
- **Domain Model Entities**: Paths, settings, models and reports.
- **Design Components**: `cpt-nextgear-component-experiment`
- **API**: `cpt-nextgear-interface-cli`
- **Sequences**: `cpt-nextgear-seq-reproduce`, `cpt-nextgear-seq-inspect`
- **Data**: `cpt-nextgear-db-local-files`, `cpt-nextgear-dbtable-sessions`

## 3. Feature Dependencies

Predictors depend on the simulator's vocabulary and visible state. Evaluation depends on simulator truth and on the predictors. The pipeline orchestrates all three and renders the results. Every dependency points one way: the generator never imports a learned model.
