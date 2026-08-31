"""Drift detection — structural (spec.yaml field diff) and semantic (LLM design.md comparison)."""
import json
import logging
import os
import time
from typing import Optional

import httpx
import yaml
from pydantic import BaseModel

from .github import GitHubService
from ..config import get_settings

logger = logging.getLogger(__name__)

SPEC_PATH = "publishing-house/spec.yaml"
DESIGN_PATH = "publishing-house/spec/design.md"
MODULES_DIR = "publishing-house/spec/modules"
PAGES_DIR = "content/modules/ROOT/pages"
LITELLM_MODEL = "claude-haiku-4-5"

STRUCTURAL_FIELDS = [
    "project.content_type",
    "project.products",
    "spec.title",
    "spec.audience",
    "spec.learning_objectives",
    "spec.modules",
    "spec.environment.topology",
    "spec.environment.ocp_version",
    "spec.environment.cloud_provider",
    "spec.environment.cluster_type",
    "spec.environment.worker_count",
    "spec.environment.worker_cpu",
    "spec.environment.worker_ram_gb",
    "spec.environment.ai_requirement",
    "spec.environment.ai_model_tier",
]

_drift_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}


def drift_cache_get(slug: str, baseline: str, head: str) -> dict | None:
    key = (slug, baseline, head)
    entry = _drift_cache.get(key)
    if not entry:
        return None
    ts, response = entry
    ttl = get_settings().drift_cache_ttl_seconds
    if time.time() - ts > ttl:
        del _drift_cache[key]
        return None
    logger.debug("drift cache hit for %s (%s..%s)", slug, baseline[:8], head[:8])
    return response


def drift_cache_set(slug: str, baseline: str, head: str, response: dict) -> None:
    _drift_cache[(slug, baseline, head)] = (time.time(), response)


def drift_cache_evict(slug: str) -> None:
    keys = [k for k in _drift_cache if k[0] == slug]
    for k in keys:
        del _drift_cache[k]
    if keys:
        logger.info("evicted %d drift cache entries for %s", len(keys), slug)


SEMANTIC_SYSTEM_PROMPT = """You are a technical document reviewer. You will receive two versions of a design document (BASELINE and CURRENT). Compare them and identify meaningful changes, organized by section.

Ignore cosmetic changes (whitespace, punctuation, rewording that preserves meaning). Only flag substantive changes: added/removed/renamed modules, changed durations, altered infrastructure requirements, changed cluster sizing, added/removed environment dependencies, changed products, etc.

Respond with valid JSON only, no markdown fencing:
{
  "has_drift": true/false,
  "summary": "one-sentence summary of what changed, or 'No meaningful drift detected'",
  "changes": [
    {
      "section": "section name (e.g. Module Map, Environment, Infrastructure Requirements)",
      "difference": "description of what changed"
    }
  ]
}

Only include sections that have meaningful changes. If no drift, return an empty changes array."""

ALIGNMENT_SYSTEM_PROMPT = """You are a technical content reviewer. You will receive a module outline with learning objectives and the corresponding AsciiDoc content page. Determine whether the learning objectives from the outline are adequately covered in the content.

For each learning objective, check if the content page addresses it with relevant instructions, explanations, or exercises.

Respond with valid JSON only, no markdown fencing:
{
  "aligned": true/false,
  "uncovered_objectives": [
    {
      "objective": "the learning objective text",
      "reason": "brief explanation of why it is not covered"
    }
  ]
}

If all objectives are covered, set aligned to true and return an empty uncovered_objectives array. Only flag objectives that are genuinely missing or inadequately addressed — minor wording differences are fine."""


class DriftChange(BaseModel):
    file: str
    comparing: str
    difference: str
    severity: str | None = None


class DriftResponse(BaseModel):
    has_drift: bool
    baseline_sha: str
    current_sha: str
    summary: str
    changes: list[DriftChange]


