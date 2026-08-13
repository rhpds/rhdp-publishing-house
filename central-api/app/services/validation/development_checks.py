"""Group J — Development-stage checks (module completion and content file coverage)."""
import os
import re

from .models import CheckResult, CheckStatus

_PLACEHOLDER_PATTERNS = re.compile(
    r'\bTODO\b|\bFIXME\b|\bTBD\b|\[placeholder\]',
    re.IGNORECASE,
)


def run_checks(
    spec_data: dict,
    outline_files: dict[str, str],
    page_files: list[str],
    has_nav: bool = False,
    page_contents: dict[str, str] | None = None,
) -> list[CheckResult]:
    results = []
    modules = spec_data.get("spec", {}).get("modules", [])

    # J-01: All modules must have status "complete"
    if not modules:
        results.append(CheckResult(
            check_id="J-01", group="J", status=CheckStatus.SKIP,
            message="No modules in spec.yaml",
            field="spec.modules",
        ))
    else:
        incomplete = []
        for i, mod in enumerate(modules):
            status = mod.get("status", "")
            if status != "complete":
                title = mod.get("title", f"module {i + 1}")
                incomplete.append(f"{title} ({status or 'no status'})")
        if incomplete:
            results.append(CheckResult(
                check_id="J-01", group="J", status=CheckStatus.FAIL,
                message=f"Modules not complete: {', '.join(incomplete[:5])}",
                field="spec.modules[*].status",
            ))
        else:
            results.append(CheckResult(
                check_id="J-01", group="J", status=CheckStatus.PASS,
                message=f"All {len(modules)} modules have status complete",
                field="spec.modules[*].status",
            ))

    # J-02: Every spec/modules file has a corresponding .adoc page
    if not outline_files:
        results.append(CheckResult(
            check_id="J-02", group="J", status=CheckStatus.SKIP,
            message="No module outline files to check",
            field="publishing-house/spec/modules/",
        ))
    else:
        page_stems = {os.path.splitext(f)[0] for f in page_files if f.endswith(".adoc")}
        missing = []
        for fname in sorted(outline_files.keys()):
            stem = os.path.splitext(fname)[0]
            if stem not in page_stems:
                missing.append(f"{stem}.adoc")
        if missing:
            results.append(CheckResult(
                check_id="J-02", group="J", status=CheckStatus.FAIL,
                message=f"No matching page for: {', '.join(missing[:5])}",
                field="content/modules/ROOT/pages/",
            ))
        else:
            results.append(CheckResult(
                check_id="J-02", group="J", status=CheckStatus.PASS,
                message=f"All {len(outline_files)} module outlines have matching pages",
                field="content/modules/ROOT/pages/",
            ))

    # J-03: index.adoc must exist
    if "index.adoc" in page_files:
        results.append(CheckResult(
            check_id="J-03", group="J", status=CheckStatus.PASS,
            message="index.adoc exists",
            field="content/modules/ROOT/pages/index.adoc",
        ))
    else:
        results.append(CheckResult(
            check_id="J-03", group="J", status=CheckStatus.FAIL,
            message="index.adoc not found in content/modules/ROOT/pages/",
            field="content/modules/ROOT/pages/index.adoc",
        ))

    # J-04: conclusion.adoc must exist
    if "conclusion.adoc" in page_files:
        results.append(CheckResult(
            check_id="J-04", group="J", status=CheckStatus.PASS,
            message="conclusion.adoc exists",
            field="content/modules/ROOT/pages/conclusion.adoc",
        ))
    else:
        results.append(CheckResult(
            check_id="J-04", group="J", status=CheckStatus.FAIL,
            message="conclusion.adoc not found in content/modules/ROOT/pages/",
            field="content/modules/ROOT/pages/conclusion.adoc",
        ))

    # J-05: nav.adoc must exist
    if has_nav:
        results.append(CheckResult(
            check_id="J-05", group="J", status=CheckStatus.PASS,
            message="nav.adoc exists",
            field="content/modules/ROOT/nav.adoc",
        ))
    else:
        results.append(CheckResult(
            check_id="J-05", group="J", status=CheckStatus.FAIL,
            message="nav.adoc not found in content/modules/ROOT/",
            field="content/modules/ROOT/nav.adoc",
        ))

    # J-06: No placeholder text in .adoc pages
    if page_contents:
        files_with_placeholders = []
        for fname, content in sorted(page_contents.items()):
            matches = _PLACEHOLDER_PATTERNS.findall(content)
            if matches:
                files_with_placeholders.append(f"{fname} ({', '.join(set(matches))})")
        if files_with_placeholders:
            results.append(CheckResult(
                check_id="J-06", group="J", status=CheckStatus.FAIL,
                message=f"Placeholder text found in: {', '.join(files_with_placeholders[:5])}",
                field="content/modules/ROOT/pages/",
            ))
        else:
            results.append(CheckResult(
                check_id="J-06", group="J", status=CheckStatus.PASS,
                message="No placeholder text found in .adoc pages",
                field="content/modules/ROOT/pages/",
            ))

    # J-07: development.automation.status must be "complete"
    dev = spec_data.get("development", {})
    auto_status = dev.get("automation", {}).get("status", "")
    if auto_status == "complete":
        results.append(CheckResult(
            check_id="J-07", group="J", status=CheckStatus.PASS,
            message="Automation status is complete",
            field="development.automation.status",
        ))
    else:
        results.append(CheckResult(
            check_id="J-07", group="J", status=CheckStatus.FAIL,
            message=f"Automation status is '{auto_status or 'not set'}', expected 'complete'",
            field="development.automation.status",
        ))

    # J-08: development.e2e.status must be "complete"
    e2e_status = dev.get("e2e", {}).get("status", "")
    if e2e_status == "complete":
        results.append(CheckResult(
            check_id="J-08", group="J", status=CheckStatus.PASS,
            message="E2E testing status is complete",
            field="development.e2e.status",
        ))
    else:
        results.append(CheckResult(
            check_id="J-08", group="J", status=CheckStatus.FAIL,
            message=f"E2E testing status is '{e2e_status or 'not set'}', expected 'complete'",
            field="development.e2e.status",
        ))

    # J-09: development.healthCheck.status must be "complete"
    hc_status = dev.get("healthCheck", {}).get("status", "")
    if hc_status == "complete":
        results.append(CheckResult(
            check_id="J-09", group="J", status=CheckStatus.PASS,
            message="Health check status is complete",
            field="development.healthCheck.status",
        ))
    else:
        results.append(CheckResult(
            check_id="J-09", group="J", status=CheckStatus.FAIL,
            message=f"Health check status is '{hc_status or 'not set'}', expected 'complete'",
            field="development.healthCheck.status",
        ))

    return results
