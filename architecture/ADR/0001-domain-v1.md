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

The assignment allows any discrete event sequence. A useful one needs a history that matters for prediction, decisions made under uncertainty, deterministic checks and ground truth that can be inspected.

## Decision Drivers

- Relevance to architecture modelling
- Repair history that a predictor can observe
- A small, controlled experiment

## Considered Options

- Gear assembly simulator
- Generic event stream

## Decision Outcome

Chosen option: "Gear assembly simulator". Accepted gears, rejected proposals and rollbacks give a predictor something it has to remember, while every event and check stays easy to inspect.

### Consequences

The data are synthetic, so a model can be rewarded for exploiting regularities of the authored rules. No real Fabric checker or deployment runs.

### Confirmation

Tests cover rule examples, deterministic seeded generation and replay of complete sessions. FABRIC_USAGE.md separates the public motivation from the authored assumptions.

## Pros and Cons of the Options

### Gear assembly simulator

Connects requirements, proposals and admissibility, but every stochastic and latency assumption has to be declared.


### Generic event stream

Smaller, but with less connection to the role and no meaningful composition state.

## More Information

[Recorded results](../../results/REPORT.md). This record summarises the rationale for the reviewed design. It does not show that the choice was made before results were seen, or that it was preregistered.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-event-vocabulary`, `cpt-nextgear-fr-session-generator`, `cpt-nextgear-fr-checks`.
