#!/usr/bin/env python3
"""
ph-check.py — Publishing House local compliance checker.
Runs deterministic checks against the project repo.
Policy data (OCP version, vocabulary) fetched from Central API, cached 24h.

Usage:
  python publishing-house/tools/ph-check.py              # Run all checks
  python publishing-house/tools/ph-check.py --offline    # Force stale-cache path (air-gapped)
  python publishing-house/tools/ph-check.py --verbose    # Show all pass results too
"""

import sys
import os
import re
import json
import argparse
import datetime
import ssl
import urllib.request
import urllib.error
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

CACHE_DIR = Path.home() / ".cache" / "ph-check"
CACHE_TTL_HOURS = 24

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_AI_KEYWORDS = {"ai", "rhoai", "openshift ai", "maas", "granite", "instructlab",
                "ollama", "llm", "inference", "model serving", "generative"}
_VAGUE_EGRESS = {"internet", "any public ip", "any ip", "anywhere", "cloud", "external"}


def find_repo_root():
    p = Path.cwd()
    while p != p.parent:
        if (p / "catalog-info.yaml").exists():
            return p
        p = p.parent
    return None


def get_central_url(root):
    auth_path = Path(os.path.expanduser("~/.config/publishing-house/ph.json"))
    if auth_path.exists():
        creds = json.loads(auth_path.read_text())
        url = creds.get("central", "")
        if url:
            return url.rstrip("/")
    return ""


def log(msg, level="INFO"):
    symbols = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ ", "SKIP": "⏭️ "}
    print(f"{symbols.get(level, '  ')} [{level}] {msg}")


def fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def load_cache(key):
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None, 999
    try:
        data = json.loads(path.read_text())
        cached_at = datetime.datetime.fromisoformat(data["cached_at"])
        age_hours = (datetime.datetime.now() - cached_at).total_seconds() / 3600
        return data["payload"], age_hours
    except Exception:
        return None, 999


def save_cache(key, payload):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({
        "cached_at": datetime.datetime.now().isoformat(),
        "payload": payload
    }))


def get_policy(key, central_url, endpoint, offline=False):
    cached, age = load_cache(key)
    if cached and age < CACHE_TTL_HOURS:
        return cached, None
    if offline:
        if cached:
            return cached, f"offline mode — using {age:.0f}h old cache"
        return None, f"offline mode and no cache for {key}"
    if not central_url:
        if cached:
            return cached, "no Central URL configured, using cache"
        return None, "no Central URL configured and no cache"
    data = fetch_json(f"{central_url}{endpoint}")
    if data:
        save_cache(key, data)
        return data, None
    elif cached:
        warn = f"Central unreachable, using {age:.0f}h old cache"
        if age > 48:
            return None, f"cache too stale ({age:.0f}h) — reconnect to Central"
        return cached, warn if age > CACHE_TTL_HOURS else None
    return None, "Central unreachable and no local cache"


def load_spec(root):
    path = root / "publishing-house" / "spec.yaml"
    if not path.exists():
        return None, "publishing-house/spec.yaml not found"
    try:
        return yaml.safe_load(path.read_text()), None
    except Exception as e:
        return None, f"spec.yaml parse error: {e}"


def load_design_md(root):
    path = root / "publishing-house" / "spec" / "design.md"
    if not path.exists():
        return None
    return path.read_text()


def extract_module_map_from_design(design_text):
    """Parse the Module Map table from design.md. Returns list of {title, duration}."""
    modules = []
    in_table = False
    for line in design_text.splitlines():
        if "module map" in line.lower():
            in_table = True
            continue
        if in_table:
            if line.startswith("|") and "---" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0].strip().isdigit():
                    modules.append({"title": cells[1].strip(), "duration": cells[2].strip() if len(cells) > 2 else ""})
            elif in_table and not line.startswith("|") and line.strip():
                break
    return modules