def _empty_response(baseline_sha: str, current_sha: str, summary: str, has_drift: bool = False) -> DriftResponse:
    return DriftResponse(
        has_drift=has_drift,
        baseline_sha=baseline_sha,
        current_sha=current_sha,
        summary=summary,
        changes=[],
    )


def _get_nested(data: dict, dotpath: str):
    keys = dotpath.split(".")
    val = data
    for k in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(k)
    return val


def _format_value(val) -> str:
    if val is None:
        return "<not set>"
    if isinstance(val, list):
        if not val:
            return "<empty>"
        if isinstance(val[0], dict) and "title" in val[0]:
            return ", ".join(m.get("title", "?") for m in val)
        return ", ".join(str(v) for v in val)
    return str(val)


def _compute_module_diff(old_modules: list, new_modules: list) -> str:
    """Compute detailed diff for spec.modules showing indexed changes."""
    if not old_modules and not new_modules:
        return "<empty> → <empty>"
    if not old_modules:
        return f"Added {len(new_modules)} module(s)"
    if not new_modules:
        return f"Removed {len(old_modules)} module(s)"

    # Build ID-to-module maps
    old_by_id = {m.get("id"): m for m in old_modules if m.get("id")}
    new_by_id = {m.get("id"): m for m in new_modules if m.get("id")}

    # If no IDs, fall back to simple count comparison
    if not old_by_id or not new_by_id:
        return f"{len(old_modules)} module(s) → {len(new_modules)} module(s)"

    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    common_ids = old_ids & new_ids

    parts = []

    # Removed modules
    for id in sorted(removed_ids):
        m = old_by_id[id]
        module_num = id.split("-")[-1] if "-" in id else "?"
        parts.append(f'Module {module_num}: Removed "{m.get("title")}"')

    # Modified modules (only check title and duration_min, ignore status)
    for id in sorted(common_ids):
        old_m = old_by_id[id]
        new_m = new_by_id[id]

        changes_detail = []
        if old_m.get("title") != new_m.get("title"):
            changes_detail.append(f'title: "{old_m.get("title")}" → "{new_m.get("title")}"')
        if old_m.get("duration_min") != new_m.get("duration_min"):
            changes_detail.append(f'duration: {old_m.get("duration_min")} → {new_m.get("duration_min")} min')

        if changes_detail:
            module_num = id.split("-")[-1] if "-" in id else "?"
            parts.append(f'Module {module_num}: {" | ".join(changes_detail)}')

    # Added modules
    for id in sorted(added_ids):
        m = new_by_id[id]
        module_num = id.split("-")[-1] if "-" in id else "?"
        parts.append(f'Module {module_num}: Added "{m.get("title")}"')

    if not parts:
        return "No changes detected (status/id changes only)"

    # Show all changes - reviewers need complete information
    return " | ".join(parts)


async def check_drift_structural(
    github: GitHubService,
    repo_url: str,
    branch: str,
    baseline_sha: str,
) -> DriftResponse:
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    baseline_raw = await github.get_file_content(repo_url, SPEC_PATH, baseline_sha)
    current_raw = await github.get_file_content(repo_url, SPEC_PATH, branch)

    if not baseline_raw and not current_raw:
        return _empty_response(baseline_sha, current_sha, "spec.yaml not found in either commit")

    if not baseline_raw:
        return _empty_response(baseline_sha, current_sha, "spec.yaml was added after baseline commit", has_drift=True)

    if baseline_raw == current_raw:
        return _empty_response(baseline_sha, current_sha, "No changes to spec.yaml")

    try:
        baseline_data = yaml.safe_load(baseline_raw) or {}
        current_data = yaml.safe_load(current_raw) or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse spec.yaml: {e}")
        return _empty_response(baseline_sha, current_sha, f"Failed to parse spec.yaml: {e}")

    changes: list[DriftChange] = []
    for field in STRUCTURAL_FIELDS:
        old_val = _get_nested(baseline_data, field)
        new_val = _get_nested(current_data, field)
        if old_val != new_val:
            # Special handling for spec.modules - show detailed indexed diff
            if field == "spec.modules" and isinstance(old_val, list) and isinstance(new_val, list):
                difference = _compute_module_diff(old_val, new_val)
            else:
                difference = f"{_format_value(old_val)} → {_format_value(new_val)}"

            changes.append(DriftChange(
                file="spec.yaml",
                comparing=field,
                difference=difference,
                severity="critical",
            ))

    if not changes:
        return _empty_response(baseline_sha, current_sha, "No structural drift in contract fields")

    # Summary removed - all details are in the changes table
    return DriftResponse(
        has_drift=True,
        baseline_sha=baseline_sha,
        current_sha=current_sha,
        summary="",
        changes=changes,
    )


