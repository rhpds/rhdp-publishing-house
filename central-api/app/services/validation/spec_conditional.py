"""Group B — Conditional spec.yaml field checks."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    project = spec_data.get("project", {})
    spec = spec_data.get("spec", {})
    env = spec.get("environment", {})
    searchable_fields = [
        str(spec.get("title", "")),
        str(spec.get("learning_objectives", "")),
        " ".join(str(m.get("title", "")) for m in spec.get("modules", [])),
        str(project.get("content_type", "")),
    ]
    all_text = " ".join(searchable_fields).lower()

    ai_keywords = policy.get("ai_keywords", [])
    vague_egress = policy.get("vague_egress_terms", [])

    # B-01: Sizing consistency — if worker_count > 0, cpu/ram/disk must be set
    worker_count = env.get("worker_count")
    sizing_detail = ["worker_cpu", "worker_ram_gb", "worker_disk_gb"]
    detail_values = {f: env.get(f) for f in sizing_detail}
    details_set = all(v is not None and v != "" for v in detail_values.values())

    if worker_count is not None and int(worker_count) > 0 and not details_set:
        missing = [f for f, v in detail_values.items() if v is None or v == ""]
        results.append(CheckResult(
            check_id="B-01", group="B", status=CheckStatus.FAIL,
            message=f"worker_count={worker_count} but missing: {', '.join(missing)}",
            field="spec.environment.worker_*",
        ))
    else:
        results.append(CheckResult(
            check_id="B-01", group="B", status=CheckStatus.PASS,
            message="Sizing fields consistent",
            field="spec.environment.worker_*",
        ))

    # B-02: Concurrent users required for per-student / cnv-pool
    topology = env.get("topology", "")
    if topology in ("per-student", "cnv-pool"):
        max_users = env.get("max_concurrent_users")
        if max_users is None or max_users == "":
            results.append(CheckResult(
                check_id="B-02", group="B", status=CheckStatus.FAIL,
                message=f"topology={topology} requires max_concurrent_users",
                field="spec.environment.max_concurrent_users",
            ))
        elif isinstance(max_users, (int, float)) and max_users > 0:
            results.append(CheckResult(
                check_id="B-02", group="B", status=CheckStatus.PASS,
                message=f"Max concurrent users: {max_users}",
                field="spec.environment.max_concurrent_users",
            ))
        else:
            results.append(CheckResult(
                check_id="B-02", group="B", status=CheckStatus.FAIL,
                message="max_concurrent_users must be a positive number",
                field="spec.environment.max_concurrent_users",
            ))
    else:
        results.append(CheckResult(
            check_id="B-02", group="B", status=CheckStatus.SKIP,
            message=f"topology={topology or 'not set'} — concurrent users not required",
            field="spec.environment.max_concurrent_users",
        ))

    # B-03: AI/MaaS — if AI keyword detected, ai_requirement must be set
    ai_req = env.get("ai_requirement", "")
    ai_tier = env.get("ai_model_tier", "")
    ai_justification = env.get("ai_justification", "")
    ai_mentioned = any(kw in all_text for kw in ai_keywords)

    if ai_mentioned and not ai_req:
        results.append(CheckResult(
            check_id="B-03", group="B", status=CheckStatus.FAIL,
            message="AI/LLM keyword detected but spec.environment.ai_requirement not set (maas/gpu/none)",
            field="spec.environment.ai_requirement",
        ))
    elif ai_req == "gpu" and not ai_justification:
        results.append(CheckResult(
            check_id="B-03", group="B", status=CheckStatus.FAIL,
            message="ai_requirement=gpu requires ai_justification",
            field="spec.environment.ai_justification",
        ))
    elif ai_tier == "frontier" and not ai_justification:
        results.append(CheckResult(
            check_id="B-03", group="B", status=CheckStatus.FAIL,
            message="ai_model_tier=frontier requires ai_justification",
            field="spec.environment.ai_justification",
        ))
    else:
        results.append(CheckResult(
            check_id="B-03", group="B",
            status=CheckStatus.PASS if ai_req else CheckStatus.SKIP,
            message=f"AI: {ai_req or 'not detected'}",
            field="spec.environment.ai_requirement",
        ))

    # B-04: AAP version required if AAP in products
    if "ansible automation platform" in all_text or " aap " in all_text or "aap2." in all_text:
        aap_version = env.get("aap_version", "")
        if not aap_version:
            results.append(CheckResult(
                check_id="B-04", group="B", status=CheckStatus.FAIL,
                message="AAP detected in spec but aap_version not set",
                field="spec.environment.aap_version",
            ))
        else:
            results.append(CheckResult(
                check_id="B-04", group="B", status=CheckStatus.PASS,
                message=f"AAP version: {aap_version}",
                field="spec.environment.aap_version",
            ))
    else:
        results.append(CheckResult(
            check_id="B-04", group="B", status=CheckStatus.SKIP,
            message="AAP not in products",
            field="spec.environment.aap_version",
        ))

    # B-05: External services — no vague entries
    external_services = env.get("external_services", [])
    if external_services:
        vague = [s for s in external_services
                 if any(v in str(s).lower() for v in vague_egress)]
        if vague:
            results.append(CheckResult(
                check_id="B-05", group="B", status=CheckStatus.FAIL,
                message=f"Vague external service entries: {vague}. Use specific names.",
                field="spec.environment.external_services",
            ))
        else:
            results.append(CheckResult(
                check_id="B-05", group="B", status=CheckStatus.PASS,
                message=f"{len(external_services)} named external service(s)",
                field="spec.environment.external_services",
            ))
    else:
        results.append(CheckResult(
            check_id="B-05", group="B", status=CheckStatus.PASS,
            message="No external services — auto-approved",
            field="spec.environment.external_services",
        ))

    # B-06: Non-GA products + access plan
    non_ga = env.get("non_ga_products", [])
    non_ga_plan = env.get("non_ga_access_plan", "")
    if non_ga:
        if not non_ga_plan:
            results.append(CheckResult(
                check_id="B-06", group="B", status=CheckStatus.FAIL,
                message=f"Non-GA products listed but no access plan: {non_ga}",
                field="spec.environment.non_ga_access_plan",
            ))
        else:
            results.append(CheckResult(
                check_id="B-06", group="B", status=CheckStatus.WARN,
                message=f"Non-GA products present ({len(non_ga)}) — routes to infra review",
                field="spec.environment.non_ga_products",
            ))
    else:
        results.append(CheckResult(
            check_id="B-06", group="B", status=CheckStatus.PASS,
            message="No non-GA products — auto-approved",
            field="spec.environment.non_ga_products",
        ))

    # B-07: Content type must be from controlled vocabulary
    content_type = project.get("content_type", "")
    valid_types = policy.get("valid_content_types", [])
    if content_type and valid_types:
        if content_type.lower() not in [t.lower() for t in valid_types]:
            results.append(CheckResult(
                check_id="B-07", group="B", status=CheckStatus.FAIL,
                message=f"content_type '{content_type}' not in allowed list: {valid_types}",
                field="spec.content_type",
            ))
        else:
            results.append(CheckResult(
                check_id="B-07", group="B", status=CheckStatus.PASS,
                message=f"content_type '{content_type}' is valid",
                field="spec.content_type",
            ))
    else:
        results.append(CheckResult(
            check_id="B-07", group="B", status=CheckStatus.SKIP,
            message="Content type not set or no policy",
            field="spec.content_type",
        ))

    return results
