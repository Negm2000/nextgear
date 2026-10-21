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

A gain over n-grams is hard to interpret on its own. It does not say how much of the remaining loss a better model could remove, and how much comes from hidden values that no predictor can see.

## Decision Drivers

- A known, finite hidden space
- A reference that measures unavoidable uncertainty
- Clear semantics for a forced one-step action

## Considered Options

- Enumerated Bayes filter
- Privileged true-state predictor
- Simulation-only reference

## Decision Outcome

Chosen option: "Enumerated Bayes filter". The 384 hypotheses are few enough to update exactly, and the observation likelihoods and posterior mixture define the reference without approximation.

### Consequences

The oracle minimises expected log loss only when its assumptions match the data. In the excluded-group test it keeps the base prior and serves as a common reference. Because it shares code with the generator, it is not independent validation.

### Confirmation

Tests check that posteriors and predictions are normalised, that parallel and serial prediction agree, that prefix queries match a full pass, and how a forced action changes beliefs.

## Pros and Cons of the Options

### Enumerated Bayes filter

Exact when the priors and equations match, but it shares the generator's implementation and may be slower.


### Privileged true-state predictor

Easy to compute, but it sees the hidden values, so the comparison would be unfair.


### Simulation-only reference

Flexible, but adds sampling error and runtime for a model this small.

## More Information

[Recorded results](../../results/REPORT.md). This record summarises the rationale for the reviewed design. It does not show that the choice was made before results were seen, or that it was preregistered.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-oracle`, `cpt-nextgear-fr-what-if`.
