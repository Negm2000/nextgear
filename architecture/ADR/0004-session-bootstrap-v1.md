---
version: 2.0
status: accepted
date: 2026-10-21
description: Bootstrap paired sessions
---

# Bootstrap paired sessions

<!-- toc -->

- [Context and Problem Statement](#context-and-problem-statement)
- [Decision Drivers](#decision-drivers)
- [Considered Options](#considered-options)
- [Decision Outcome](#decision-outcome)
  - [Consequences](#consequences)
  - [Confirmation](#confirmation)
- [Pros and Cons of the Options](#pros-and-cons-of-the-options)
  - [Paired session bootstrap](#paired-session-bootstrap)
  - [Event-wise bootstrap](#event-wise-bootstrap)
  - [Accuracy-only summary](#accuracy-only-summary)
- [More Information](#more-information)
- [Traceability](#traceability)

<!-- /toc -->

**ID**: `cpt-nextgear-adr-session-bootstrap`

## Context and Problem Statement

Events within one session are dependent and models forecast the same events. Event-wise independent resampling would overstate precision.

## Decision Drivers

- Preserve within-session dependence
- Paired comparison
- Event-weighted estimand

## Considered Options

- Paired session bootstrap
- Event-wise bootstrap
- Accuracy-only summary

## Decision Outcome

Chosen option: "Paired session bootstrap". Resampling complete sessions and dividing summed loss difference by summed event count matches the intended per-event comparison.

### Consequences

Percentile intervals do not capture simulator error, all training randomness or model-selection uncertainty. Analyses are exploratory and lack multiplicity correction.

### Confirmation

Identity and known-sign tests, same-event checks and explicit three-seed reporting. The holdout model has one training seed.

## Pros and Cons of the Options

### Paired session bootstrap

Preserves sequence dependence and comparison pairing; conditional on fitted models and generator.


### Event-wise bootstrap

Cheap, but treats correlated events as independent.


### Accuracy-only summary

Simple, but discards probability quality and uncertainty.

## More Information

[Recorded results](../../results/REPORT.md). This is a concise record of the reviewed design rationale, not evidence of an untouched or preregistered selection process.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-statistics`, `cpt-nextgear-fr-benchmark`.
