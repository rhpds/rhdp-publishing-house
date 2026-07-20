"""Group F — Cross-validation checks (CV-1 to CV-5)."""
import re

from .models import CheckResult, CheckStatus


def _extract_module_map(text: str) -> list[dict]:
    modules = []
    in_table = False
    for line in text.splitlines():
        if "module map" in line.lower():
            in_table = True
            continue
        if in_table:
            if line.startswith("|") and "---" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0].strip().isdigit():
                    modules.append({
                        "title": cells[1].strip(),
                        "duration": cells[2].strip() if len(cells) > 2 else "",
                    })
            elif in_table and not line.startswith("|") and line.strip():
                break
    return modules


def _parse_duration_minutes(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(min|hour|hr)", text.lower())
    if m:
        val = int(m.group(1))
        return val if "min" in m.group(2) else val * 60
    return None


def run_checks(
    spec_data: dict,
    design_text: str | None,
    outline_files: dict[str, str],
    policy: dict,
) -> list[CheckResult]:
    results = []
    modules_in_spec = spec_data.get("spec", {}).get("modules", [])
    objectives = spec_data.get("spec", {}).get("learning_objectives", [])

    if not design_text:
        results.append(CheckResult(
            check_id="F-00", group="F", status=CheckStatus.SKIP,
            message="design.md not available — CV-1 to CV-5 skipped",
            field="publishing-house/spec/design.md",
        ))
        return results

    design_modules = _extract_module_map(design_text)
    sorted_outlines = sorted(outline_files.keys())

    # CV-1: Module count — design.md Module Map vs outline files
    if design_modules and outline_files:
        if len(design_modules) != len(outline_files):
            results.append(CheckResult(
                check_id="F-01", group="F", status=CheckStatus.FAIL,
                message=f"CV-1: design.md has {len(design_modules)} modules, "
                        f"found {len(outline_files)} outline files",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="F-01", group="F", status=CheckStatus.PASS,
                message=f"CV-1: {len(design_modules)} modules match outline count",
                field="publishing-house/spec/modules/",
            ))
    else:
        results.append(CheckResult(
            check_id="F-01", group="F", status=CheckStatus.SKIP,
            message="CV-1: Module Map or outline files not available",
            field="publishing-house/spec/modules/",
        ))

    # CV-2: Module title alignment (slug prefix match)
    if design_modules and sorted_outlines:
        mismatches = []
        for i, dm in enumerate(design_modules):
            expected_prefix = f"module-{i+1:02d}-"
            if i < len(sorted_outlines):
                fname = sorted_outlines[i]
                if not fname.startswith(expected_prefix):
                    mismatches.append(f"Module {i+1}: expected {expected_prefix}*, found {fname}")
        if mismatches:
            results.append(CheckResult(
                check_id="F-02", group="F", status=CheckStatus.WARN,
                message=f"CV-2: {len(mismatches)} title/filename mismatch(es): {mismatches[0]}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="F-02", group="F", status=CheckStatus.PASS,
                message="CV-2: Module title prefixes align with outline files",
                field="publishing-house/spec/modules/",
            ))

    # CV-3: Learning objectives traceable to outlines
    if objectives and outline_files:
        all_outline_text = " ".join(outline_files.values()).lower()
        uncovered = []
        for obj in objectives:
            keywords = [w for w in obj.lower().split() if len(w) > 4]
            if keywords and not any(kw in all_outline_text for kw in keywords[:3]):
                uncovered.append(obj[:60])
        if uncovered:
            results.append(CheckResult(
                check_id="F-03", group="F", status=CheckStatus.WARN,
                message=f"CV-3: {len(uncovered)} objective(s) not found in outlines: {uncovered[0]}",
                field="spec.learning_objectives",
            ))
        else:
            results.append(CheckResult(
                check_id="F-03", group="F", status=CheckStatus.PASS,
                message=f"CV-3: All {len(objectives)} objectives traceable to outlines",
                field="spec.learning_objectives",
            ))
    elif not objectives:
        results.append(CheckResult(
            check_id="F-03", group="F", status=CheckStatus.SKIP,
            message="CV-3: No learning objectives in spec",
            field="spec.learning_objectives",
        ))

    # CV-4: Duration consistency between design.md and outlines
    if design_modules and outline_files:
        design_total = sum(d for d in [_parse_duration_minutes(dm.get("duration", ""))
                                       for dm in design_modules] if d)
        outline_total = sum(d for d in [_parse_duration_minutes(content)
                                        for content in outline_files.values()] if d)
        if design_total and outline_total:
            if design_total > 0 and abs(design_total - outline_total) / design_total > 0.2:
                results.append(CheckResult(
                    check_id="F-04", group="F", status=CheckStatus.WARN,
                    message=f"CV-4: Duration mismatch >20% — design: {design_total}min, outlines: {outline_total}min",
                    field="publishing-house/spec/design.md",
                ))
            else:
                results.append(CheckResult(
                    check_id="F-04", group="F", status=CheckStatus.PASS,
                    message=f"CV-4: Durations consistent (design: ~{design_total}min, outlines: ~{outline_total}min)",
                    field="publishing-house/spec/design.md",
                ))
        else:
            results.append(CheckResult(
                check_id="F-04", group="F", status=CheckStatus.SKIP,
                message="CV-4: Could not parse durations",
                field="publishing-house/spec/design.md",
            ))

    # CV-5: spec.yaml modules vs design.md Module Map alignment
    spec_titles = [m.get("title", "") for m in modules_in_spec]
    design_titles = [m["title"] for m in design_modules]
    if spec_titles and design_titles:
        only_in_spec = set(spec_titles) - set(design_titles)
        only_in_design = set(design_titles) - set(spec_titles)
        if only_in_spec or only_in_design:
            msg = "CV-5: spec.yaml modules differ from design.md Module Map."
            if only_in_spec:
                msg += f" In spec only: {only_in_spec}."
            if only_in_design:
                msg += f" In design only: {only_in_design}."
            results.append(CheckResult(
                check_id="F-05", group="F", status=CheckStatus.FAIL,
                message=msg,
                field="spec.modules",
            ))
        else:
            results.append(CheckResult(
                check_id="F-05", group="F", status=CheckStatus.PASS,
                message=f"CV-5: spec.yaml modules match design.md Module Map ({len(spec_titles)} modules)",
                field="spec.modules",
            ))
    else:
        results.append(CheckResult(
            check_id="F-05", group="F", status=CheckStatus.SKIP,
            message="CV-5: modules not set in spec.yaml or design.md has no Module Map",
            field="spec.modules",
        ))

    return results
