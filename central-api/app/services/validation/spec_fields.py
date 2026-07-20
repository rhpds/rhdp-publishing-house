"""Group A — Required spec.yaml field checks."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    project = spec_data.get("project", {})
    spec = spec_data.get("spec", {})
    env = spec.get("environment", {})

    required = [
        ("A-01", "spec.title", spec.get("title")),
        ("A-02", "project.slug", project.get("slug")),
        ("A-03", "project.content_type", project.get("content_type")),
        ("A-04", "spec.audience", spec.get("audience")),
        ("A-05", "spec.modules", spec.get("modules")),
        ("A-06", "spec.learning_objectives", spec.get("learning_objectives")),
        ("A-07", "spec.environment.topology", env.get("topology")),
        ("A-08", "spec.environment.ocp_version", env.get("ocp_version")),
    ]

    for check_id, field, value in required:
        if value is None or value == "" or value == []:
            results.append(CheckResult(
                check_id=check_id, group="A", status=CheckStatus.FAIL,
                message=f"{field} is required but missing or empty",
                field=field,
            ))
        else:
            results.append(CheckResult(
                check_id=check_id, group="A", status=CheckStatus.PASS,
                message=f"{field} is set",
                field=field,
            ))

    ocp_version = env.get("ocp_version", "")
    minimum = policy.get("ocp_version_minimum", "4.20")
    if ocp_version and minimum:
        try:
            current = [int(x) for x in str(ocp_version).split(".")]
            min_ver = [int(x) for x in minimum.split(".")]
            if current < min_ver:
                for r in results:
                    if r.check_id == "A-08":
                        r.status = CheckStatus.FAIL
                        r.message = f"OCP {ocp_version} is below minimum {minimum}"
        except ValueError:
            pass

    return results
