# Intake Questions — Canonical List

Ask these questions **exactly as written**, **in this order**, **one at a time**.
Skip any question whose `spec.yaml field` already has a value.
After each answer, immediately write to spec.yaml.

---

## Q1: Main Goal

> **What will someone be able to DO after completing this?** Be specific — a concrete, measurable outcome.

- **spec.yaml field:** `spec.title` (derive a short title from the goal)
- **Also captures:** the problem statement for design.md

## Q2: Target Audience

> **Who is this for?** What's their role, experience level, and what background knowledge should they have?

- **spec.yaml field:** `spec.audience` (one of: `beginner`, `intermediate`, `advanced`)

## Q3: Products and Technologies

> **Which Red Hat products and technologies are involved?** Include full product names and versions if known.

- **Used in:** design.md Products & Technologies section

## Q4: Content Type (if not set)

> **Is this a hands-on lab, a guided demo, or a workshop?**

- **Skip if:** `project.content_type` is already set
- **spec.yaml field:** `project.content_type` (one of: `lab`, `demo`, `workshop`)

## Q5: Showroom Type (if not set)

> **Will this be a standard Showroom lab (Classic) or an embedded Zero-Touch experience?**

- **Skip if:** `project.showroom_type` is already set
- **spec.yaml field:** `project.showroom_type` (one of: `classic`, `zero_touch`)

## Q6: Environment

> **What does the learner start with, and what needs to be pre-configured by automation?** For example: a shared OpenShift cluster with operators pre-installed, or a per-student cluster with nothing installed.

- **spec.yaml field:** `spec.environment.topology` (one of: `shared-cluster`, `per-student`, `cnv-pool`)
- **Also captures:** environment details for design.md

## Q7: Total Duration

> **How long should this take end to end?** Consider the complexity of what you described.

- **spec.yaml field:** `spec.duration_hours`

## Q8: Module Structure

> **Let me propose a module breakdown based on what you've described.** [Present proposed modules with titles and estimated durations, 15-45 min each.] **Does this structure work, or would you adjust it?**

- **spec.yaml field:** `spec.modules` (list of `{title, duration_min}`)

## Q9: Module Relationship

> **How do these modules relate to each other?**
> 1. **Sequential** — they build on each other and must be done in order
> 2. **Independent with shared context** — can be done in any order but share a scenario
> 3. **Fully independent** — standalone topics

- **Used in:** design.md Module Map section

## Q10: Difficulty Level

> **What difficulty level best describes this content?** Beginner, intermediate, or advanced?

- **spec.yaml field:** `spec.audience` (update if different from Q2; use a separate `spec.difficulty_level` field if the audience level and difficulty differ)

## Q11: OpenShift Version

> **Which OpenShift version should this target?** For example: 4.17, 4.18, 4.19.

- **spec.yaml field:** `spec.environment.ocp_version`

## Q12: Infrastructure Requirements

> **Let me confirm the infrastructure needs.** Based on what you described:
> - **Base infrastructure:** [propose: ocp4-cluster, ocp-workloads, or cloud-vms-base]
> - **Sizing:** [propose based on complexity — e.g. 6 workers, 8 vCPU, 32GB RAM, 100GB disk]
> - **Cloud provider:** CNV (default) or exception?
> - **Automation approach:** Ansible, GitOps (Helm + ArgoCD), or combo?
>
> **Does this sound right, or should I adjust anything?**

- **spec.yaml fields:** `spec.environment.worker_count`, `worker_cpu`, `worker_ram_gb`, `worker_disk_gb`
- **Used in:** design.md Infrastructure Requirements section

## Q13: Reference Material

> **Do you have any reference material I should work from?** Internal docs, existing labs, recorded demos, architecture diagrams, or blog posts?

- **Used in:** informs design.md content

---

## Infrastructure & Compliance Questions

*Ask Q14–Q18 after Q13. Skip any whose spec.yaml field already has a value.*

## Q14: Concurrent Users

**Ask when:** `topology = per-student` or `topology = cnv-pool`

> **How many students will use this simultaneously at peak?**
> For example: 25 students in a live workshop, or 5 at a time in self-paced access.

- **spec.yaml field:** `spec.environment.max_concurrent_users`
- **Validation:** Required if topology is per-student or cnv-pool. Block if blank.

## Q15: AI / MaaS Requirement

**Ask when:** Any product includes AI/LLM keywords (OpenShift AI, RHOAI, MaaS, Granite, InstructLab, Ollama, LLM, model serving, inference)

> **Does this lab use AI or large language models at runtime?**
>
> - **MaaS** (recommended) — our shared model service. No GPU needed, pre-approved for all labs.
> - **Dedicated GPU** — expensive and scarce. Only if MaaS cannot meet the requirement. Requires full justification.
> - **None** — this lab does not use AI at runtime.

**If they choose MaaS**, ask:
> **Which model tier fits your use case?**
> - **Open-source** (default, auto-approved) — Granite, Llama, Mistral, or similar. Use unless you have a specific reason not to.
> - **Frontier/premium model** — Claude Opus, GPT-4o, or similar. Why is open-source insufficient?

**If they choose frontier**, ask:
> **Why is an open-source model insufficient?** Be specific — what capability, context length, or quality requirement rules out open-source?