def run_checks(root, central_url, offline=False, verbose=False):
    passed = failed = warned = 0

    def record(check, level, msg):
        nonlocal passed, failed, warned
        if level == "PASS":
            passed += 1
            if verbose:
                log(f"{check}: {msg}", level)
        elif level == "FAIL":
            failed += 1
            log(f"{check}: {msg}", level)
        elif level in ("WARN", "SKIP"):
            warned += 1
            log(f"{check}: {msg}", level)

    data, err = load_spec(root)
    if err:
        log(f"Cannot load spec: {err}", "FAIL")
        return 1

    spec = data.get("spec", {})
    project = data.get("project", {})
    env = spec.get("environment", {})
    approval = data.get("approval_checklist", {})

    modules_in_spec = spec.get("modules", [])
    objectives = spec.get("learning_objectives", [])
    ocp_version = env.get("ocp_version", "")
    topology = env.get("topology", "")
    products_text = " ".join(str(v) for v in project.values()).lower()

    design_text = load_design_md(root)
    modules_dir = root / "publishing-house" / "spec" / "modules"
    content_dir = root / "content" / "modules" / "ROOT" / "pages"

    log(f"Project: {project.get('slug', '?')} | Modules: {len(modules_in_spec)} | Objectives: {len(objectives)}")
    print()

    # ── Existing checks ───────────────────────────────────────────────────────

    if content_dir.exists():
        content_files = list(content_dir.glob("module-*.adoc"))
        expected = len(modules_in_spec)
        actual = len(content_files)
        if expected == 0:
            record("module-count", "SKIP", "No modules in spec yet (intake phase)")
        elif actual == 0:
            record("module-count", "SKIP", f"Spec declares {expected} modules — content not written yet")
        elif actual == expected:
            record("module-count", "PASS", f"{actual} modules match spec")
        else:
            record("module-count", "WARN", f"Spec declares {expected} modules, {actual} written so far")
    else:
        record("module-count", "SKIP", "content/modules/ROOT/pages/ not found — no content yet")

    nav = root / "content" / "modules" / "ROOT" / "nav.adoc"
    if nav.exists():
        record("nav-adoc", "PASS", "nav.adoc found")
        nav_content = nav.read_text()
        missing_from_nav = [m.get("id", "") for m in modules_in_spec
                            if m.get("id") and m["id"] not in nav_content]
        if missing_from_nav:
            record("nav-modules", "WARN", f"Modules not yet in nav.adoc: {', '.join(missing_from_nav)}")
        elif modules_in_spec:
            record("nav-modules", "PASS", "All spec modules referenced in nav.adoc")
    else:
        record("nav-adoc", "SKIP", "nav.adoc not found — content not yet created")

    antora = root / "content" / "antora.yml"
    if antora.exists():
        record("antora-yml", "PASS", "antora.yml found")
    else:
        record("antora-yml", "SKIP", "antora.yml not found — not yet created")

    if objectives and content_dir.exists():
        adoc_files = list(content_dir.glob("*.adoc"))
        if adoc_files:
            all_content = " ".join(f.read_text() for f in adoc_files).lower()
            missing_obj = [obj[:60] for obj in objectives
                           if not any(w in all_content for w in obj.lower().split() if len(w) > 4)]
            if missing_obj:
                record("learning-objectives", "FAIL",
                       f"{len(missing_obj)} objectives not found in content: {'; '.join(missing_obj[:2])}")
            else:
                record("learning-objectives", "PASS",
                       f"All {len(objectives)} learning objectives referenced in content")
        else:
            record("learning-objectives", "SKIP", "No content files yet")
    elif not objectives:
        record("learning-objectives", "SKIP", "No learning objectives in spec yet")
    else:
        record("learning-objectives", "SKIP", "No content directory yet")

    policy, warn = get_policy("ocp-policy", central_url, "/api/v1/reference/ocp-policy", offline)
    if warn:
        log(f"OCP policy: {warn}", "WARN")
    if policy and ocp_version:
        minimum = policy.get("ocp_version_minimum", "4.20")
        try:
            if [int(x) for x in ocp_version.split(".")] >= [int(x) for x in minimum.split(".")]:
                record("ocp-version", "PASS", f"OCP {ocp_version} meets minimum {minimum}")
            else:
                record("ocp-version", "FAIL", f"OCP {ocp_version} below minimum {minimum}")
        except ValueError:
            record("ocp-version", "WARN", f"Could not parse OCP version '{ocp_version}'")
    elif not ocp_version:
        record("ocp-version", "SKIP", "OCP version not set in spec yet")


    # ── design.md placeholder check ──────────────────────────────────────────

    if design_text:
        import re as _re2
        _design_clean = _re2.sub(r'<!--.*?-->', '', design_text, flags=_re2.DOTALL)
        _ph_pattern = _re2.compile(
            r'\[(?:Project Title|XX\s*min|Module title|Action verb|'
            r'Official Red Hat|PLACEHOLDER|TODO|REPLACE_ME|TBD|'
            r'specific,?\s*measurable)[^\]]*\]',
            _re2.IGNORECASE
        )
        found_ph = _ph_pattern.findall(_design_clean)
        first_line = design_text.split('\n')[0] if design_text else ''
        if found_ph:
            record('design-placeholders', 'FAIL',
                   f"Unfilled template placeholders in design.md: {', '.join(found_ph[:3])}")
        elif '# [Project Title]' in first_line or (first_line.startswith('# [') and ']' in first_line):
            record('design-placeholders', 'FAIL',
                   'H1 title in design.md is still a placeholder — replace with actual project name')
        else:
            record('design-placeholders', 'PASS', 'No unfilled placeholders in design.md')
    else:
        record('design-placeholders', 'SKIP', 'design.md not yet written')


    # ── Part 3: Infrastructure field checks ───────────────────────────────────

    # Sizing — if any field is set, all four must be set
    sizing_fields = ["worker_count", "worker_cpu", "worker_ram_gb", "worker_disk_gb"]
    sizing_values = {f: env.get(f) for f in sizing_fields}
    any_set = any(v is not None for v in sizing_values.values())
    all_set = all(v is not None for v in sizing_values.values())
    if any_set and not all_set:
        missing_sizing = [f for f, v in sizing_values.items() if v is None]
        record("infra-sizing", "FAIL",
               f"Partial sizing — missing fields: {', '.join(missing_sizing)}. Set all four or none.")
    elif all_set:
        record("infra-sizing", "PASS",
               f"Sizing: {sizing_values['worker_count']} workers, "
               f"{sizing_values['worker_cpu']} vCPU, {sizing_values['worker_ram_gb']}GB RAM")
    else:
        record("infra-sizing", "SKIP", "Cluster sizing not set yet (fill in during spec refinement)")

    # Concurrent users — required for per-student and cnv-pool
    if topology in ("per-student", "cnv-pool"):
        max_users = env.get("max_concurrent_users")
        if max_users is None:
            record("concurrent-users", "FAIL",
                   f"topology={topology} requires max_concurrent_users to be set (Q14)")
        elif max_users > 0:
            record("concurrent-users", "PASS", f"Max concurrent users: {max_users}")
        else:
            record("concurrent-users", "FAIL", "max_concurrent_users must be > 0")
    else:
        record("concurrent-users", "SKIP", f"topology={topology or 'not set'} — concurrent users not required")

    # AI/MaaS requirement
    ai_req = env.get("ai_requirement", "")
    ai_tier = env.get("ai_model_tier", "")
    ai_justification = env.get("ai_justification", "")
    all_text = (str(spec) + " " + str(project)).lower()
    ai_mentioned = any(kw in all_text for kw in _AI_KEYWORDS)

    if ai_mentioned and not ai_req:
        record("ai-requirement", "FAIL",
               "AI/LLM keyword detected in spec but spec.environment.ai_requirement not set. "
               "Answer Q15: maas / gpu / none.")
    elif ai_req == "gpu" and not ai_justification:
        record("ai-requirement", "FAIL",
               "ai_requirement=gpu requires ai_justification explaining why MaaS is insufficient")
    elif ai_tier == "frontier" and not ai_justification:
        record("ai-requirement", "FAIL",
               "ai_model_tier=frontier requires ai_justification explaining why open-source is insufficient")
    elif ai_req in ("maas", "gpu", "none") or not ai_mentioned:
        if ai_req:
            record("ai-requirement", "PASS",
                   f"AI: {ai_req}" + (f" / {ai_tier}" if ai_tier else "") +
                   (f" ({env.get('ai_model_name', '')})" if env.get("ai_model_name") else ""))
        else:
            record("ai-requirement", "SKIP", "No AI keywords detected in spec")

    # AAP version
    if "ansible automation platform" in all_text or " aap " in all_text or "aap2." in all_text:
        aap_version = env.get("aap_version", "")
        if not aap_version:
            record("aap-version", "FAIL",
                   "AAP detected in products but spec.environment.aap_version not set (Q16)")
        else:
            record("aap-version", "PASS", f"AAP version: {aap_version}")
    else:
        record("aap-version", "SKIP", "AAP not in products")

    # External services — vague entries
    external_services = env.get("external_services", [])
    if external_services:
        vague = [s for s in external_services
                 if any(v in str(s).lower() for v in _VAGUE_EGRESS)]
        if vague:
            record("external-services", "FAIL",
                   f"Vague external service entries — use specific names (e.g. github.com): {vague}")
        else:
            record("external-services", "PASS",
                   f"{len(external_services)} named external service(s): {', '.join(str(s) for s in external_services[:3])}")
    else:
        record("external-services", "PASS", "No external services — auto-approved")

    # Non-GA products + access plan
    non_ga = env.get("non_ga_products", [])
    non_ga_plan = env.get("non_ga_access_plan", "")
    if non_ga:
        if not non_ga_plan:
            record("non-ga-products", "FAIL",
                   f"Non-GA products listed but no access plan: {non_ga}. Answer Q18 follow-up.")
        else:
            record("non-ga-products", "WARN",
                   f"Non-GA products present ({len(non_ga)}) — routes to infra review. "
                   f"Access plan: {non_ga_plan[:60]}")
    else:
        record("non-ga-products", "PASS", "No non-GA products — auto-approved")

    # ── Part 4: Cross-validation (CV-1 to CV-5) ───────────────────────────────

    if design_text and modules_dir.exists():
        design_modules = extract_module_map_from_design(design_text)
        outline_files = sorted(modules_dir.glob("module-*.md"))

        # CV-1: Module count
        if len(design_modules) != len(outline_files):
            record("cv-module-count", "FAIL",
                   f"CV-1: design.md Module Map has {len(design_modules)} modules "
                   f"but found {len(outline_files)} outline files in spec/modules/")
        else:
            record("cv-module-count", "PASS",
                   f"CV-1: {len(design_modules)} modules in design.md match {len(outline_files)} outlines")

        # CV-2: Module title alignment (slug match)
        if design_modules and outline_files:
            mismatches = []
            for i, dm in enumerate(design_modules):
                slug = re.sub(r"[^a-z0-9]+", "-", dm["title"].lower()).strip("-")
                expected_prefix = f"module-{i+1:02d}-"
                if i < len(outline_files):
                    fname = outline_files[i].name
                    if not fname.startswith(expected_prefix):
                        mismatches.append(f"Module {i+1}: expected {expected_prefix}*, found {fname}")
            if mismatches:
                record("cv-module-titles", "WARN",
                       f"CV-2: {len(mismatches)} title/filename mismatch(es): {mismatches[0]}")
            else:
                record("cv-module-titles", "PASS", "CV-2: Module title prefixes align with outline files")

        # CV-3: Learning objectives coverage in outlines
        if objectives and outline_files:
            all_outline_text = " ".join(f.read_text().lower() for f in outline_files)
            uncovered = []
            for obj in objectives:
                keywords = [w for w in obj.lower().split() if len(w) > 4]
                if keywords and not any(kw in all_outline_text for kw in keywords[:3]):
                    uncovered.append(obj[:60])
            if uncovered:
                record("cv-objectives-coverage", "WARN",
                       f"CV-3: {len(uncovered)} objective(s) not found in module outlines (may use synonyms): "
                       + uncovered[0])
            else:
                record("cv-objectives-coverage", "PASS",
                       f"CV-3: All {len(objectives)} objectives traceable to module outlines")

        # CV-4: Duration consistency
        if design_modules and outline_files:
            design_durations = []
            for dm in design_modules:
                m = re.search(r"(\d+)\s*(min|hour|hr)", dm.get("duration", "").lower())
                if m:
                    val = int(m.group(1))
                    design_durations.append(val if "min" in m.group(2) else val * 60)

            outline_durations = []
            for of in outline_files:
                text = of.read_text()
                m = re.search(r"(\d+)\s*(min|hour|hr)", text.lower())
                if m:
                    val = int(m.group(1))
                    outline_durations.append(val if "min" in m.group(2) else val * 60)

            if design_durations and outline_durations:
                design_total = sum(design_durations)
                outline_total = sum(outline_durations)
                if design_total > 0 and abs(design_total - outline_total) / design_total > 0.2:
                    record("cv-duration", "WARN",
                           f"CV-4: Duration mismatch — design.md sums to {design_total}min, "
                           f"outlines sum to {outline_total}min (>20% difference)")
                else:
                    record("cv-duration", "PASS",
                           f"CV-4: Durations consistent (design: ~{design_total}min, outlines: ~{outline_total}min)")
            else:
                record("cv-duration", "SKIP", "CV-4: Could not parse durations from design.md or outlines")

        # CV-5: spec.yaml modules vs design.md Module Map
        spec_titles = [m.get("title", "") for m in modules_in_spec]
        design_titles = [m["title"] for m in design_modules]
        if spec_titles and design_titles:
            only_in_spec = set(spec_titles) - set(design_titles)
            only_in_design = set(design_titles) - set(spec_titles)
            if only_in_spec or only_in_design:
                record("cv-spec-alignment", "FAIL",
                       f"CV-5: spec.yaml modules differ from design.md Module Map. "
                       + (f"In spec only: {only_in_spec}. " if only_in_spec else "")
                       + (f"In design only: {only_in_design}." if only_in_design else ""))
            else:
                record("cv-spec-alignment", "PASS",
                       f"CV-5: spec.yaml module list matches design.md Module Map ({len(spec_titles)} modules)")
        else:
            record("cv-spec-alignment", "SKIP",
                   "CV-5: modules not yet set in spec.yaml or design.md has no Module Map")

    elif not design_text:
        record("cross-validation", "SKIP", "design.md not written yet — CV-1 to CV-5 skipped")
    elif not modules_dir.exists():
        record("cross-validation", "SKIP", "spec/modules/ not yet created — CV-1 to CV-5 skipped")

    # ── Part 5: Approval checklist checks ─────────────────────────────────────

    cl = approval.get("content_lead", {})

    prereq_verifiable = cl.get("prerequisites_verifiable")
    if prereq_verifiable is None:
        record("approval-prerequisites", "FAIL",
               "Q22 not answered: approval_checklist.content_lead.prerequisites_verifiable must be true or false")
    else:
        record("approval-prerequisites", "PASS",
               f"Prerequisites verifiable: {prereq_verifiable}")

    assessment = cl.get("assessment_strategy", "")
    if not assessment:
        record("approval-assessment", "FAIL",
               "Q23 not answered: approval_checklist.content_lead.assessment_strategy must be non-empty")
    else:
        record("approval-assessment", "PASS",
               f"Assessment strategy: {assessment[:60]}...")

    differentiation = cl.get("differentiation", "")
    if not differentiation:
        record("approval-differentiation", "FAIL",
               "Q24 not answered: approval_checklist.content_lead.differentiation must be non-empty")
    else:
        record("approval-differentiation", "PASS",
               f"Differentiation: {differentiation[:60]}...")

    # ── Summary ────────────────────────────────────────────────────────────────

    print()
    print("─" * 50)
    total = passed + failed + warned
    print(f"Results: {passed} passed, {failed} failed, {warned} skipped/warned")
    if failed > 0:
        print("❌ Compliance check FAILED — fix errors before pushing to Central")
        return 1
    elif warned > 0:
        print("⚠️  Compliance check PASSED with warnings")
        return 0
    else:
        print("✅ All checks PASSED")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Publishing House compliance checker")
    parser.add_argument("--offline", action="store_true",
                        help="Force stale-cache path (no Central calls)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show passing checks too")
    args = parser.parse_args()

    root = find_repo_root()
    if not root:
        print("ERROR: Not a Publishing House project — catalog-info.yaml not found.", file=sys.stderr)
        sys.exit(2)

    spec_path = root / "publishing-house" / "spec.yaml"
    if not spec_path.exists():
        print("ERROR: publishing-house/spec.yaml not found.", file=sys.stderr)
        sys.exit(2)

    central_url = get_central_url(root)
    sys.exit(run_checks(root, central_url, offline=args.offline, verbose=args.verbose))


if __name__ == "__main__":
    main()
