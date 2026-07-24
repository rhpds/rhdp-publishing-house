"""Group C — Approval checklist field checks."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    approval = spec_data.get("approval_checklist", {})
    cl = approval.get("content", {})

    # C-03: Q24 — differentiation
    diff = cl.get("differentiation", "")
    if not diff:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.FAIL,
            message="Q24: differentiation must be non-empty",
            field="approval_checklist.content.differentiation",
        ))
    else:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.PASS,
            message=f"Differentiation set ({len(diff)} chars)",
            field="approval_checklist.content.differentiation",
        ))

    return results
