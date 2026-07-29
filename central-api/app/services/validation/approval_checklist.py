"""Group C — Approval checklist field checks."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    approval = spec_data.get("approval_checklist", {})
    cl = approval.get("content", {})

    # C-01: prerequisites_verifiable
    pv = cl.get("prerequisites_verifiable")
    if pv is None:
        results.append(CheckResult(
            check_id="C-01", group="C", status=CheckStatus.FAIL,
            message="prerequisites_verifiable must be true or false (Phase 6)",
            field="approval_checklist.content.prerequisites_verifiable",
        ))
    else:
        results.append(CheckResult(
            check_id="C-01", group="C", status=CheckStatus.PASS,
            message=f"prerequisites_verifiable = {pv}",
            field="approval_checklist.content.prerequisites_verifiable",
        ))

    # C-02: assessment_strategy (optional for classic labs)
    strategy = cl.get("assessment_strategy", "")
    results.append(CheckResult(
        check_id="C-02", group="C",
        status=CheckStatus.PASS if strategy else CheckStatus.SKIP,
        message="assessment_strategy is optional for classic labs and demos" if not strategy else f"assessment_strategy set ({len(strategy)} chars)",
        field="approval_checklist.content.assessment_strategy",
    ))

    # C-03: differentiation (Phase 3 RCARS)
    diff = cl.get("differentiation", "")
    if not diff:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.FAIL,
            message="differentiation must be non-empty (Phase 3)",
            field="approval_checklist.content.differentiation",
        ))
    else:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.PASS,
            message=f"Differentiation set ({len(diff)} chars)",
            field="approval_checklist.content.differentiation",
        ))

    # C-04: all rejection reasons must be resolved before resubmitting
    content_rejections = cl.get("rejections", [])
    infra_rejections = approval.get("infra", {}).get("rejections", [])
    all_rejections = (content_rejections or []) + (infra_rejections or [])
    unresolved = [r for r in all_rejections if not r.get("resolved", True)]
    if unresolved:
        results.append(CheckResult(
            check_id="C-04", group="C", status=CheckStatus.FAIL,
            message=f"{len(unresolved)} unresolved rejection reason(s) — address all feedback before resubmitting",
            field="approval_checklist.rejections",
        ))
    elif all_rejections:
        results.append(CheckResult(
            check_id="C-04", group="C", status=CheckStatus.PASS,
            message=f"All {len(all_rejections)} rejection reason(s) resolved",
            field="approval_checklist.rejections",
        ))

    return results
