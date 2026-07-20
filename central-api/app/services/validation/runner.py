"""Validation runner — maps stages to check groups, orchestrates execution."""
import asyncio
import logging

import yaml

from ..github import GitHubService
from .models import CheckResult, CheckStatus, AutoComputedFields, ValidationResponse
from .policy import load_policy
from . import (
    spec_fields,
    spec_conditional,
    approval_checklist,
    design_structure,
    module_outlines,
    cross_validation,
    automation_manifest,
    vocabulary,
    auto_compute,
)

logger = logging.getLogger(__name__)

STAGE_GROUPS = {
    "intake": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
    "review": ["A", "B", "D", "E", "F"],
}


async def _fetch_project_files(github: GitHubService, repo_url: str, branch: str) -> dict:
    """Fetch all needed files from the project repo in parallel."""
    spec_task = github.get_file_content(repo_url, "publishing-house/spec.yaml", branch)
    design_task = github.get_file_content(repo_url, "publishing-house/spec/design.md", branch)
    manifest_task = github.get_file_content(
        repo_url, "publishing-house/spec/automation-manifest.yaml", branch
    )
    modules_list_task = github.list_directory(repo_url, "publishing-house/spec/modules", branch)

    spec_raw, design_text, manifest_text, module_filenames = await asyncio.gather(
        spec_task, design_task, manifest_task, modules_list_task
    )

    outline_files = {}
    md_files = [f for f in module_filenames if f.startswith("module-") and f.endswith(".md")]
    if md_files:
        tasks = [
            github.get_file_content(repo_url, f"publishing-house/spec/modules/{f}", branch)
            for f in md_files
        ]
        contents = await asyncio.gather(*tasks)
        for fname, content in zip(md_files, contents):
            if content is not None:
                outline_files[fname] = content

    spec_data = yaml.safe_load(spec_raw) if spec_raw else None
    return {
        "spec_data": spec_data,
        "design_text": design_text,
        "manifest_text": manifest_text,
        "outline_files": outline_files,
    }


async def run_validation(
    github: GitHubService,
    repo_url: str,
    branch: str,
    stage: str,
) -> ValidationResponse:
    groups = STAGE_GROUPS.get(stage, STAGE_GROUPS["intake"])
    policy = load_policy()

    files = await _fetch_project_files(github, repo_url, branch)
    spec_data = files["spec_data"]
    design_text = files["design_text"]
    manifest_text = files["manifest_text"]
    outline_files = files["outline_files"]

    if not spec_data:
        return ValidationResponse(
            passed=False,
            results=[CheckResult(
                check_id="SYS-01", group="SYS", status=CheckStatus.FAIL,
                message="publishing-house/spec.yaml not found or unparseable",
                field="publishing-house/spec.yaml",
            )],
        )

    all_results: list[CheckResult] = []
    auto = AutoComputedFields()

    if "A" in groups:
        all_results.extend(spec_fields.run_checks(spec_data, policy))

    if "B" in groups:
        all_results.extend(spec_conditional.run_checks(spec_data, policy))

    if "C" in groups:
        all_results.extend(approval_checklist.run_checks(spec_data, policy))

    if "D" in groups:
        all_results.extend(design_structure.run_checks(design_text, policy))

    if "E" in groups:
        all_results.extend(module_outlines.run_checks(spec_data, outline_files, policy))

    if "F" in groups:
        all_results.extend(cross_validation.run_checks(spec_data, design_text, outline_files, policy))

    if "G" in groups:
        all_results.extend(automation_manifest.run_checks(manifest_text, policy))

    if "H" in groups:
        all_results.extend(vocabulary.run_checks(spec_data, policy))

    if "I" in groups:
        compute_results, auto = auto_compute.run_checks(spec_data, policy)
        all_results.extend(compute_results)

    passed = not any(r.status == CheckStatus.FAIL for r in all_results)

    return ValidationResponse(
        passed=passed,
        results=all_results,
        auto_computed=auto if "I" in groups else None,
    )
