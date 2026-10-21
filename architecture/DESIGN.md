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

Nextgear is a local Python experiment with three separate stages: generation, prediction and scoring. Predictors read event histories; only evaluation reads the stored hidden truth. Because the generator and the oracle share one transition function, the oracle is an exact Bayesian reference under the declared priors.

### 1.2 Architecture Drivers

**ADRs**: `cpt-nextgear-adr-domain`, `cpt-nextgear-adr-bayes-oracle`, `cpt-nextgear-adr-gru`, `cpt-nextgear-adr-session-bootstrap`, `cpt-nextgear-adr-fabric-dependencies`.

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
| `cpt-nextgear-nfr-reproducible` | Seeds and split sizes live in `configs/*.toml`, and every split has its own seed. `data/stamp.txt` and `models/stamp.txt` hash the settings that produced the data and checkpoints; missing or mismatched data is regenerated, and mismatched models are refused. `report.json` records library versions. The stamps cover settings only, not edited data or generator code. |
| `cpt-nextgear-nfr-information-boundary` | Predictors receive event tuples only, and row t of a forecast uses events up to t. The state-count model is labelled domain-informed, and the oracle's extra knowledge of equations and priors is stated. Tests check that predictors never see hidden values and that the generator imports no predictor. |
| `cpt-nextgear-nfr-runtime` | CPU-only PyTorch with a `--threads` option. `report.json` records the thread count and the time of each stage. The README reports the 1,422-second Linux run with 4 threads as a measurement, not a guarantee. |

### 1.3 Architecture Layers

![Modules and information boundaries](../assets/architecture.svg)

A single application component holds the domain rules and generator, the predictors, the metrics, the orchestration and the rendering. It needs no services and no database. Source: [src/nextgear](../src/nextgear/).

## 2. Principles & Constraints

### 2.1 Design Principles

#### One transition function

- [x] `p2` - **ID**: `cpt-nextgear-principle-one-transition-function`

The generator samples from `next_distribution`, and the oracle computes its likelihoods with the same function. Separate tests exercise the rules. The two cannot drift apart, but an error in that function would affect both.

#### Events only

- [x] `p2` - **ID**: `cpt-nextgear-principle-events-only`

Each forecast is made before its target event. The learned and count models never receive hidden session fields. The engineered state counts are labelled domain-informed.

#### Absolute reference under declared assumptions

- [x] `p2` - **ID**: `cpt-nextgear-principle-absolute-reference`

Where the evaluation sessions come straight from the oracle's priors, scores are compared with it as the best achievable. The novel-trace subset and the group exclusion select sessions after generation; the oracle keeps the base prior and is not told about the selection, so there it serves as a common reference rather than the optimum.

#### Keep the experiment small

- [x] `p2` - **ID**: `cpt-nextgear-principle-small`

One recurrent layer, count baselines, one report and four features. Slow outcome rollouts and duplicate audit machinery were removed; the controls that carry statistical weight were kept.

### 2.2 Constraints

#### CPU execution

- [x] `p2` - **ID**: `cpt-nextgear-constraint-cpu-only`

Use CPU-only libraries and local files. Worker and thread counts are bounded, and worker functions live at module level behind a guarded entry point so that Windows process spawning works. Runtime is measured, not promised across machines.

## 3. Technical Architecture

### 3.1 Domain Model

| Entity | Definition |
|---|---|
| Spec | Execution gear, optional capabilities and latency budget in `rules.py` |
| Dependencies | Each gear's declared `deps` from gears-rust, in the generated `fabric_gears.py` |
| Hidden | Spec, careful-agent flag, and whether the agent knows about the outbound gateway and dependencies |
| State | Visible path, platform gears, cache/outbound flags, counters, phase and pending gear |
| Priors | Requirement probabilities, policy errors and budgets |
| Session | Identifier, event tuple and hidden ground truth |

The state machine in [simulator.py](../src/nextgear/simulator.py) reconstructs the visible state from events. [Its TikZ diagram](../assets/states.svg) separates the phases that are stochastic or depend on hidden values from deterministic bookkeeping.

### 3.2 Component Model

#### Local experiment

- [x] `p2` - **ID**: `cpt-nextgear-component-experiment`

##### Why this component exists

It delivers the whole assignment as one reproducible local program with clear boundaries between modules.

##### Responsibility scope

