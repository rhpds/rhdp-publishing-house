# Content Helpers

Writing and reviewing your Showroom modules can be done manually, or with two optional AI helpers: **writer-helper** and **reviewer-helper**.

!!! info "These helpers are optional"
    You can write and review content manually or with any tool you prefer. If you do use them,
    their output is a starting point — read through everything they produce and verify it yourself
    before marking a workstream complete.

See [Development](development.md) for how content helpers fit into the overall development workflow.

---

## File naming

Whether you write manually or use the writer helper, your `.adoc` files must follow the same naming convention — the helper derives the filename from your outline automatically:

| Outline file | Content file |
|---|---|
| `publishing-house/spec/modules/module-01-pipeline-setup.md` | `content/modules/ROOT/pages/module-01-pipeline-setup.adoc` |
| `publishing-house/spec/modules/module-02-deploy-app.md` | `content/modules/ROOT/pages/module-02-deploy-app.adoc` |

Same filename stem, `.adoc` extension, same position in the sequence. If you write manually, use the same pattern.

---

## Writer Helper

The writer helper generates AsciiDoc content from your module outlines.

### How it works

1. Reads your outline from `publishing-house/spec/modules/module-NN-<slug>.md`
2. Reads your `publishing-house/spec/design.md` and `publishing-house/spec.yaml` for project context
3. Presents a plan — waits for your approval before writing anything
4. Writes `content/modules/ROOT/pages/module-NN-<slug>.adoc` (same filename stem as the outline)
5. Reports any open items: missing images, placeholder text, TODOs
6. Asks you to review the output before marking the module complete

Modules are written one at a time, in order. Each module waits for your approval before starting.

### Index and conclusion

After all modules are complete, the writer helper generates two additional files:

| File | Purpose |
|---|---|
| `content/modules/ROOT/pages/index.adoc` | Learner-facing introduction |
| `content/modules/ROOT/pages/conclusion.adoc` | Recap of learning objectives and next steps |

Both are generated sequentially with the same approve-before-writing step.

### Using it

Select a module from the **Modules** workstream in the development dashboard, then choose **Use AI writer helper**. The skill reads your outlines and presents a plan.

!!! tip "Invest in your outlines"
    The writer generates content directly from `publishing-house/spec/modules/`. The more detail
    you put in those outlines during intake, the better the generated content.

### Writing manually

Select **Write it myself** from the Modules workstream. Claude points you to the file path and waits. Write your `.adoc` file in your editor, then come back and confirm you're done.

---

## Reviewer Helper

The reviewer helper runs a quality pass on any `.adoc` file — content you wrote yourself or AI-generated.

### What it checks

- **Red Hat standards** — heading structure, admonition usage, code block formatting, terminology
- **Spec alignment** — does the content cover everything in the outline? Do learning objectives match? Are product names and versions consistent?
- **Findings** — severity-rated (CRITICAL, HIGH, MEDIUM, LOW); written to `publishing-house/reviews/editing-review-module-NN.md`

Findings are guidance, not mandatory fixes. Review them and apply your own judgment — some may not apply to your specific lab.

### Using it

From the **Modules** workstream, after writing, choose **Run AI quality pass**. You can also invoke it directly:

```
/rhdp-publishing-house:reviewer-helper
```

### Fix loop

After the review, you have three options:

| # | Option |
|---|--------|
| 1 | Edit the file yourself, then re-run the review |
| 2 | Ask Claude to fix specific items |
| 3 | Done — go back to development to mark the module complete |

---

## Typical flow

```
spec/modules/module-NN-slug.md   ⇒   writer-helper   ⇒   reviewer-helper   ⇒   mark complete
    (your outline)                        (optional)             (optional)
```

You can skip either helper entirely. The development skill tracks status and handles submission regardless of how you produce the work.

---

## Tips

- **The writer and reviewer are independent.** Use one, both, or neither.
- **You can re-run the reviewer after manual edits.** Choose "review again" to get a fresh pass on updated content.
- **File names must match between outlines and content.** The helper enforces this automatically; if writing manually, follow the same convention.
