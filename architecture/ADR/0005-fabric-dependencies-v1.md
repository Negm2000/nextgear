---
version: 1.0
status: accepted
date: 2026-10-21
description: Take gear dependencies from gears-rust
---

# Take gear dependencies from gears-rust

<!-- toc -->

- [Context and Problem Statement](#context-and-problem-statement)
- [Decision Drivers](#decision-drivers)
- [Considered Options](#considered-options)
- [Decision Outcome](#decision-outcome)
  - [Consequences](#consequences)
  - [Confirmation](#confirmation)
- [Pros and Cons of the Options](#pros-and-cons-of-the-options)
  - [Declared dependencies from gears-rust](#declared-dependencies-from-gears-rust)
  - [Hand-written composition rules](#hand-written-composition-rules)
  - [Run the Rust registry inside the generator](#run-the-rust-registry-inside-the-generator)
- [More Information](#more-information)
- [Traceability](#traceability)

<!-- /toc -->

**ID**: `cpt-nextgear-adr-fabric-dependencies`

## Context and Problem Statement

The first version of the simulator took its gear names and request order from Fabric's documentation, but every rule about what an assembly needs was written for this project. In constructorfabric/gears-rust, each gear declares the gears it depends on in its `#[toolkit::gear(deps = [...])]` attribute, and the toolkit's registry refuses to build an application in which one of those dependencies is absent. The question was whether the simulator should use those declarations instead.

## Decision Drivers

- Composition structure that comes from Fabric rather than from this project
- A rule that can be checked against the real implementation
- No Rust toolchain needed to run the experiment

## Considered Options

- Declared dependencies from gears-rust
- Hand-written composition rules
- Run the Rust registry inside the generator

## Decision Outcome

Chosen option: "Declared dependencies from gears-rust". `tools/extract_gears.py` reads the declarations of the simulated gears and everything they depend on at a pinned commit, and writes them to `fabric_gears.py`. Six platform gears that the declarations require join the vocabulary. A new system verdict, MISSING_DEPENDENCY, mirrors the registry's `UnknownDependency` error.

### Consequences

The dependency graph is Fabric's own: the outbound gateway needs the Credentials Store, the Billing Ledger needs the Account Manager and, through it, the Resource Group, and every valid assembly needs the Tenant Resolver, so it is no longer a separate requirement. Sessions are about twice as long, so the proposal and submission budgets were raised. Serverless Runtime has no gear declaration at the pinned commit and therefore no dependencies. The request order, the check precedence, the agent's policy and all probabilities and latencies remain this project's assumptions.

### Confirmation

`tools/crosscheck_registry.py` sends 24,910 assemblies to a small Rust program that registers them with the real `RegistryBuilder` and calls `build_topo_sorted`. They are the 4,910 assemblies submitted in 2,000 simulated sessions, 1,544 of which have a missing dependency, and 20,000 random subsets of the sixteen gears. The registry and Nextgear's check agree on all of them. Unit tests pin individual declarations and check that the harness and the extracted table use the same commit.

## Pros and Cons of the Options

### Declared dependencies from gears-rust

Real composition structure that can be re-extracted when the repository changes, at the cost of a larger vocabulary and longer sessions.


### Hand-written composition rules

Smaller and easier to explain, but every rule is the author's guess about the platform.


### Run the Rust registry inside the generator

The most faithful, but every user and CI run would need a Rust toolchain and a large build. A one-off cross-check gives the same assurance for this rule.

## More Information

[Recorded results](../../results/REPORT.md). This record summarises the rationale for the reviewed design. It does not show that the choice was made before results were seen, or that it was preregistered.

## Traceability

[PRD](../PRD.md) · [Design](../DESIGN.md).

`cpt-nextgear-fr-checks`, `cpt-nextgear-fr-session-generator`.
