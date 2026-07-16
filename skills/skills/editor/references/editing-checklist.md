# Publishing House Editing Checklist

Additional editorial checks the editor agent performs beyond what `showroom:verify-content`
covers. These are PH-specific quality gates.

## Spec Alignment Checks

These checks verify the content matches the approved spec. `showroom:verify-content`
does not know about the PH spec — only the editor agent does.

### SA-1: Outline Coverage
- Every section in the module outline has a corresponding section in the content
- No major content was added that isn't in the outline (scope creep)
- Section ordering follows the outline's lab structure

### SA-2: Learning Objectives Match
- Each module-level learning objective has corresponding content (hands-on exercise, explanatory section, or observable outcome)
- No objectives in the outline are missing from the content
- No major content exists that doesn't map to an objective (possible scope creep)

### SA-3: Duration Alignment
- Content depth is appropriate for the estimated duration in the outline
- A 15-minute module should not have 45 minutes of content (or vice versa)
- Flag modules that seem significantly over/under the time estimate

### SA-4: Cross-Module Consistency
- Terminology is consistent across modules (same term for the same concept)
- Prerequisites mentioned in later modules were covered in earlier modules
- Story/scenario continuity — the business context flows between modules
- No contradictions between modules

## Red Hat Style Additions

Beyond the Red Hat style checks in `showroom:verify-content`:

### RS-1: Product Name Accuracy
- Official Red Hat product names used consistently
- Cross-reference against products listed in `publishing-house/spec/design.md`
- First mention in each module should use the full product name

### RS-2: Version Consistency
- Version references match the spec's infrastructure requirements
- No mixed version references (e.g., OCP 4.14 in one module, 4.15 in another)

## Review Output Format

The editor produces a review report at `publishing-house/reviews/editing-review-module-NN.md`:

```markdown
# Editorial Review — Module N: [Title]

## showroom:verify-content Results

[Findings table from verify-content, grouped by severity]

## Spec Alignment

| Check | Status | Notes |
|-------|--------|-------|
| SA-1: Outline Coverage | PASS/FAIL | [details] |
| SA-2: Learning Objectives | PASS/FAIL | [details] |
| SA-3: Duration Alignment | PASS/FAIL | [details] |
| SA-4: Cross-Module Consistency | PASS/FAIL | [details] |

## Red Hat Style

| Check | Status | Notes |
|-------|--------|-------|
| RS-1: Product Names | PASS/FAIL | [details] |
| RS-2: Version Consistency | PASS/FAIL | [details] |

## Summary

- Critical issues: N
- High issues: N
- Medium issues: N
- Low issues: N

## Recommended Actions

1. [Specific action with file and line reference]
2. ...
```
