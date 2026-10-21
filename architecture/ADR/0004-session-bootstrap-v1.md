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

Events within one session depend on each other, and every model forecasts the same events. Resampling events independently would overstate precision.

## Decision Drivers

- Preserve within-session dependence
- Paired comparison
- Event-weighted estimand

## Considered Options

- Paired session bootstrap
- Event-wise bootstrap
- Accuracy-only summary

## Decision Outcome

Chosen option: "Paired session bootstrap". It resamples complete sessions and divides the summed loss difference by the summed event count, which matches the per-event comparison the report states.

### Consequences

Percentile intervals do not capture simulator error, all training randomness or the uncertainty of model selection. The analyses are exploratory and not corrected for multiple comparisons.

### Confirmation

Tests check that identical scores give a zero difference, that a clearly better model gets a negative one, and that both score sets cover the same events. All three training seeds are reported; the holdout model has one.

## Pros and Cons of the Options

### Paired session bootstrap

Keeps the dependence within sessions and the pairing between models; conditional on the fitted models and the generator.


### Event-wise bootstrap

Cheap, but treats correlated events as independent.


### Accuracy-only summary

Simple, but discards probability quality and uncertainty.

## More Information

[Recorded results](../../results/REPORT.md). This record summarises the rationale for the reviewed design. It does not show that the choice was made before results were seen, or that it was preregistered.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-statistics`, `cpt-nextgear-fr-benchmark`.
