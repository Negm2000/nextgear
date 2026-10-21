---
version: 2.0
status: accepted
date: 2026-10-21
description: Keep an exact Bayesian reference
---

# Keep an exact Bayesian reference

<!-- toc -->

- [Context and Problem Statement](#context-and-problem-statement)
- [Decision Drivers](#decision-drivers)
- [Considered Options](#considered-options)
- [Decision Outcome](#decision-outcome)
  - [Consequences](#consequences)
  - [Confirmation](#confirmation)
- [Pros and Cons of the Options](#pros-and-cons-of-the-options)
  - [Enumerated Bayes filter](#enumerated-bayes-filter)
  - [Privileged true-state predictor](#privileged-true-state-predictor)
  - [Simulation-only reference](#simulation-only-reference)
- [More Information](#more-information)
- [Traceability](#traceability)

<!-- /toc -->

**ID**: `cpt-nextgear-adr-bayes-oracle`

## Context and Problem Statement

A gain over n-grams is hard to interpret without separating avoidable model error from hidden-state uncertainty.

## Decision Drivers

- Known finite hidden space
- Honest uncertainty reference
- One-step intervention semantics

## Considered Options

- Enumerated Bayes filter
- Privileged true-state predictor
- Simulation-only reference

## Decision Outcome

Chosen option: "Enumerated Bayes filter". 384 hypotheses are small enough to update exactly; observation likelihoods and posterior mixtures define the reference clearly.

### Consequences

Optimality is in expected log loss under matching assumptions. The selected-group test retains the base prior as a common reference. Shared code is not independent validation.

### Confirmation

Normalized posterior/prediction tests, serial/parallel equivalence, prefix/full-pass agreement and forced-action tests.

## Pros and Cons of the Options

### Enumerated Bayes filter

Exact under matching priors and equations, but shares generator implementation and may be slower.


### Privileged true-state predictor

Easy to compute, but changes the information available and gives an unfair comparison.


### Simulation-only reference

Flexible, but adds sampling error and runtime for this finite model.

## More Information

[Recorded results](../../results/REPORT.md). This is a concise record of the reviewed design rationale, not evidence of an untouched or preregistered selection process.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-oracle`, `cpt-nextgear-fr-what-if`.
