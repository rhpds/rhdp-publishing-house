"""Group G — Automation manifest check."""
from .models import CheckResult, CheckStatus


def run_checks(manifest_text: str | None, policy: dict) -> list[CheckResult]:
    results = []

    if manifest_text is None:
        results.append(CheckResult(
            check_id="G-01", group="G", status=CheckStatus.FAIL,
            message="automation-manifest.yaml not found",
            field="publishing-house/spec/automation-manifest.yaml",
        ))
    elif not manifest_text.strip() or manifest_text.strip() == "---":
        results.append(CheckResult(
            check_id="G-01", group="G", status=CheckStatus.FAIL,
            message="automation-manifest.yaml is empty or blank template",
            field="publishing-house/spec/automation-manifest.yaml",
        ))
    else:
        results.append(CheckResult(
            check_id="G-01", group="G", status=CheckStatus.PASS,
            message="automation-manifest.yaml exists and has content",
            field="publishing-house/spec/automation-manifest.yaml",
        ))

    return results
