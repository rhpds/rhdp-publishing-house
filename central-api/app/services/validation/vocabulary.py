"""Group H — Controlled vocabulary checks."""
from .models import CheckResult, CheckStatus


def run_checks(spec_data: dict, policy: dict) -> list[CheckResult]:
    results = []
    spec = spec_data.get("spec", {})
    project = spec_data.get("project", {})

    valid_audiences = [a.lower() for a in policy.get("valid_audiences", [])]
    valid_types = [t.lower() for t in policy.get("valid_content_types", [])]
    products_list = policy.get("products", [])

    # H-01: Content type in vocabulary
    content_type = project.get("content_type", "")
    if content_type:
        if content_type.lower() in valid_types:
            results.append(CheckResult(
                check_id="H-01", group="H", status=CheckStatus.PASS,
                message=f"content_type '{content_type}' is valid",
                field="spec.content_type",
            ))
        else:
            results.append(CheckResult(
                check_id="H-01", group="H", status=CheckStatus.FAIL,
                message=f"content_type '{content_type}' not in: {', '.join(valid_types)}",
                field="spec.content_type",
            ))
    else:
        results.append(CheckResult(
            check_id="H-01", group="H", status=CheckStatus.SKIP,
            message="content_type not set",
            field="spec.content_type",
        ))

    # H-02: Audience in vocabulary
    audience = spec.get("audience", "")
    if audience:
        if audience.lower() in valid_audiences:
            results.append(CheckResult(
                check_id="H-02", group="H", status=CheckStatus.PASS,
                message=f"audience '{audience}' is valid",
                field="spec.audience",
            ))
        else:
            results.append(CheckResult(
                check_id="H-02", group="H", status=CheckStatus.FAIL,
                message=f"audience '{audience}' not in: {', '.join(valid_audiences)}",
                field="spec.audience",
            ))
    else:
        results.append(CheckResult(
            check_id="H-02", group="H", status=CheckStatus.SKIP,
            message="audience not set",
            field="spec.audience",
        ))

    # H-04: Cloud provider in vocabulary
    valid_cloud_providers = [c.lower() for c in policy.get("valid_cloud_providers", ["cnv", "aws"])]
    cloud_provider = spec.get("environment", {}).get("cloud_provider", "")
    if cloud_provider:
        if cloud_provider.lower() in valid_cloud_providers:
            results.append(CheckResult(
                check_id="H-04", group="H", status=CheckStatus.PASS,
                message=f"cloud_provider '{cloud_provider}' is valid",
                field="spec.environment.cloud_provider",
            ))
        else:
            results.append(CheckResult(
                check_id="H-04", group="H", status=CheckStatus.FAIL,
                message=f"cloud_provider '{cloud_provider}' not in: {', '.join(valid_cloud_providers)}",
                field="spec.environment.cloud_provider",
            ))
    else:
        results.append(CheckResult(
            check_id="H-04", group="H", status=CheckStatus.SKIP,
            message="cloud_provider not set",
            field="spec.environment.cloud_provider",
        ))

    # H-05: Cluster type in vocabulary
    valid_cluster_types = [c.lower() for c in policy.get("valid_cluster_types", ["sno", "multinode"])]
    cluster_type = spec.get("environment", {}).get("cluster_type", "")
    if cluster_type:
        if cluster_type.lower() in valid_cluster_types:
            results.append(CheckResult(
                check_id="H-05", group="H", status=CheckStatus.PASS,
                message=f"cluster_type '{cluster_type}' is valid",
                field="spec.environment.cluster_type",
            ))
        else:
            results.append(CheckResult(
                check_id="H-05", group="H", status=CheckStatus.FAIL,
                message=f"cluster_type '{cluster_type}' not in: {', '.join(valid_cluster_types)}",
                field="spec.environment.cluster_type",
            ))
    else:
        results.append(CheckResult(
            check_id="H-05", group="H", status=CheckStatus.SKIP,
            message="cluster_type not set",
            field="spec.environment.cluster_type",
        ))

    # H-03: Product names against known list (if policy has products)
    if products_list:
        spec_products = project.get("products", [])
        if spec_products:
            known_names = set()
            for p in products_list:
                known_names.add(p.get("name", "").lower())
                for alias in p.get("aliases", []):
                    known_names.add(alias.lower())

            unrecognized = [p for p in spec_products if p.lower() not in known_names]
            if unrecognized:
                results.append(CheckResult(
                    check_id="H-03", group="H", status=CheckStatus.WARN,
                    message=f"Unrecognized product names: {', '.join(unrecognized[:5])}. "
                            "Use official Red Hat product names.",
                    field="project.products",
                ))
            else:
                results.append(CheckResult(
                    check_id="H-03", group="H", status=CheckStatus.PASS,
                    message=f"All {len(spec_products)} products recognized",
                    field="project.products",
                ))
        else:
            results.append(CheckResult(
                check_id="H-03", group="H", status=CheckStatus.SKIP,
                message="No products listed",
                field="project.products",
            ))
    else:
        results.append(CheckResult(
            check_id="H-03", group="H", status=CheckStatus.SKIP,
            message="No product vocabulary in policy — skipping product name check",
            field="project.products",
        ))

    return results
