"""Load validation policy from ConfigMap-mounted YAML."""
import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

POLICY_PATH = Path("/etc/ph-policy/policy.yaml")

_FALLBACK_POLICY = {
    "ocp_version_minimum": "4.20",
    "valid_content_types": ["lab", "demo"],
    "valid_audiences": ["beginner", "intermediate", "advanced"],
    "valid_topologies": ["shared-cluster", "per-student", "cnv-pool"],
    "valid_showroom_types": ["showroom", "instructions"],
    "valid_platforms": ["ocp", "rhel-vms"],
    "valid_cluster_types": ["sno", "multinode"],
    "valid_rhel_versions": ["8", "9", "10"],
    "action_verbs_valid": [
        "configure", "deploy", "create", "implement", "troubleshoot",
        "monitor", "scale", "install", "build", "integrate", "automate",
        "manage", "observe", "migrate", "secure", "provision", "verify",
        "demonstrate", "explore", "analyze",
    ],
    "action_verbs_rejected": [
        "understand", "learn", "know", "be familiar with", "appreciate",
        "become aware", "realize", "recognize",
    ],
    "ai_keywords": [
        "ai", "rhoai", "openshift ai", "maas", "granite", "instructlab",
        "ollama", "llm", "inference", "model serving", "generative",
    ],
    "vague_egress_terms": [
        "internet", "any public ip", "any ip", "anywhere", "cloud", "external",
    ],
    "required_design_sections": [
        "overview",
        "target audience",
        "prerequisites",
        "learning objectives",
        "content type",
        "products & technologies",
        "module map",
        "difficulty level",
        "environment",
        "infrastructure requirements",
    ],
    "optional_design_sections": [
        "assessment strategy",
    ],
    "required_outline_sections": [
        "brief overview",
        "audience and time",
        "learning objectives",
        "lab structure",
        "key takeaways",
    ],
    "products": [],
    "initiative_jira_keys": {
        "rh1_2027": "RHDPCD-2029",
        "summit_2027": "RHDPCD-2030",
        "content_dev_labs": "RHDPCD-2031",
        "content_dev_blogs": "RHDPCD-2032",
        "content_dev_interactive": "RHDPCD-2033",
        "_default": "RHDPCD-2031",
    },
    "provisioning_time_estimates": {
        "shared-cluster": 5,
        "per-student": 25,
        "cnv-pool": 20,
    },
    "cost_hourly_rate_per_vcpu": 0.05,
}


@lru_cache(maxsize=1)
def load_policy() -> dict:
    if POLICY_PATH.exists():
        try:
            data = yaml.safe_load(POLICY_PATH.read_text())
            if isinstance(data, dict):
                logger.info("Loaded validation policy from %s", POLICY_PATH)
                merged = {**_FALLBACK_POLICY, **data}
                return merged
        except Exception as e:
            logger.warning("Failed to parse %s: %s — using fallback", POLICY_PATH, e)
    else:
        logger.info("Policy file %s not found — using fallback defaults", POLICY_PATH)
    return dict(_FALLBACK_POLICY)
