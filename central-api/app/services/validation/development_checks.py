"""Group J — Development-stage checks (module completion and content file coverage)."""
import os

from .models import CheckResult, CheckStatus


def run_checks(
    spec_data: dict,
    outline_files: dict[str, str],
    page_files: list[str],
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

    return results
