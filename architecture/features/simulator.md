---
version: 2.0
description: The 31 events, the checks, and the generator whose transition function the oracle reuses.
---

# Feature: Simulator

<!-- toc -->

- [1. Feature Context](#1-feature-context)
  - [1.1 Overview](#11-overview)
  - [1.2 Purpose](#12-purpose)
  - [1.3 Actors](#13-actors)
  - [1.4 References](#14-references)
- [2. Actor Flows (CDSL)](#2-actor-flows-cdsl)
  - [Generated, not driven by a user](#generated-not-driven-by-a-user)
- [3. Processes / Business Logic (CDSL)](#3-processes--business-logic-cdsl)
  - [Local check](#local-check)
  - [System check](#system-check)
  - [Next-event distribution](#next-event-distribution)
  - [Generate a split](#generate-a-split)
- [4. States (CDSL)](#4-states-cdsl)
  - [Session](#session)
- [5. Definitions of Done](#5-definitions-of-done)
  - [Reproducible sessions](#reproducible-sessions)
- [6. Acceptance Criteria](#6-acceptance-criteria)

<!-- /toc -->

The 31 events, the checks, and the generator whose transition function the oracle reuses.

- [x] `p1` - **ID**: `cpt-nextgear-featstatus-simulator`
## 1. Feature Context

- [x] `p1` - `cpt-nextgear-feature-simulator`

### 1.1 Overview

An agent receives a hidden specification and assembles an application one gear at a time: request-path gears in the documented order, the outbound gateway, and the platform gears that the others depend on. A local check answers every proposed gear; a system check answers every submitted assembly. Which gear depends on which comes from the `deps` declarations in constructorfabric/gears-rust, extracted into `fabric_gears.py` at a pinned commit. The agent intends to add the next required gear, but with a small probability proposes something else. Everything that happens is written down as a sequence of named events.

### 1.2 Purpose

Produce sequences with real structure: some events follow from the visible history, and some depend on a specification that only the history can reveal.

**Requirements**: `cpt-nextgear-fr-event-vocabulary`, `cpt-nextgear-fr-session-generator`, `cpt-nextgear-fr-checks`, `cpt-nextgear-nfr-reproducible`

**Principles**: `cpt-nextgear-principle-one-transition-function`, `cpt-nextgear-principle-small`

### 1.3 Actors

| Actor | Role in Feature |
|-------|-----------------|
| `cpt-nextgear-actor-agent` | Proposes gears and submissions for its hidden specification |
| `cpt-nextgear-actor-checker` | Answers proposals and submissions with verdicts |

### 1.4 References

- **PRD**: [PRD.md](../PRD.md)
- **Design**: [DESIGN.md](../DESIGN.md)
- **Dependencies**: None

## 2. Actor Flows (CDSL)

### Generated, not driven by a user

This feature has no user-facing flow; it runs inside `cpt-nextgear-flow-pipeline-reproduce`.

## 3. Processes / Business Logic (CDSL)

### Local check

- [x] `p1` - **ID**: `cpt-nextgear-algo-simulator-local-check`

**Input**: The current request path, whether the outbound gateway is attached, the platform gears present, and the proposed gear

**Output**: STEP_ACCEPTED, ORDER_VIOLATION or BYPASS_VIOLATION

**Steps**:
1. [x] - `p1` - **IF** the gear is the outbound gateway or a platform gear, accept it unless it is already present - `inst-outbound`
2. [x] - `p1` - **IF** the gear is an execution gear and the Auth Resolver is not on the path, **RETURN** BYPASS_VIOLATION - `inst-bypass`
3. [x] - `p1` - Accept the gear only if it comes later in the fixed order than the last gear on the path, and an empty path only takes the API Gateway - `inst-order`

### System check

- [x] `p1` - **ID**: `cpt-nextgear-algo-simulator-system-check`

**Input**: The hidden specification and the submitted assembly

**Output**: The first failing verdict, or ASSEMBLY_ADMISSIBLE

**Steps**:
1. [x] - `p1` - **IF** a gear the specification needs on the request path is missing, **RETURN** MISSING_CAPABILITY - `inst-complete`
2. [x] - `p1` - **IF** any present gear declares a dependency that is not present, as the gears-rust registry would refuse to build, **RETURN** MISSING_DEPENDENCY - `inst-dependencies`
3. [x] - `p1` - **IF** the execution gear calls external services and no outbound gateway is attached, **RETURN** EXTERNAL_CALL_VIOLATION - `inst-external`
4. [x] - `p1` - **IF** the assembly has a gear that neither the specification nor any dependency needs, **RETURN** COST_VIOLATION - `inst-cost`
5. [x] - `p1` - **IF** the estimated latency exceeds the budget, **RETURN** LATENCY_VIOLATION; otherwise **RETURN** ASSEMBLY_ADMISSIBLE - `inst-latency`

### Next-event distribution

- [x] `p1` - **ID**: `cpt-nextgear-algo-simulator-next-event`

**Input**: Hidden parameters, the observable state and the priors

**Output**: A probability for every possible next event

**Steps**:
1. [x] - `p1` - **IF** the agent must decide and has used up its proposals or submissions, **RETURN** SESSION_ABANDONED with probability 1 - `inst-budget`
2. [x] - `p1` - **IF** the agent must decide, give its intended step probability 1 − ε and split ε evenly over the other sixteen actions, with ε set by whether the agent is careful - `inst-agent`
3. [x] - `p1` - Otherwise **RETURN** the single event the checks or the bookkeeping rules produce - `inst-checks`

### Generate a split

- [x] `p1` - **ID**: `cpt-nextgear-algo-simulator-generate`

**Input**: Session count, split seed, split name and priors

**Output**: Complete sessions written as JSON Lines

**Steps**:
1. [x] - `p1` - Derive one random generator per session from the split seed, so the first k sessions never depend on the count - `inst-seed`
2. [x] - `p1` - **FOR EACH** session, draw hidden parameters and sample events from the next-event distribution until the session ends - `inst-simulate`
3. [x] - `p1` - Write each session's identifier, events and hidden parameters as one JSON line - `inst-write`

## 4. States (CDSL)

### Session

- [x] `p1` - **ID**: `cpt-nextgear-state-simulator-session`

**States**: start, decide, local, revert, system, rollback, latency, done

**Initial State**: start

**Transitions**:
1. [x] - `p1` - **FROM** start **TO** decide **WHEN** SESSION_STARTED - `inst-start`
2. [x] - `p1` - **FROM** decide **TO** local **WHEN** a gear is proposed, **TO** system **WHEN** SUBMIT_ASSEMBLY, or **TO** done **WHEN** SESSION_ABANDONED - `inst-decide`
3. [x] - `p1` - **FROM** local **TO** decide **WHEN** STEP_ACCEPTED, adding the gear to the path, the outbound slot or the platform gears, or **TO** revert **WHEN** a violation is reported - `inst-local`
4. [x] - `p1` - **FROM** revert **TO** decide **WHEN** STEP_REVERTED - `inst-revert`
5. [x] - `p1` - **FROM** system **TO** done, rollback, decide or latency **WHEN** the verdict is admissible, missing capability or cost, external call or missing dependency, or latency - `inst-system`
6. [x] - `p1` - **FROM** rollback **TO** decide **WHEN** ROLLBACK_ASSEMBLY, emptying the assembly - `inst-rollback`
7. [x] - `p1` - **FROM** latency **TO** decide **WHEN** ENABLE_RESOLVER_CACHE, or **TO** done **WHEN** SESSION_ABANDONED - `inst-latency`

## 5. Definitions of Done

### Reproducible sessions

- [x] `p1` - **ID**: `cpt-nextgear-dod-simulator-sessions`

The same configuration and seed **MUST** produce identical sessions, every session **MUST** replay through the state machine to a terminal event, and the generator **MUST NOT** import any predictor or evaluation code.

**Implements**:
- `cpt-nextgear-algo-simulator-local-check`
- `cpt-nextgear-algo-simulator-system-check`
- `cpt-nextgear-algo-simulator-next-event`
- `cpt-nextgear-algo-simulator-generate`
- `cpt-nextgear-state-simulator-session`

**Constraints**: `cpt-nextgear-constraint-cpu-only`

**Touches**:
- Files: `data/*.jsonl`
- Entities: `Session`, `Hidden`, `State`

## 6. Acceptance Criteria

- [x] The published gears order is accepted step by step, bypass and order violations are rejected, and platform gears are accepted once anywhere.
- [x] System checks fail in the documented order, the outbound gateway's declared dependency on the Credentials Store is enforced, and the cache halves only resolver latency.
- [x] The extracted dependencies match the gears-rust declarations at the pinned commit, and the Rust registry harness uses the same commit.
- [x] Regenerating with the same seed gives identical sessions; truncated traces are rejected on load.
- [x] There are 384 hidden parameter sets and their prior probabilities sum to one.
