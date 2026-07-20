"""Group I — Auto-computed fields (informational, not pass/fail)."""
from .models import CheckResult, CheckStatus, AutoComputedFields


def run_checks(spec_data: dict, policy: dict) -> tuple[list[CheckResult], AutoComputedFields]:
    results = []
    env = spec_data.get("spec", {}).get("environment", {})
    auto = AutoComputedFields()

    topology = env.get("topology", "")
    max_users = env.get("max_concurrent_users")
    prov_estimates = policy.get("provisioning_time_estimates", {})
    cost_rate = policy.get("cost_hourly_rate_per_vcpu", 0.05)

    # I-01: Peak environments
    if topology and max_users and isinstance(max_users, (int, float)):
        factor = {"shared-cluster": 1, "per-student": int(max_users), "cnv-pool": int(max_users)}
        peak = factor.get(topology, 1)
        auto.peak_environments = peak
        results.append(CheckResult(
            check_id="I-01", group="I", status=CheckStatus.PASS,
            message=f"Peak environments: {peak} (topology={topology}, users={max_users})",
            field="auto_computed.peak_environments",
        ))
    else:
        results.append(CheckResult(
            check_id="I-01", group="I", status=CheckStatus.SKIP,
            message="Cannot compute peak environments — topology or max_users not set",
            field="auto_computed.peak_environments",
        ))

    # I-02: Provisioning time estimate
    if topology and topology in prov_estimates:
        auto.provisioning_time_min = prov_estimates[topology]
        results.append(CheckResult(
            check_id="I-02", group="I", status=CheckStatus.PASS,
            message=f"Provisioning time estimate: ~{auto.provisioning_time_min} min",
            field="auto_computed.provisioning_time_min",
        ))
    else:
        results.append(CheckResult(
            check_id="I-02", group="I", status=CheckStatus.SKIP,
            message="Cannot estimate provisioning time — topology not set or unknown",
            field="auto_computed.provisioning_time_min",
        ))

    # I-03: Cost per run estimate
    worker_count = env.get("worker_count")
    worker_cpu = env.get("worker_cpu")
    modules = spec_data.get("spec", {}).get("modules", [])

    if worker_count and worker_cpu and modules:
        total_vcpu = int(worker_count) * int(worker_cpu)
        # Rough duration from module count (assume 20min avg per module)
        total_hours = (len(modules) * 20) / 60
        auto.cost_per_run_est = round(total_vcpu * cost_rate * total_hours, 2)
        results.append(CheckResult(
            check_id="I-03", group="I", status=CheckStatus.PASS,
            message=f"Cost estimate: ~${auto.cost_per_run_est}/run "
                    f"({total_vcpu} vCPU × {total_hours:.1f}h × ${cost_rate}/vCPU·h)",
            field="auto_computed.cost_per_run_est",
        ))
    else:
        results.append(CheckResult(
            check_id="I-03", group="I", status=CheckStatus.SKIP,
            message="Cannot estimate cost — sizing or modules not set",
            field="auto_computed.cost_per_run_est",
        ))

    return results, auto