| Modules | Ownership |
|---|---|
| `events`, `fabric_gears`, `rules`, `simulator` | Vocabulary, declared gear dependencies, deterministic checks, hidden-state sampling and sessions |
| `baselines`, `gru`, `oracle` | Frequency, n-gram and state-count models; the GRU; exact posterior prediction |
| `evaluation` | Proper scores, step labels, bootstrap, calibration and one-step alternatives |
| `benchmark` | Split generation, training workers, cohort comparisons, settings stamps and timing |
| `report`, `demo`, `hero`, `cli` | Reports, terminal replay, animation and command dispatch |

##### Responsibility boundaries

The generator imports neither predictors nor evaluation. Predictors see event tuples; the oracle also knows the equations and the configured priors. Only the checks and evaluation use the true session specifications. Presentation renders recorded results and does not recompute any model evidence.

##### Related components (by ID)

There are no external application components. The four features divide ownership inside `cpt-nextgear-component-experiment`; they are modules of one local program, not network services.

### 3.3 API Contracts

**ID**: `cpt-nextgear-interface-predictor`

`predict_many(sequences)` returns a list of `(len(sequence)-1, 31)` matrices. Row t forecasts event t+1 from events up to t. `predict_next(prefixes)` returns one 31-way row for each valid nonempty prefix. Values are finite, nonnegative and sum to one. With `intervene=True`, the oracle advances the visible state through the forced final action without using it as evidence.

**ID**: `cpt-nextgear-interface-cli`

`all`, `train`, `evaluate`, `demo`, `hero`. Global path, configuration and thread options go before the command. The demo refuses invalid session or decision indices and exhausted action budgets. A settings mismatch requires retraining; the stamps do not detect manual edits to data or code.

### 3.4 Internal Dependencies

Vocabulary → rules → simulator. The state counts and the oracle reuse the visible transitions; the GRU uses event IDs. Evaluation imports simulator truth and the predictor contract. `benchmark` combines them, and the CLI calls `benchmark` and rendering. The generator does not depend on any predictor.

### 3.5 External Dependencies

NumPy for arrays and resampling; PyTorch for the GRU, Adam and weight-only checkpoint loading; matplotlib with its bundled Computer Modern fonts. Constructor Studio validates the engineering artifacts. `tools/extract_gears.py` regenerates `fabric_gears.py` from a gears-rust checkout, and the optional Rust harness in `tools/registry_check` builds against the same pinned commit. TeX and dvisvgm rebuild the two optional TikZ diagrams. After installation, ordinary runs need no network.

### 3.6 Interactions & Sequences

#### Reproduction sequence

**ID**: `cpt-nextgear-seq-reproduce`

**Use cases**: `cpt-nextgear-usecase-reproduce`

Reviewer → CLI → generate or load data → train and stamp checkpoints → score every test condition → JSON, Markdown and figures. The paired bootstrap uses the same resampled sessions for both models. `evaluate` checks the settings and then loads existing checkpoints.

#### Inspection sequence

**ID**: `cpt-nextgear-seq-inspect`

**Use cases**: `cpt-nextgear-usecase-inspect`

Reviewer → CLI → events-only forecasts → replay → alternatives at an open decision → true checks. `hero` selects an illustrative session and shows the forecast made before each event next to the oracle's belief after it.

### 3.7 Database schemas & tables

**ID**: `cpt-nextgear-db-local-files`

There is no database service. The dataset, checkpoint and report directories are CLI options.

#### Session records

**ID**: `cpt-nextgear-dbtable-sessions`

One JSON object per line: `session_id`, `events` and `hidden` (the nested spec and agent traits). IDs are unique across splits; event sequences need not be. Loading rejects truncated or invalid sessions. Hidden fields are stored for the checks and evaluation, and never passed to predictors.

Checkpoints store the model configuration, tensor state and validation history; the separate model stamp records the data and model settings. `report.json` stores scores, intervals, configuration, versions and timings. The stamps check configuration; they are not a cryptographic provenance record.

### 3.8 Deployment Topology

One local CPU process with a bounded number of training and scoring workers. Nothing is deployed. CI runs on Windows and Linux.

## 4. Additional context

This document describes the implementation as reviewed; it does not show that requirements came first. Shared simulator and oracle code and the authored assumptions limit external validity. The holdout reuses the main experiment's settings, so the exclusion test is exploratory.

## 5. Traceability

[PRD](PRD.md) · [Decisions](ADR/) · [Feature ownership](DECOMPOSITION.md) · [Feature algorithms](features/). Code markers cover the specified algorithms, flows, session state machine and definitions of done. They do not vouch for every line of Python.
