"""Validation runner — maps stages to check groups, orchestrates execution."""
import logging

import yaml

from ..github import GitHubService, ClonedRepo
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
    "review": ["A", "B", "C", "D", "E", "F"],
    "development": [],
}


def _read_project_files(repo: ClonedRepo) -> dict:
    """Read all needed files from a cloned repo."""
    spec_raw = repo.read_file("publishing-house/spec.yaml")
    design_text = repo.read_file("publishing-house/spec/design.md")
    manifest_text = repo.read_file("publishing-house/spec/automation-manifest.yaml")

    outline_files = {}
    module_filenames = repo.list_dir("publishing-house/spec/modules")
    for fname in module_filenames:
        if fname.startswith("module-") and fname.endswith(".md"):
            content = repo.read_file(f"publishing-house/spec/modules/{fname}")
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

    repo = await github.clone_repo(repo_url, branch)
    try:
        files = _read_project_files(repo)
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
                commit_sha=repo.head_sha,
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

        env = spec_data.get("spec", {}).get("environment") if spec_data else None

        return ValidationResponse(
            passed=passed,
            results=all_results,
            auto_computed=auto if "I" in groups else None,
            commit_sha=repo.head_sha,
            approval_checklist=spec_data.get("approval_checklist"),
            repo_url=repo_url,
            spec_environment=env,
        )
    finally:
        repo.cleanup()
