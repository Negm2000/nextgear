---
version: 2.0
description: Two count baselines, the GRU and the Bayes oracle, all behind one prediction contract.
---

# Feature: Predictors

<!-- toc -->

- [1. Feature Context](#1-feature-context)
  - [1.1 Overview](#11-overview)
  - [1.2 Purpose](#12-purpose)
  - [1.3 Actors](#13-actors)
  - [1.4 References](#14-references)
- [2. Actor Flows (CDSL)](#2-actor-flows-cdsl)
  - [Used by the pipeline](#used-by-the-pipeline)
- [3. Processes / Business Logic (CDSL)](#3-processes--business-logic-cdsl)
  - [n-gram](#n-gram)
  - [State counts](#state-counts)
  - [GRU training](#gru-training)
  - [Bayes oracle](#bayes-oracle)
- [4. States (CDSL)](#4-states-cdsl)
  - [No lifecycle states](#no-lifecycle-states)
- [5. Definitions of Done](#5-definitions-of-done)
  - [One prediction contract](#one-prediction-contract)
- [6. Acceptance Criteria](#6-acceptance-criteria)

<!-- /toc -->

Two count baselines, the GRU and the Bayes oracle, all behind one prediction contract.

- [x] `p1` - **ID**: `cpt-nextgear-featstatus-predictors`
## 1. Feature Context

- [x] `p1` - `cpt-nextgear-feature-predictors`

### 1.1 Overview

Every predictor maps a prefix of events to a probability for each of the 24 possible next events. The n-gram sees the last few events. The state-count model is given the simulator's state machine and counts what follows each visible state. The GRU learns its own summary of the whole history. The oracle knows the simulator's equations and priors and infers the hidden specification with Bayes' rule.

### 1.2 Purpose

Bracket the learned model between simple methods it must beat and the best result any events-only method can reach.

**Requirements**: `cpt-nextgear-fr-next-event-prediction`, `cpt-nextgear-fr-baselines`, `cpt-nextgear-fr-learned-model`, `cpt-nextgear-fr-oracle`, `cpt-nextgear-nfr-information-boundary`

**Principles**: `cpt-nextgear-principle-events-only`, `cpt-nextgear-principle-one-transition-function`

### 1.3 Actors

| Actor | Role in Feature |
|-------|-----------------|
| `cpt-nextgear-actor-reviewer` | Inspects individual forecasts |
| `cpt-nextgear-actor-researcher` | Changes model settings in the configuration |

### 1.4 References

- **PRD**: [PRD.md](../PRD.md)
- **Design**: [DESIGN.md](../DESIGN.md)
- **Dependencies**: `cpt-nextgear-feature-simulator`

## 2. Actor Flows (CDSL)

### Used by the pipeline

This feature has no user-facing flow; predictors are trained and queried inside `cpt-nextgear-flow-pipeline-reproduce` and `cpt-nextgear-flow-pipeline-demo`.

## 3. Processes / Business Logic (CDSL)

### n-gram

- [x] `p1` - **ID**: `cpt-nextgear-algo-predictors-ngram`

**Input**: Training sequences and a context length k

**Output**: A next-event distribution for any prefix

**Steps**:
1. [x] - `p1` - Count which event follows every context of 0 to k preceding events - `inst-count`
2. [x] - `p1` - Interpolate from the empty context to the longest one seen, Witten-Bell style, starting from a uniform distribution - `inst-interpolate`

### State counts

- [x] `p1` - **ID**: `cpt-nextgear-algo-predictors-state-counts`

**Input**: Training sequences

**Output**: A next-event distribution for any prefix

**Steps**:
1. [x] - `p1` - Replay each sequence through the state machine and count which event follows each visible state, at four levels of detail - `inst-count`
2. [x] - `p1` - Interpolate from the coarsest level to the most detailed one seen - `inst-interpolate`

### GRU training

- [x] `p1` - **ID**: `cpt-nextgear-algo-predictors-gru-train`

**Input**: Training and validation sequences, model settings and a seed

**Output**: The network with the lowest validation log loss

**Steps**:
1. [x] - `p1` - **FOR EACH** epoch, shuffle the training sequences and minimise cross-entropy of every next event with Adam and gradient clipping - `inst-epoch`
2. [x] - `p1` - Measure validation log loss; stop after `patience` epochs without improvement - `inst-early-stop`
3. [x] - `p1` - **RETURN** the weights from the best validation epoch - `inst-restore`

### Bayes oracle

- [x] `p1` - **ID**: `cpt-nextgear-algo-predictors-oracle`

**Input**: The priors and a prefix of events

**Output**: The exact next-event distribution given the prefix

**Steps**:
1. [x] - `p1` - Start from the prior over all 384 hidden parameter sets - `inst-prior`
2. [x] - `p1` - Forecast by averaging each hypothesis' next-event distribution, weighted by its posterior - `inst-mix`
3. [x] - `p1` - After each event, multiply every weight by the probability that hypothesis gave the event, then renormalise - `inst-update`
4. [x] - `p1` - **IF** the last action is forced rather than observed, move the state without updating the posterior (Pearl's do-operator) - `inst-intervene`

## 4. States (CDSL)

### No lifecycle states

Predictors are fitted once and then only queried; session state belongs to `cpt-nextgear-state-simulator-session`.

## 5. Definitions of Done

### One prediction contract

- [x] `p1` - **ID**: `cpt-nextgear-dod-predictors-contract`

Every predictor **MUST** return, for every prefix, a strictly valid distribution over the 24 events, computed from the event names alone; only the oracle may read the configured priors and simulator equations, and none may read a session's hidden parameters.

**Implements**:
- `cpt-nextgear-algo-predictors-ngram`
- `cpt-nextgear-algo-predictors-state-counts`
- `cpt-nextgear-algo-predictors-gru-train`
- `cpt-nextgear-algo-predictors-oracle`

**Constraints**: `cpt-nextgear-constraint-cpu-only`

**Touches**:
- Files: `models/*.pt`
- Entities: `Session`

## 6. Acceptance Criteria

- [x] Every predictor's rows sum to one, and querying a prefix gives the same row as a full pass over the session.
- [x] Changing a session's hidden parameters does not change any baseline's predictions.
- [x] The oracle never assigns zero probability to an event that happened, and beats both count baselines.
- [x] A saved GRU loads back to identical predictions.
