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
