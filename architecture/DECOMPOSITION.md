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

Four features follow generation → prediction → evaluation → commands/presentation. Shared component references denote one local application with distinct module ownership. There is no separate audit layer.

## 2. Entries

- [x] `p1` - **ID**: `cpt-nextgear-status-overall`

### 2.1 [Simulator](features/simulator.md) - HIGH

- [x] `p1` - **ID**: `cpt-nextgear-feature-simulator`

- **Purpose**: Rules, vocabulary, sessions and visible transitions.
- **Depends On**: None
- **Scope**: Rules, vocabulary, sessions and visible transitions.
- **Out of scope**: Production services and multi-step planning.
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

- **Purpose**: Count models, GRU and Bayesian reference.
- **Depends On**: `cpt-nextgear-feature-simulator`
- **Scope**: Count models, GRU and Bayesian reference.
- **Out of scope**: Production services and multi-step planning.
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

- **Purpose**: Scores, intervals, cohorts, what-if evidence and report.
- **Depends On**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`
- **Scope**: Scores, intervals, cohorts, what-if evidence and report.
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

- **Purpose**: Configuration, commands, terminal replay and animation.
- **Depends On**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`, `cpt-nextgear-feature-evaluation`
- **Scope**: Configuration, commands, terminal replay and animation.
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

Predictors depend on simulator vocabulary/state. Evaluation depends on simulator truth and predictors. Pipeline orchestrates all three and presentation. Dependencies are one-way; shared domain state never causes the generator to import learned models.
