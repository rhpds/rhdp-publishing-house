"""Group C — Approval checklist field checks (Q22-Q24)."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    approval = spec_data.get("approval_checklist", {})
    cl = approval.get("content_lead", {})

    # C-01: Q22 — prerequisites_verifiable
    prereq = cl.get("prerequisites_verifiable")
    if prereq is None:
        results.append(CheckResult(
            check_id="C-01", group="C", status=CheckStatus.FAIL,
            message="Q22: prerequisites_verifiable must be true or false",
            field="approval_checklist.content_lead.prerequisites_verifiable",
        ))
    else:
        results.append(CheckResult(
            check_id="C-01", group="C", status=CheckStatus.PASS,
            message=f"Prerequisites verifiable: {prereq}",
            field="approval_checklist.content_lead.prerequisites_verifiable",
        ))

    # C-02: Q23 — assessment_strategy
    assessment = cl.get("assessment_strategy", "")
    if not assessment:
        results.append(CheckResult(
            check_id="C-02", group="C", status=CheckStatus.FAIL,
            message="Q23: assessment_strategy must be non-empty",
            field="approval_checklist.content_lead.assessment_strategy",
        ))
    else:
        results.append(CheckResult(
            check_id="C-02", group="C", status=CheckStatus.PASS,
            message=f"Assessment strategy set ({len(assessment)} chars)",
            field="approval_checklist.content_lead.assessment_strategy",
        ))

    # C-03: Q24 — differentiation
    diff = cl.get("differentiation", "")
    if not diff:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.FAIL,
            message="Q24: differentiation must be non-empty",
            field="approval_checklist.content_lead.differentiation",
        ))
    else:
        results.append(CheckResult(
            check_id="C-03", group="C", status=CheckStatus.PASS,
            message=f"Differentiation set ({len(diff)} chars)",
            field="approval_checklist.content_lead.differentiation",
        ))

    return results
