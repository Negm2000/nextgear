---
version: 2.0
description: One command reproduces everything; another replays a held-out session.
---

# Feature: Pipeline

<!-- toc -->

- [1. Feature Context](#1-feature-context)
  - [1.1 Overview](#11-overview)
  - [1.2 Purpose](#12-purpose)
  - [1.3 Actors](#13-actors)
  - [1.4 References](#14-references)
- [2. Actor Flows (CDSL)](#2-actor-flows-cdsl)
  - [Reproduce the benchmark](#reproduce-the-benchmark)
  - [Replay a session](#replay-a-session)
- [3. Processes / Business Logic (CDSL)](#3-processes--business-logic-cdsl)
  - [Orchestration only](#orchestration-only)
- [4. States (CDSL)](#4-states-cdsl)
  - [No lifecycle states](#no-lifecycle-states)
- [5. Definitions of Done](#5-definitions-of-done)
  - [Commands](#commands)
- [6. Acceptance Criteria](#6-acceptance-criteria)

<!-- /toc -->

One command reproduces everything; another replays a held-out session.

- [x] `p1` - **ID**: `cpt-nextgear-featstatus-pipeline`
## 1. Feature Context

- [x] `p1` - `cpt-nextgear-feature-pipeline`

### 1.1 Overview

`all` generates the data, trains the GRUs and writes the report. `demo` replays one held-out session, printing each forecast next to what happened, then asks what the checks would have said to every action the agent could have taken at one decision point. `hero` draws one held-out session as an animated SVG for the README. The session is chosen by a stated rule rather than at random, and the README says so.

### 1.2 Purpose

Make the results reproducible with one command, and make individual predictions inspectable.

**Requirements**: `cpt-nextgear-fr-demo`, `cpt-nextgear-fr-traceability`, `cpt-nextgear-nfr-reproducible`, `cpt-nextgear-nfr-runtime`

**Principles**: `cpt-nextgear-principle-small`

### 1.3 Actors

| Actor | Role in Feature |
|-------|-----------------|
| `cpt-nextgear-actor-reviewer` | Runs the pipeline and the demo |
| `cpt-nextgear-actor-researcher` | Runs them with another configuration |

### 1.4 References

- **PRD**: [PRD.md](../PRD.md)
- **Design**: [DESIGN.md](../DESIGN.md)
- **Dependencies**: `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors`, `cpt-nextgear-feature-evaluation`

## 2. Actor Flows (CDSL)

**Use cases**: `cpt-nextgear-usecase-reproduce`, `cpt-nextgear-usecase-inspect`

### Reproduce the benchmark

- [x] `p1` - **ID**: `cpt-nextgear-flow-pipeline-reproduce`

**Actor**: `cpt-nextgear-actor-reviewer`

**Success Scenarios**:
- The report, its Markdown summary and the figures are written, with the time each stage took.

**Error Scenarios**:
- Checkpoints that do not match the data or the model settings are refused with an instruction to retrain.

**Steps**:
1. [x] - `p1` - Load the data, regenerating it first **IF** it is missing or was made with other settings - `inst-generate`
2. [x] - `p1` - Train one GRU per seed and one without the holdout group, in parallel, and stamp the models with the data and settings they were trained on - `inst-train`
3. [x] - `p1` - Refuse mismatched models, then run the evaluation - `inst-evaluate`
4. [x] - `p1` - Write `report.json`, `REPORT.md` and the figures - `inst-publish`

### Replay a session

- [x] `p2` - **ID**: `cpt-nextgear-flow-pipeline-demo`

**Actor**: `cpt-nextgear-actor-reviewer`

**Success Scenarios**:
- Each forecast is printed before the event it predicts and marked right or wrong, followed by a what-if table.

**Error Scenarios**:
- The session index or the decision position is out of range.

**Steps**:
1. [x] - `p1` - **FOR EACH** event, print the GRU's top guess made before it, and the probability the GRU, the n-gram and the oracle gave what happened - `inst-replay`
2. [x] - `p1` - At one decision point, print the oracle's belief about the hidden specification, the GRU's verdict for every gear next to the true one, and the chance a forced submission passes - `inst-what-if`

## 3. Processes / Business Logic (CDSL)

### Orchestration only

The processes are specified in `cpt-nextgear-feature-simulator`, `cpt-nextgear-feature-predictors` and `cpt-nextgear-feature-evaluation`.

## 4. States (CDSL)

### No lifecycle states

Commands run to completion; session state belongs to `cpt-nextgear-state-simulator-session`.

## 5. Definitions of Done

### Commands

- [x] `p1` - **ID**: `cpt-nextgear-dod-pipeline-commands`

The command line **MUST** offer `all`, `train`, `evaluate`, `demo` and `hero`, take the configuration and directories as options, and record the runtime, environment and thread count of `all`.

**Implements**:
- `cpt-nextgear-flow-pipeline-reproduce`
- `cpt-nextgear-flow-pipeline-demo`

**Constraints**: `cpt-nextgear-constraint-cpu-only`

**Touches**:
- CLI: `all`, `train`, `evaluate`, `demo`, `hero`
- Files: `configs/*.toml`, `assets/session.svg`

## 6. Acceptance Criteria

- [x] A toy configuration runs end to end, then the demo and the animation, in a test.
- [x] Models stamped with other settings are refused.
- [x] The recorded reference run took 503 seconds on Windows 11 with 16 CPU threads. Runtime on other machines will differ.
