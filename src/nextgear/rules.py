"""The checks that accept or reject an assembly.

Three rules follow the public gears-rust docs (docs/GEARS.md at commit 60db50e):
the fixed request order "API Gateway -> Auth Resolver -> Policy Manager -> License
Resolver -> Execution Gear -> Tenant Resolver -> Audit / Usage Collector" (line 63),
"bypassing middlewares is not permitted" (line 49), and "only integration/adapters talk
to external components" (line 52). The completeness, cost and latency rules, and all
numbers below, are this project's own assumptions.
"""

from dataclasses import dataclass

ORDER: dict[str, int] = {
    "API_GATEWAY": 0, "AUTH_RESOLVER": 1, "POLICY_MANAGER": 2, "LICENSE_RESOLVER": 3,
    "CHAT_ENGINE": 4, "BILLING_LEDGER": 4, "SERVERLESS_RUNTIME": 4,
    "TENANT_RESOLVER": 5, "USAGE_COLLECTOR": 6,
}
EXECUTION_GEARS: frozenset[str] = frozenset({"CHAT_ENGINE", "BILLING_LEDGER", "SERVERLESS_RUNTIME"})
CALLS_EXTERNAL: frozenset[str] = frozenset({"CHAT_ENGINE", "SERVERLESS_RUNTIME"})
OUTBOUND = "OUTBOUND_API_GATEWAY"

LATENCY_MS: dict[str, float] = {
    "API_GATEWAY": 3, "AUTH_RESOLVER": 8, "POLICY_MANAGER": 6, "LICENSE_RESOLVER": 5,
    "CHAT_ENGINE": 40, "BILLING_LEDGER": 15, "SERVERLESS_RUNTIME": 25,
    "TENANT_RESOLVER": 4, "USAGE_COLLECTOR": 3, OUTBOUND: 10,
}
CACHED_GEARS: frozenset[str] = frozenset({"AUTH_RESOLVER", "POLICY_MANAGER", "LICENSE_RESOLVER", "TENANT_RESOLVER"})
BUDGET_MS: dict[str, float] = {"tight": 60.0, "loose": 120.0}


@dataclass(frozen=True)
class Spec:
    """What the application must provide. Only the oracle and the checks may read it."""

    execution: str
    policy: bool
    license: bool
    tenant: bool
    usage: bool
    budget: str

    def required_path(self) -> tuple[str, ...]:
        gears = ["API_GATEWAY", "AUTH_RESOLVER"]
        gears += ["POLICY_MANAGER"] * self.policy + ["LICENSE_RESOLVER"] * self.license
        gears += [self.execution] + ["TENANT_RESOLVER"] * self.tenant + ["USAGE_COLLECTOR"] * self.usage
        return tuple(gears)

    def needs_outbound(self) -> bool:
        return self.execution in CALLS_EXTERNAL


# @cpt-algo:cpt-nextgear-algo-simulator-local-check:p1
def local_verdict(path: tuple[str, ...], outbound: bool, gear: str) -> str:
    """Check one proposed gear against the current request path."""
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-outbound
    if gear == OUTBOUND:
        return "ORDER_VIOLATION" if outbound else "STEP_ACCEPTED"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-outbound
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-bypass
    if gear in EXECUTION_GEARS and "AUTH_RESOLVER" not in path:
        return "BYPASS_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-bypass
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-order
    if not path:
        return "STEP_ACCEPTED" if gear == "API_GATEWAY" else "ORDER_VIOLATION"
    return "STEP_ACCEPTED" if ORDER[gear] > ORDER[path[-1]] else "ORDER_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-order


def latency_ms(path: tuple[str, ...], outbound: bool, cache: bool) -> float:
    total = sum(LATENCY_MS[g] * (0.5 if cache and g in CACHED_GEARS else 1.0) for g in path)
    return total + (LATENCY_MS[OUTBOUND] if outbound else 0.0)


# @cpt-algo:cpt-nextgear-algo-simulator-system-check:p1
def system_verdict(spec: Spec, path: tuple[str, ...], outbound: bool, cache: bool) -> str:
    """Check a submitted assembly against the specification, first failure wins."""
    required = spec.required_path()
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-complete
    if any(g not in path for g in required):
        return "MISSING_CAPABILITY"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-complete
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-external
    if spec.needs_outbound() and not outbound:
        return "EXTERNAL_CALL_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-external
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-cost
    if any(g not in required for g in path) or (outbound and not spec.needs_outbound()):
        return "COST_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-cost
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-latency
    if latency_ms(path, outbound, cache) > BUDGET_MS[spec.budget]:
        return "LATENCY_VIOLATION"
    return "ASSEMBLY_ADMISSIBLE"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-latency
