"""Validation data models."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


class CheckResult(BaseModel):
    check_id: str
    group: str
    status: CheckStatus
    message: str
    field: Optional[str] = None


class AutoComputedFields(BaseModel):
    peak_environments: Optional[int] = None
    cost_per_run_est: Optional[float] = None
    provisioning_time_min: Optional[int] = None


class ValidationRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class ValidationResponse(BaseModel):
    passed: bool
    results: list[CheckResult]
    auto_computed: Optional[AutoComputedFields] = None
    commit_sha: Optional[str] = None