- **spec.yaml field:** `spec.environment.ai_requirement` (maas | gpu | none)
- **spec.yaml field:** `spec.environment.ai_model_tier` (open-source | frontier)
- **spec.yaml field:** `spec.environment.ai_model_name` — specific model if known
- **spec.yaml field:** `spec.environment.ai_justification` — required if frontier or gpu

## Q16: AAP Version

**Ask when:** "Ansible Automation Platform" or "AAP" in products

> **Which version of AAP does this require?** (e.g., 2.4, 2.5)

- **spec.yaml field:** `spec.environment.aap_version`
- **Validation:** Required if AAP in products.

## Q17: External Services / Network Egress

> **Does this lab call any external services, APIs, or SaaS products outside the cluster?**
> List each by name. Examples: `github.com`, `registry.access.redhat.com`, a public API endpoint.
> Say "none" if there are no external dependencies.

- **spec.yaml field:** `spec.environment.external_services: []`
- **Validation:** Vague entries ("internet", "any public IP") → rejected. Must be named services.

## Q18: Non-GA Products

**Ask when:** Any product is labeled beta, tech preview, early access, or version is unclear

> **Does this lab use any non-GA products, tech previews, or beta features?**
> If yes: which products, and how will you provide access during lab provisioning?
> (Examples: product team special build, internal registry, license key, entitlement)

- **spec.yaml field:** `spec.environment.non_ga_products: []`
- **spec.yaml field:** `spec.environment.non_ga_access_plan`
- **Validation:** If non_ga_products non-empty, access_plan must be non-empty.

---

## Approval Checklist Questions

*Note: Q19-Q21 were intentionally removed during the Part 5 spec revision (2026-07-14).
They covered manager-facing fields (demand signal, maintenance owner, shelf life) that the
content manager reads directly from the spec rather than collecting as authored fields.
Q22-Q24 numbers are preserved to maintain alignment with the gate validation spec (RHDPCD-170 Parts 3-5).*

*Ask Q22–Q24 before finalizing the spec. These go into approval_checklist in spec.yaml.*

## Q22: Prerequisites Verifiable In-Lab

> **What must the learner know or have done before starting Module 1?**
>
> And separately: can the lab automatically validate those prerequisites when the learner starts?
> For example: a check script that verifies a cluster is already connected, or a pre-flight that confirms credentials exist.

- **design.md section:** `## Prerequisites` (captures the list of prerequisites)
- **spec.yaml field:** `approval_checklist.content_lead.prerequisites_verifiable` (true | false — answers whether validation is possible)

## Q23: Assessment Strategy

> **How will we know the learner successfully completed each module?**
> For each module, describe how success is validated: a verification script, a visible result in the UI, a quiz question, or trust-based (learner self-reports).

- **spec.yaml field:** `approval_checklist.content_lead.assessment_strategy`
- **Validation:** Required. "Trust-based" is acceptable but must be explicit.

## Q24: Differentiation from Existing Content

**Before asking this question, the intake skill MUST:**

1. Read `system.central` from `publishing-house/spec.yaml` to get the Central API URL
2. Build the products list from Q3 answers and audience from Q2
3. Call: `GET {central_url}/api/v1/rcars/overlap?products={products}&audience={audience}&limit=5`
4. Present the results inline before asking the differentiation question

**If RCARS returns matches**, present them to the author:

> I checked the RHDP catalog for similar content. Here's what already exists:
>
> **Top matches:**
> 1. **[display_name]** — [url]
> 2. **[display_name]** — [url]
> 3. **[display_name]** — [url]
>
> **How does your lab specifically differ from these?** What does it cover that these labs don't? What's the unique value for a learner who has already seen one of these?

**If RCARS returns no matches** (empty or overlap_pct < 5%), present:

> I checked the RHDP catalog — no close matches found for your products and audience combination. This looks like genuinely new territory.
>
> **Still, how would you describe what makes this lab unique?** (This helps reviewers understand the positioning.)

**If Central is unreachable** (network error, timeout), fall back gracefully:

> **In your own words: how does this differ from existing content on similar topics?**
> Reference specific existing labs you're aware of, and explain what this adds.

- **spec.yaml field:** `approval_checklist.content_lead.differentiation`
- **spec.yaml field:** `approval_checklist.content_lead.rcars_overlap_pct` — write from RCARS response (or null if unreachable)
- **spec.yaml field:** `approval_checklist.content_lead.rcars_top_matches` — write from RCARS response (or [] if unreachable)
- **Validation:** `differentiation` must be non-empty before intake completes.

---

## Rules

- Ask ONE question at a time. Wait for the answer before asking the next.
- Use the **exact wording** above. Do not rephrase, merge, or reorder questions.
- If the user's answer to one question also answers a later question, mark that later question as answered and skip it.
- After each answer, immediately update `publishing-house/spec.yaml` with the captured value.
- If an answer is vague, ask a single follow-up to clarify before moving on.
- Q14–Q18 are infrastructure gates: if any required field is blank, intake is NOT complete. Do not signal completion to the orchestrator until all required fields are set.
- **Q24 RCARS lookup is mandatory** — always attempt the lookup before asking the differentiation question. Only fall back to the blind question if Central is unreachable.
