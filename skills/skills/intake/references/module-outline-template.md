# Module Outline Template

Template for per-module outlines in `publishing-house/spec/modules/`. Each module gets its
own file: `module-01-<short-title>.md`, `module-02-<short-title>.md`, etc.

Granularity scales with complexity:
- Simple module (single concept, guided walkthrough): ~80-120 lines
- Medium module (multiple sections, some exploration): ~120-200 lines
- Complex module (multiple demos, infrastructure changes): ~200-300 lines

---

## Template

```markdown
# Module N: [Title]

## Brief Overview

[3-4 sentences setting context. What problem does this module address?
How does it connect to previous modules? What will the learner accomplish?]

## Audience and Time

- **Target personas:** [e.g., platform engineers, developers]
- **Prerequisites:** [what they need from prior modules or general knowledge]
- **Estimated duration:** [total time for this module]

## Learning Objectives

<!-- Module-level learning objectives. Map back to design spec objectives. Use action verbs. -->
- [Objective 1 — action verb + specific outcome]
- [Objective 2 — action verb + specific outcome]

## Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1       | [Name] | [X min] |
| 2       | [Name] | [X min] |
| 3       | [Name] | [X min] |

## Detailed Steps

### Section 1: [Title]

1. [Specific step — what to do, where to go]
2. [Next step — include commands if applicable]
3. [Observation step — what they should see]
4. ...

### Section 2: [Title]

5. [Steps continue numbering across sections]
6. ...

## Key Takeaways

- [Concept 1 reinforced by this module]
- [Concept 2]
- [How this connects to the next module]

## Infrastructure Notes

<!-- Optional — only include if this module has specific infrastructure requirements. -->

- [Requirement or configuration detail]
```

---

## Examples of Good Step Granularity

**Too vague (bad):**
> 3. Configure the application for high availability

**Right level (good):**
> 3. Open the deployment configuration:
>    `oc edit deployment/my-app -n demo`
> 4. Set replicas to 3 under `spec.replicas`
> 5. Save and exit. Verify pods are scaling:
>    `oc get pods -n demo -w`
> 6. Observe 3 pods reaching Ready state (takes ~30 seconds)

The outline should give the writer agent enough to work with, but not write the
actual AsciiDoc content.