async def _check_content_alignment(
    github: GitHubService,
    repo_url: str,
    branch: str,
    litellm_api_url: str,
    ph_internal_ai_api_key: str,
) -> list[DriftChange]:
    """Check if content pages cover the learning objectives from module outlines."""
    outline_names = await github.list_directory(repo_url, MODULES_DIR, branch)
    outline_names = [f for f in outline_names if f.startswith("module-") and f.endswith(".md")]
    if not outline_names:
        return []

    page_names = await github.list_directory(repo_url, PAGES_DIR, branch)
    page_stems = {os.path.splitext(f)[0]: f for f in page_names if f.endswith(".adoc")}

    changes: list[DriftChange] = []

    for outline_name in outline_names:
        stem = os.path.splitext(outline_name)[0]
        page_name = page_stems.get(stem)
        if not page_name:
            continue

        outline_content = await github.get_file_content(repo_url, f"{MODULES_DIR}/{outline_name}", branch)
        page_content = await github.get_file_content(repo_url, f"{PAGES_DIR}/{page_name}", branch)
        if not outline_content or not page_content:
            continue

        user_prompt = f"""## MODULE OUTLINE ({outline_name}):

{outline_content}

---

## CONTENT PAGE ({page_name}):

{page_content}"""

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                resp = await client.post(
                    f"{litellm_api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {ph_internal_ai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LITELLM_MODEL,
                        "messages": [
                            {"role": "system", "content": ALIGNMENT_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0,
                        "max_tokens": 1024,
                    },
                )

            if resp.status_code != 200:
                logger.error("alignment check failed for %s: %s", outline_name, resp.status_code)
                continue

            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(content)
            if not result.get("aligned", True):
                for obj in result.get("uncovered_objectives", []):
                    changes.append(DriftChange(
                        file=page_name,
                        comparing=f"{stem}: {obj['objective']}",
                        difference=obj.get("reason", "Learning objective not covered"),
                        severity="critical",
                    ))
        except Exception as e:
            logger.error("alignment check error for %s: %s", outline_name, e)

    return changes


async def check_drift_semantic(
    github: GitHubService,
    repo_url: str,
    branch: str,
    baseline_sha: str,
    litellm_api_url: str,
    ph_internal_ai_api_key: str,
    slug: str = "",
) -> DriftResponse:
    current_sha = await github.get_head_sha(repo_url, branch) or ""

    if slug and current_sha:
        cached = drift_cache_get(slug, baseline_sha, current_sha)
        if cached is not None:
            return DriftResponse(**cached)

    baseline_md = await github.get_file_content(repo_url, DESIGN_PATH, baseline_sha)
    current_md = await github.get_file_content(repo_url, DESIGN_PATH, branch)

    if not baseline_md and not current_md:
        return _empty_response(baseline_sha, current_sha, "design.md not found in either commit")

    if not baseline_md:
        return _empty_response(baseline_sha, current_sha, "design.md was added after the baseline commit", has_drift=True)

    if baseline_md == current_md:
        alignment_changes = await _check_content_alignment(
            github, repo_url, branch, litellm_api_url, ph_internal_ai_api_key,
        )
        if alignment_changes:
            resp = DriftResponse(
                has_drift=True,
                baseline_sha=baseline_sha,
                current_sha=current_sha,
                summary=f"Content misaligned: {len(alignment_changes)} uncovered learning objective(s)",
                changes=alignment_changes,
            )
        else:
            resp = _empty_response(baseline_sha, current_sha, "No changes to design.md")
        if slug and current_sha:
            drift_cache_set(slug, baseline_sha, current_sha, resp.model_dump())
        return resp

    user_prompt = f"""## BASELINE VERSION (commit {baseline_sha[:8]}):

{baseline_md}

---

## CURRENT VERSION (commit {current_sha[:8]}):

{current_md}"""

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.post(
                f"{litellm_api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ph_internal_ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LITELLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            )

        if resp.status_code != 200:
            logger.error(f"LLM drift check failed: {resp.status_code} {resp.text}")
            return _empty_response(baseline_sha, current_sha, f"LLM comparison failed (HTTP {resp.status_code})")

        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(content)

        changes = [
            DriftChange(
                file="design.md",
                comparing=c["section"],
                difference=c["difference"],
                severity="critical",
            )
            for c in result.get("changes", [])
        ]

        design_has_drift = result.get("has_drift", False)
        design_summary = result.get("summary", "")

        # Content alignment check — learning objectives vs page content
        alignment_changes = await _check_content_alignment(
            github, repo_url, branch, litellm_api_url, ph_internal_ai_api_key,
        )
        changes.extend(alignment_changes)

        has_drift = design_has_drift or len(alignment_changes) > 0
        if alignment_changes and not design_has_drift:
            design_summary = f"Content misaligned: {len(alignment_changes)} uncovered learning objective(s)"
        elif alignment_changes and design_has_drift:
            design_summary += f"; plus {len(alignment_changes)} uncovered learning objective(s)"

        resp = DriftResponse(
            has_drift=has_drift,
            baseline_sha=baseline_sha,
            current_sha=current_sha,
            summary=design_summary,
            changes=changes,
        )
        if slug and current_sha:
            drift_cache_set(slug, baseline_sha, current_sha, resp.model_dump())
        return resp

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM drift response: {e}")
        return _empty_response(baseline_sha, current_sha, "Failed to parse LLM comparison result")
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        return _empty_response(baseline_sha, current_sha, f"Drift detection error: {str(e)}")


# ── Infra (AgnosticV sizing) drift ──────────────────────────────────────────

import re as _re

_aws_instance_cache: dict | None = None


def _get_aws_instance_map() -> dict[str, tuple[int, int]]:
    global _aws_instance_cache
    if _aws_instance_cache is not None:
        return _aws_instance_cache
    try:
        raw = get_settings().aws_instance_type_map
        parsed = json.loads(raw) if raw else {}
        _aws_instance_cache = {k: tuple(v) for k, v in parsed.items()}
    except Exception as e:
        logger.warning("failed to parse AWS_INSTANCE_TYPE_MAP: %s", e)
        _aws_instance_cache = {}
    return _aws_instance_cache


def _parse_agnosticv_url(url: str) -> tuple[str, str, str] | None:
    """Extract (repo_url, branch, path) from a GitHub tree URL."""
    m = _re.match(r"https?://github\.com/([^/]+/[^/]+)/tree/([^/]+)/(.+?)/?$", url)
    if not m:
        return None
    return f"https://github.com/{m.group(1)}", m.group(2), m.group(3)


def _parse_ram(value) -> int | None:
    """Normalise RAM values: '128Gi'→128, '65536Mi'→64, plain int→int."""
    if value is None:
        return None
    s = str(value).strip().strip("'\"")
    m = _re.match(r"^(\d+)\s*[Gg]i?$", s)
    if m:
        return int(m.group(1))
    m = _re.match(r"^(\d+)\s*[Mm]i?$", s)
    if m:
        return int(m.group(1)) // 1024
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_cpu(value) -> int | None:
    """Normalise CPU values: string or int → int."""
    if value is None:
        return None
    s = str(value).strip().strip("'\"")
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _is_static_int(value) -> bool:
    """Check if value is a static integer (not a Jinja expression)."""
    if value is None:
        return False
    if isinstance(value, int):
        return True
    if not isinstance(value, str):
        return False
    # Reject if contains Jinja markers
    if "{{" in value or "}}" in value or "{%" in value or "%}" in value:
        return False
    # Check if it's a plain integer string
    s = str(value).strip().strip("'\"")
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False


def _get_value_with_source(
    key: str,
    configs: list[tuple[dict, str]],
) -> tuple[str, str]:
    """Get value from configs with source file tracking.

    Args:
        key: The config key to look up
        configs: List of (config_dict, file_name) tuples, checked in order

    Returns:
        (value, source_file) tuple. Returns ("", "") if not found.
    """
    for config_dict, file_name in configs:
        value = config_dict.get(key, "")
        if value:
            return (value, file_name)
    return ("", "")


def _resolve_jinja_ternary(value, variables: dict):
    """Resolve simple Jinja ternary: {{ A if var == 'val' else B }}."""
    if not isinstance(value, str) or "{{" not in value:
        return value
    m = _re.match(
        r"\{\{\s*['\"]?(.+?)['\"]?\s+if\s+(\w+)\s*==\s*['\"](.+?)['\"]\s+else\s+['\"]?(.+?)['\"]?\s*\}\}",
        value.strip(),
    )
    if not m:
        return value
    true_val, var_name, test_val, false_val = m.group(1), m.group(2), m.group(3), m.group(4)
    actual = str(variables.get(var_name, ""))
    return true_val.strip("'\"") if actual == test_val else false_val.strip("'\"")


def _extract_gpu_type(configs: list[dict]) -> str | None:
    """Extract GPU instance type from AgnosticV config."""
    for cfg in configs:
        for key, val in cfg.items():
            if key.startswith("gpu_instance_type"):
                s = str(val).strip("'\"")
                jinja_var = _re.match(r"\{\{\s*(\w+)\s*\}\}", s)
                if jinja_var:
                    for c in configs:
                        v = c.get(jinja_var.group(1))
                        if v:
                            return str(v).strip("'\"")
                elif s and "{{" not in s:
                    return s
                break

    for cfg in configs:
        ms_list = cfg.get("ocp4_workload_machineset_config", [])
        if not isinstance(ms_list, list):
            continue
        for ms in ms_list:
            if not isinstance(ms, dict):
                continue
            role = str(ms.get("role", ""))
            if "gpu" not in role.lower():
                continue
            inst = str(ms.get("instance_type", ""))
            jinja_var = _re.match(r"\{\{\s*(\w+)\s*\}\}", inst)
            if jinja_var:
                for c in configs:
                    v = c.get(jinja_var.group(1))
                    if v:
                        return str(v).strip("'\"")
            elif inst and "{{" not in inst:
                return inst

    return None


async def check_drift_infra(
    github: GitHubService,
    agnosticv_urls: list[str],
    spec_env: dict,
    current_sha: str = "",
) -> DriftResponse:
    """Compare spec.yaml environment sizing against AgnosticV catalog item config."""
    if not agnosticv_urls:
        return _empty_response("", current_sha, "No AgnosticV URLs configured")

    changes: list[DriftChange] = []

    for url in agnosticv_urls:
        parsed = _parse_agnosticv_url(url)
        if not parsed:
            logger.warning("infra drift: cannot parse agnosticv URL: %s", url)
            continue

        repo_url, branch, path = parsed

        try:
            common_raw = await github.get_file_content(repo_url, f"{path}/common.yaml", branch)
            if not common_raw:
                logger.warning("infra drift: common.yaml not found at %s", path)
                continue

            common = yaml.safe_load(common_raw) or {}
            dev_raw = await github.get_file_content(repo_url, f"{path}/dev.yaml", branch)
            dev = yaml.safe_load(dev_raw) or {} if dev_raw else {}
            cloud_provider = common.get("cloud_provider", "")
            config_type = common.get("config", "")
            meta = common.get("__meta__", {})
            components = meta.get("components", [])
            display_file = f"{path.split('/')[-1]}/common.yaml"

            # Determine if this is OCP or RHEL
            is_rhel = config_type in ("ansible-multi-node",) or cloud_provider in ("ec2",)
            platform = spec_env.get("platform", "").lower()
            if platform == "rhel" or is_rhel:
                # RHEL VM sizing comparison
                spec_vms = spec_env.get("vms_per_student", [])
                if not spec_vms:
                    continue
                # Look for cnv_instances or ec2_instances in the config
                agv_vms = common.get("cnv_instances", common.get("ec2_instances", []))
                for spec_vm in spec_vms:
                    role = spec_vm.get("role", "unknown")
                    matched = next((v for v in agv_vms if v.get("name", "") == role), None)
                    if not matched:
                        changes.append(DriftChange(
                            file=display_file,
                            comparing=f"vm:{role}",
                            difference=f"VM role '{role}' in spec.yaml not found in AgnosticV config",
                            severity="warning",
                        ))
                        continue
                    agv_cpu = _parse_cpu(matched.get("cores", matched.get("cpu")))
                    agv_ram = _parse_ram(matched.get("memory", matched.get("ram")))
                    spec_cpu = spec_vm.get("cpu")
                    spec_ram = spec_vm.get("ram_gb")
                    if spec_cpu and agv_cpu and int(spec_cpu) != agv_cpu:
                        changes.append(DriftChange(
                            file=display_file,
                            comparing=f"vm:{role}:cpu",
                            difference=f"spec: {spec_cpu} vCPU vs agnosticv: {agv_cpu} vCPU",
                            severity="warning",
                        ))
                    if spec_ram and agv_ram and int(spec_ram) != agv_ram:
                        changes.append(DriftChange(
                            file=display_file,
                            comparing=f"vm:{role}:ram",
                            difference=f"spec: {spec_ram} GB vs agnosticv: {agv_ram} GB",
                            severity="warning",
                        ))
                continue

            # OCP sizing comparison
            pool_common = common
            pool_file = display_file
            param_values: dict = {}

            if cloud_provider == "none" and components:
                comp = components[0]
                param_values = comp.get("parameter_values", {})
                pool_ref = comp.get("item", "")
                if pool_ref:
                    # Convert item ref to path: agd-v2/foo/bar → agd_v2/foo (drop stage suffix)
                    pool_path = pool_ref.replace("agd-v2/", "agd_v2/")
                    # Strip stage suffix like /prod, /event, /dev
                    pool_path = _re.sub(r"/(prod|dev|test|event)$", "", pool_path)
                    pool_raw = await github.get_file_content(repo_url, f"{pool_path}/common.yaml", branch)
                    if pool_raw:
                        pool_common = yaml.safe_load(pool_raw) or {}
                        pool_file = f"{pool_path.split('/')[-1]}/common.yaml"
                    else:
                        logger.warning("infra drift: pool common.yaml not found at %s", pool_path)

            pool_cloud = pool_common.get("cloud_provider", cloud_provider)

            # Resolve Jinja ternaries using parameter_values
            resolve_vars = {**pool_common, **param_values}

            if pool_cloud == "aws":
                instance_map = _get_aws_instance_map()
                config_sources = [(pool_common, pool_file), (common, display_file), (dev, display_file)]

                # Control plane (check both control_plane_instance_type and master_instance_type)
                cp_type_raw = ""
                cp_type_file = ""
                for config_dict, file_name in config_sources:
                    cp_type_raw = config_dict.get("control_plane_instance_type") or config_dict.get("master_instance_type", "")
                    if cp_type_raw:
                        cp_type_file = file_name
                        break

                cp_type = _resolve_jinja_ternary(cp_type_raw, resolve_vars)
                if cp_type and cp_type in instance_map:
                    agv_cp_cpu, agv_cp_ram = instance_map[cp_type]
                    spec_cp_cpu = spec_env.get("control_plane_cpu")
                    spec_cp_ram = spec_env.get("control_plane_ram_gb")
                    if spec_cp_cpu and int(spec_cp_cpu) != agv_cp_cpu:
                        changes.append(DriftChange(
                            file=cp_type_file or pool_file,
                            comparing="control_plane_cpu",
                            difference=f"spec: {spec_cp_cpu} vCPU vs agnosticv: {agv_cp_cpu} vCPU ({cp_type})",
                            severity="warning",
                        ))
                    if spec_cp_ram and int(spec_cp_ram) != agv_cp_ram:
                        changes.append(DriftChange(
                            file=cp_type_file or pool_file,
                            comparing="control_plane_ram_gb",
                            difference=f"spec: {spec_cp_ram} GB vs agnosticv: {agv_cp_ram} GB ({cp_type})",
                            severity="warning",
                        ))

                # Workers (check pool first, fall back to component common, then dev)
                wk_type_raw, wk_type_file = _get_value_with_source("worker_instance_type", config_sources)
                wk_type = _resolve_jinja_ternary(wk_type_raw, resolve_vars)
                if wk_type and wk_type in instance_map:
                    agv_wk_cpu, agv_wk_ram = instance_map[wk_type]
                    spec_wk_cpu = spec_env.get("worker_cpu")
                    spec_wk_ram = spec_env.get("worker_ram_gb")
                    if spec_wk_cpu and int(spec_wk_cpu) != agv_wk_cpu:
                        changes.append(DriftChange(
                            file=wk_type_file or display_file,
                            comparing="worker_cpu",
                            difference=f"spec: {spec_wk_cpu} vCPU vs agnosticv: {agv_wk_cpu} vCPU ({wk_type})",
                            severity="warning",
                        ))
                    if spec_wk_ram and int(spec_wk_ram) != agv_wk_ram:
                        changes.append(DriftChange(
                            file=wk_type_file or display_file,
                            comparing="worker_ram_gb",
                            difference=f"spec: {spec_wk_ram} GB vs agnosticv: {agv_wk_ram} GB ({wk_type})",
                            severity="warning",
                        ))

            else:
                # CNV or other — direct values
                # Track which file the value came from: [(config_dict, file_name), ...]
                config_sources = [(pool_common, pool_file), (common, display_file), (dev, display_file)]

                cp_cpu_raw, cp_cpu_file = _get_value_with_source("ai_control_plane_cores", config_sources)
                agv_cp_cpu = _parse_cpu(_resolve_jinja_ternary(cp_cpu_raw, resolve_vars))
                cp_ram_raw, cp_ram_file = _get_value_with_source("ai_control_plane_memory", config_sources)
                agv_cp_ram = _parse_ram(_resolve_jinja_ternary(cp_ram_raw, resolve_vars))
                spec_cp_cpu = spec_env.get("control_plane_cpu")
                spec_cp_ram = spec_env.get("control_plane_ram_gb")

                if spec_cp_cpu and agv_cp_cpu and int(spec_cp_cpu) != agv_cp_cpu:
                    changes.append(DriftChange(
                        file=cp_cpu_file or pool_file,
                        comparing="control_plane_cpu",
                        difference=f"spec: {spec_cp_cpu} vCPU vs agnosticv: {agv_cp_cpu} vCPU",
                        severity="warning",
                    ))
                if spec_cp_ram and agv_cp_ram and int(spec_cp_ram) != agv_cp_ram:
                    changes.append(DriftChange(
                        file=cp_ram_file or pool_file,
                        comparing="control_plane_ram_gb",
                        difference=f"spec: {spec_cp_ram} GB vs agnosticv: {agv_cp_ram} GB",
                        severity="warning",
                    ))

                wk_cpu_raw, wk_cpu_file = _get_value_with_source("ai_workers_cores", config_sources)
                agv_wk_cpu = _parse_cpu(_resolve_jinja_ternary(wk_cpu_raw, resolve_vars))
                wk_ram_raw, wk_ram_file = _get_value_with_source("ai_workers_memory", config_sources)
                agv_wk_ram = _parse_ram(_resolve_jinja_ternary(wk_ram_raw, resolve_vars))
                spec_wk_cpu = spec_env.get("worker_cpu")
                spec_wk_ram = spec_env.get("worker_ram_gb")

                if spec_wk_cpu and agv_wk_cpu and int(spec_wk_cpu) != agv_wk_cpu:
                    changes.append(DriftChange(
                        file=wk_cpu_file or pool_file,
                        comparing="worker_cpu",
                        difference=f"spec: {spec_wk_cpu} vCPU vs agnosticv: {agv_wk_cpu} vCPU",
                        severity="warning",
                    ))
                if spec_wk_ram and agv_wk_ram and int(spec_wk_ram) != agv_wk_ram:
                    changes.append(DriftChange(
                        file=wk_ram_file or pool_file,
                        comparing="worker_ram_gb",
                        difference=f"spec: {spec_wk_ram} GB vs agnosticv: {agv_wk_ram} GB",
                        severity="warning",
                    ))

            # Worker count comparison (only if AgnosticV value is static, not Jinja)
            worker_count_raw, worker_count_file = _get_value_with_source(
                "worker_instance_count",
                [(pool_common, pool_file), (common, display_file), (dev, display_file)]
            )
            if _is_static_int(worker_count_raw):
                agv_worker_count = _parse_cpu(worker_count_raw)
                spec_worker_count = spec_env.get("worker_count")
                if spec_worker_count and agv_worker_count is not None and int(spec_worker_count) != agv_worker_count:
                    changes.append(DriftChange(
                        file=worker_count_file or display_file,
                        comparing="worker_count",
                        difference=f"spec: {spec_worker_count} workers vs agnosticv: {agv_worker_count} workers",
                        severity="warning",
                    ))

            # GPU type comparison
            spec_gpu_type = spec_env.get("gpu_type", "")
            agv_gpu_type = _extract_gpu_type([pool_common, common, dev])

            if spec_gpu_type or agv_gpu_type:
                if spec_gpu_type and agv_gpu_type and spec_gpu_type.lower() != agv_gpu_type.lower():
                    changes.append(DriftChange(
                        file=display_file,
                        comparing="gpu_type",
                        difference=f"spec: {spec_gpu_type} vs agnosticv: {agv_gpu_type}",
                        severity="warning",
                    ))
                elif spec_gpu_type and not agv_gpu_type:
                    changes.append(DriftChange(
                        file=display_file,
                        comparing="gpu_type",
                        difference=f"spec: {spec_gpu_type} vs agnosticv: <not found>",
                        severity="warning",
                    ))
                elif agv_gpu_type and not spec_gpu_type:
                    changes.append(DriftChange(
                        file=display_file,
                        comparing="gpu_type",
                        difference=f"spec: <not set> vs agnosticv: {agv_gpu_type}",
                        severity="warning",
                    ))

        except Exception as e:
            logger.error("infra drift check failed for %s: %s", url, e)
            continue

    summary = f"{len(changes)} sizing mismatch(es)" if changes else "Spec sizing matches AgnosticV config"
    return DriftResponse(
        has_drift=False,
        baseline_sha="",
        current_sha=current_sha,
        summary=summary,
        changes=changes,
    )
