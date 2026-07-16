# Publishing House Writing Standards

Standards for the writer agent when generating content via showroom skills.
These supplement the showroom skill's own rules — do not duplicate them.

## Module Outline as Starting Point

The approved module outline in `publishing-house/spec/modules/module-NN-*.md` is the
writer's primary input. When generating new content, every section in the outline should
appear in the generated content. Do not add major sections not in the outline. Do not
skip sections that are in the outline.

If the outline is ambiguous or incomplete, ask the user for clarification rather than
guessing.

**However:** Both the outline and any existing content may have been modified by a human
since the last agent run. Always read the current version of files from disk. Human edits
take precedence — build on what exists rather than overwriting it.

## Content Type Routing

| `project.type` | Showroom Skill | Content Structure |
|----------------|----------------|-------------------|
| `workshop`/`lab` | `showroom:create-lab` | Exercises with verification sections |
| `demo` | `showroom:create-demo` | Know/Show presenter-led format |

## Showroom Skill Invocation (ph_payload format)

### For `showroom:create-lab`

**First module:**
```
showroom:create-lab content/
ph_payload:
  target_dir: content/modules/ROOT/pages/
  mode: new
  spec:
    lab_name: <from design.md project title>
    audience: <from design.md target audience>
    learning_objectives: <from module outline Learning Objectives as list>
    business_scenario: <from design.md problem statement>
    duration: <from module outline Audience and Time>
    module_outline: |
      <full module outline content>
    env:
      ocp_version: <from spec.yaml or design spec>
      attributes: <from module outline Infrastructure Notes>
```

**Subsequent modules:**
```
showroom:create-lab content/
ph_payload:
  target_dir: content/modules/ROOT/pages/
  mode: continue
  previous_module: <filename of the previous module>
  spec:
    lab_name: <same as first module>
    learning_objectives: <from THIS module's outline>
    module_outline: |
      <THIS module's detailed steps only>
```

## Module Numbering

Modules are numbered sequentially in the Showroom content directory:
- First module: `03-module-01-<title>.adoc`
- Second module: `04-module-02-<title>.adoc`
- Pattern: `0{N+2}-module-{NN}-<title>.adoc`

The showroom skills handle this numbering automatically.

## Post-Generation Checklist

1. All sections from the module outline are represented in the generated content
2. Navigation (`nav.adoc`) was updated with the new module
3. The generated file exists at the expected path
4. No hardcoded credentials, URLs, or environment-specific values (use `{attributes}`)
