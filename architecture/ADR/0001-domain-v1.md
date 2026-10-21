---
version: 2.0
status: accepted
date: 2026-10-21
description: Use gear assembly sessions
---

# Use gear assembly sessions

<!-- toc -->

- [Context and Problem Statement](#context-and-problem-statement)
- [Decision Drivers](#decision-drivers)
- [Considered Options](#considered-options)
- [Decision Outcome](#decision-outcome)
  - [Consequences](#consequences)
  - [Confirmation](#confirmation)
- [Pros and Cons of the Options](#pros-and-cons-of-the-options)
  - [Gear assembly simulator](#gear-assembly-simulator)
  - [Generic event stream](#generic-event-stream)
- [More Information](#more-information)
- [Traceability](#traceability)

<!-- /toc -->

**ID**: `cpt-nextgear-adr-domain`

## Context and Problem Statement

The assignment permits any discrete sequence. We need meaningful history, uncertain decisions, deterministic checks and inspectable ground truth.

## Decision Drivers

- Relevance to architecture modelling
- Observable repair history
- Small controlled experiment

## Considered Options

- Gear assembly simulator
- Generic event stream

## Decision Outcome

Chosen option: "Gear assembly simulator". Its accepted gears, rejected proposals and rollbacks create memory requirements while keeping events and checks inspectable.

### Consequences

The data are synthetic and can reward authored shortcuts. No real Fabric checker or deployment is executed.

### Confirmation

Rule examples, deterministic seeded generation and complete-session replay tests. Public motivation and authored assumptions are separated in FABRIC_USAGE.md.

## Pros and Cons of the Options

### Gear assembly simulator

Links requirements, proposals and admissibility; all stochastic and latency assumptions must be declared.


### Generic event stream

Smaller, but offers less connection to the role or meaningful composition state.

## More Information

[Recorded results](../../results/REPORT.md). This is a concise record of the reviewed design rationale, not evidence of an untouched or preregistered selection process.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-event-vocabulary`, `cpt-nextgear-fr-session-generator`, `cpt-nextgear-fr-checks`.
