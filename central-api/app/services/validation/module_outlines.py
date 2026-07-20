"""Group E — Module outline file checks."""
import re

from .models import CheckResult, CheckStatus


def run_checks(
    spec_data: dict,
    outline_files: dict[str, str],
    policy: dict,
) -> list[CheckResult]:
    """Check module outline files against spec.yaml modules list.

    Args:
        spec_data: parsed spec.yaml
        outline_files: {filename: content} for all module-*.md files
        policy: loaded policy dict
    """
    results = []
    modules_in_spec = spec_data.get("spec", {}).get("modules", [])
    required_sections = policy.get("required_outline_sections", [])

    # E-01: Each module in spec.yaml has a corresponding outline file
    expected_count = len(modules_in_spec)
    actual_count = len(outline_files)

    if expected_count == 0:
        results.append(CheckResult(
            check_id="E-01", group="E", status=CheckStatus.SKIP,
            message="No modules in spec.yaml yet",
            field="spec.modules",
        ))
    elif actual_count == 0:
        results.append(CheckResult(
            check_id="E-01", group="E", status=CheckStatus.FAIL,
            message=f"Spec declares {expected_count} modules but no outline files found",
            field="publishing-house/spec/modules/",
        ))
    elif actual_count != expected_count:
        results.append(CheckResult(
            check_id="E-01", group="E", status=CheckStatus.FAIL,
            message=f"Module count mismatch: spec has {expected_count}, outlines has {actual_count}",
            field="publishing-house/spec/modules/",
        ))
    else:
        results.append(CheckResult(
            check_id="E-01", group="E", status=CheckStatus.PASS,
            message=f"{actual_count} outline files match spec module count",
            field="publishing-house/spec/modules/",
        ))

    # E-02: Each outline has required sections
    if outline_files and required_sections:
        files_missing_sections = []
        for fname, content in sorted(outline_files.items()):
            headings = [m.group(1).strip().lower()
                        for m in re.finditer(r"^#{2,3}\s+(.+)$", content, re.MULTILINE)]
            for section in required_sections:
                section_lower = section.lower()
                # "see/learn/do" also matches "what you will see, learn, and do"
                if not any(section_lower in h or
                           (section_lower == "see/learn/do" and "see" in h and "learn" in h)
                           for h in headings):
                    files_missing_sections.append(f"{fname}: missing '{section}'")

        if files_missing_sections:
            results.append(CheckResult(
                check_id="E-02", group="E", status=CheckStatus.FAIL,
                message=f"Missing outline sections: {'; '.join(files_missing_sections[:5])}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="E-02", group="E", status=CheckStatus.PASS,
                message="All outlines have required sections",
                field="publishing-house/spec/modules/",
            ))
    elif not outline_files:
        results.append(CheckResult(
            check_id="E-02", group="E", status=CheckStatus.SKIP,
            message="No outline files to check",
            field="publishing-house/spec/modules/",
        ))

    # E-04: Lab Structure section has at least one table row per outline
    if outline_files:
        no_table = []
        for fname, content in sorted(outline_files.items()):
            in_lab = False
            has_row = False
            for line in content.splitlines():
                if re.match(r"^#{2,3}\s+lab\s+structure", line, re.IGNORECASE):
                    in_lab = True
                    continue
                if in_lab:
                    if re.match(r"^#{2,3}\s+", line):
                        break
                    if line.startswith("|") and "---" not in line:
                        cells = [c.strip() for c in line.strip("|").split("|")]
                        if len(cells) >= 2 and cells[0].strip().isdigit():
                            has_row = True
            if in_lab and not has_row:
                no_table.append(fname)
        if no_table:
            results.append(CheckResult(
                check_id="E-04", group="E", status=CheckStatus.FAIL,
                message=f"Lab Structure has no table rows: {', '.join(no_table[:3])}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="E-04", group="E", status=CheckStatus.PASS,
                message="All outlines have Lab Structure table rows",
                field="publishing-house/spec/modules/",
            ))

    # E-05: Duration specified in Audience and Time section
    if outline_files:
        no_duration = []
        duration_re = re.compile(r"\d+\s*(min|hour|hr|minute)", re.IGNORECASE)
        for fname, content in sorted(outline_files.items()):
            in_aud = False
            found = False
            for line in content.splitlines():
                if re.match(r"^#{2,3}\s+audience\s+and\s+time", line, re.IGNORECASE):
                    in_aud = True
                    continue
                if in_aud:
                    if re.match(r"^#{2,3}\s+", line):
                        break
                    if duration_re.search(line):
                        found = True
            if in_aud and not found:
                no_duration.append(fname)
        if no_duration:
            results.append(CheckResult(
                check_id="E-05", group="E", status=CheckStatus.FAIL,
                message=f"No duration in Audience and Time: {', '.join(no_duration[:3])}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="E-05", group="E", status=CheckStatus.PASS,
                message="All outlines specify duration in Audience and Time",
                field="publishing-house/spec/modules/",
            ))

    # E-06: No unfilled template placeholders in outlines
    if outline_files:
        ph_pattern = re.compile(
            r"\[(?:Title|Name|X\s*min|XX\s*min|Objective\s+\d|action verb|"
            r"PLACEHOLDER|TODO|REPLACE_ME|TBD|"
            r"specific,?\s*measurable|e\.g\.,)[^\]]*\]",
            re.IGNORECASE,
        )
        files_with_ph = []
        for fname, content in sorted(outline_files.items()):
            clean = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            found = ph_pattern.findall(clean)
            if found:
                files_with_ph.append(f"{fname}: {', '.join(found[:2])}")
        if files_with_ph:
            results.append(CheckResult(
                check_id="E-06", group="E", status=CheckStatus.FAIL,
                message=f"Unfilled placeholders in outlines: {'; '.join(files_with_ph[:3])}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="E-06", group="E", status=CheckStatus.PASS,
                message="No unfilled placeholders in outlines",
                field="publishing-house/spec/modules/",
            ))

    # E-03: No orphan outline files (files not matching any spec module)
    if outline_files and modules_in_spec:
        spec_ids = {m.get("id", "") for m in modules_in_spec if m.get("id")}
        orphans = []
        for fname in outline_files:
            # module-01-installing-openshift.md → extract the slug part
            match = re.match(r"module-\d+-(.+)\.md", fname)
            if match:
                slug = match.group(1)
                if spec_ids and slug not in spec_ids:
                    orphans.append(fname)
        if orphans:
            results.append(CheckResult(
                check_id="E-03", group="E", status=CheckStatus.WARN,
                message=f"Orphan outline files not matching spec modules: {', '.join(orphans[:3])}",
                field="publishing-house/spec/modules/",
            ))
        else:
            results.append(CheckResult(
                check_id="E-03", group="E", status=CheckStatus.PASS,
                message="No orphan outline files",
                field="publishing-house/spec/modules/",
            ))

    return results
