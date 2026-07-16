# RCARS Integration Design for Publishing House

**Date:** 2026-04-27
**Status:** Draft
**Scope:** How PH calls RCARS across both access modes, auth model, MCP tool contracts, deployment changes

---

## Problem

PH needs RCARS for content vetting (overlap detection) during intake. The current intake skill has a broken `curl` call to a `/recommend` endpoint that doesn't exist in RCARS v2. Beyond fixing the call, we need a proper integration pattern that:

- Works for both access modes (local Claude Code and hosted portal/chatbot)
- Handles auth transparently — users never see tokens, endpoints, or API keys
- Extends naturally as PH integrates with more backend services (Jira, Babylon, etc.)

## Decision: Portal Backend as Single Gateway

The PH portal backend (FastAPI, deployed on OpenShift in `publishing-house-dev`) already has an MCP server via FastMCP 2.0 mounted at `/mcp`. It becomes the single gateway to all backend services.

```
CC user ──HTTPS──▶ PH MCP server ──cluster-internal──▶ RCARS API
                        │
Chatbot user ──UI──▶ Portal frontend ──▶ Portal backend ──▶ RCARS API
```

Skills never call external APIs directly. They reference MCP tools (`ph_rcars_query`), and the MCP server handles routing, auth, and network access. If RCARS changes its API, or we swap the backend, skills don't change.

### Why not alternatives

- **Separate RCARS gateway service:** Duplicates integration logic. The portal backend already has MCP, a database, and a deployment pipeline. A second service is pure overhead.
- **Local MCP server:** Requires `oc port-forward` or an external RCARS route. Breaks the "same experience both ways" principle. Can't serve chatbot users.

---

## Auth Model

Two boundaries, both simple.

### Boundary 1: CC User → PH MCP Server (external)

**Mechanism:** API keys stored in a K8s Secret.

- Secret `ph-mcp-api-keys` in `publishing-house-dev` namespace
- Format: YAML map of `key-name → sha256-hashed-key` pairs
- Key names are for admin bookkeeping (who has this key), not user identity
- Backend reads the Secret on startup (volume mount or env var)
- CC user sends `Authorization: Bearer <key>` header in MCP config
- Invalid/missing key → 401

**Admin workflow:**

1. Generate a key: `openssl rand -hex 32`
2. Hash it: `echo -n "<key>" | sha256sum | awk '{print $1}'`
3. Add the **hashed** value to the Ansible vars file (`vars/dev.yml` or `vars/prod.yml`, never pushed to remote)
4. Run the deployer to update the Secret
5. Give the **raw** key to the user for their CC config
6. To revoke: remove the entry from vars, redeploy

The backend receives the raw key from the user, hashes it, and compares against the stored hashes in the Secret.

**Ansible integration:** The Secret is managed by the PH Ansible deployer. Key values live in `vars/dev.yml` and `vars/prod.yml` (gitignored). Redeployment never loses keys.

**CC user's MCP config:**

```json
{
  "mcpServers": {
    "publishing-house": {
      "type": "streamable-http",
      "url": "https://ph-mcp.apps.<cluster-domain>/mcp",
      "headers": {
        "Authorization": "Bearer <their-api-key>"
      }
    }
  }
}
```

### Boundary 2: PH MCP Server → RCARS (cluster-internal)

**Mechanism:** Kubernetes ServiceAccount token.

- PH backend pod has an auto-mounted SA token at `/var/run/secrets/kubernetes.io/serviceaccount/token`
- PH sends this as `Authorization: Bearer <sa-token>` when calling RCARS
- RCARS validates via K8s TokenReview API and checks against `RCARS_SA_ALLOWLIST_STR`
- No secrets to create, no rotation to manage — K8s handles token lifecycle
- RCARS logs requests as the PH service account name

**RCARS config change:** Add `system:serviceaccount:publishing-house-dev:<ph-backend-sa-name>` to `RCARS_SA_ALLOWLIST_STR` in the RCARS Ansible `vars/dev.yml` (and `vars/prod.yml` for prod). Managed by Ansible — never lost on redeploy.

**Cross-namespace call:** `http://rcars-api.rcars-dev.svc.cluster.local:8080/api/v1/*`

Standard cross-namespace service DNS. Verify no restrictive NetworkPolicies exist in either namespace.

---

## MCP Tools

### Core Tools (for intake vetting)

#### `ph_rcars_query(query: str) → dict`

Submit an advisor query, poll until complete, return results.

- **Maps to:** `POST /api/v1/advisor/query` → poll `GET /api/v1/advisor/query/{job_id}/result`
- **Always sends** `prod_only=False` — vetting needs the full catalog picture (prod, dev, event)
- **Async handling is internal:** The tool submits the job, polls every 3 seconds, and returns the final result. The caller never sees a job_id. Timeout: 120 seconds.
- **Returns:** List of matching CIs with relevance tiers (green/yellow/white), rationale text, CI metadata (name, display name, stage, Showroom URL)
- **On timeout/failure:** Returns a structured error the skill can handle gracefully

#### `ph_rcars_catalog_search(query: str, limit: int = 20) → dict`

Browse/search the RCARS catalog.

- **Maps to:** `GET /api/v1/catalog?limit={limit}` (with query filtering when RCARS adds text search — for now, returns paginated list)
- **Returns:** List of catalog items with basic metadata

#### `ph_rcars_catalog_item(ci_name: str) → dict`

Get details and analysis for a specific catalog item.

- **Maps to:** `GET /api/v1/catalog/{ci_name}`
- **Returns:** Full CI metadata plus analysis (summary, content hash, staleness, analyzed_at)

### Future Tools (pattern established, not built now)

| Tool | Purpose | When needed |
|------|---------|-------------|
| `ph_rcars_select(session_id, ci_name)` | Record "this fits best" selection | Prototype mode |
| `ph_rcars_catalog_stats()` | Catalog coverage stats | Admin/reporting |
| `ph_jira_create_issue(...)` | Create a Jira ticket for a PH project | Jira integration |
| `ph_jira_link_project(...)` | Link a PH project to a Jira epic | Jira integration |

---

## Network Topology & Deployment Changes

### New: External Route for PH Backend MCP

```yaml
kind: Route
metadata:
  name: ph-mcp
  namespace: publishing-house-dev
spec:
  host: ph-mcp.apps.<cluster-domain>
  path: /mcp
  to:
    kind: Service
    name: ph-dashboard-backend
  port:
    targetPort: 8080
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

Only `/mcp` is exposed externally. Internal backend APIs (`/api/v1/projects`, etc.) remain cluster-internal. API key auth guards the MCP endpoint — no OAuth proxy on this route.

### New: K8s Secret for MCP API Keys

Managed by PH Ansible deployer. Key values in `vars/dev.yml` / `vars/prod.yml` (gitignored, never pushed to remote).

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ph-mcp-api-keys
  namespace: publishing-house-dev
stringData:
  keys.yaml: |
    nate: "sha256:<hash>"
```

### Change: RCARS SA Allowlist

In RCARS Ansible `vars/dev.yml`:

```yaml
rcars_sa_allowlist:
  - "system:serviceaccount:publishing-house-dev:<ph-backend-sa-name>"
```

Fed into `RCARS_SA_ALLOWLIST_STR` env var in the RCARS deployment template. Managed by Ansible — redeployment preserves the allowlist.

### Deployment Summary

| Component | Change | Repo |
|-----------|--------|------|
| PH backend | Add RCARS HTTP client + MCP tools | `rhdp-publishing-house-portal` |
| PH backend | API key auth middleware on `/mcp` | `rhdp-publishing-house-portal` |
| PH Ansible | Route for `/mcp`, Secret for API keys | `rhdp-publishing-house-portal` |
| RCARS Ansible | PH SA in allowlist var | `rcars-advisory` |
| PH skills | Replace `curl` with `ph_rcars_query` tool reference | `rhdp-publishing-house-skills` |

---

## Skill Changes

### Intake Skill — Vetting Phase

The vetting phase (Phase 2 of intake) changes from a direct `curl` call to an MCP tool reference:

**Before (broken):**
```bash
curl -s -X POST "${RCARS_API}/recommend" \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "limit": 10}'
```

**After:**
```
Use the `ph_rcars_query` tool with a query built from the project's
learning objectives, topics, and products.
```

Everything else stays the same:
- Skill builds the query string from the spec (learning objectives, topics, products)
- Skill receives structured results (matching CIs with tiers and rationale)
- Skill writes the vetting report to `publishing-house/reviews/rcars-vetting.md`
- Skill sets manifest vetting status (`approved`, `revise`, `rejected`)
- If the MCP tool isn't available (user doesn't have the MCP server configured), skill offers to skip vetting — same graceful degradation as today

### Separation of Concerns

- **RCARS provides data:** "Here's what exists that's related to your query — matching CIs with relevance tiers, rationale, and metadata."
- **PH skill interprets in context:** The skill has the project spec (learning objectives, target audience, deployment mode). It compares RCARS results against the project goals and makes the vetting judgment — gap confirmed, partial overlap, or already covered.

RCARS knows the catalog. The skill knows the project. Neither needs the other's context.

---

## Verification Checklist

Before declaring the integration complete:

- [ ] PH backend can reach RCARS cross-namespace (`rcars-api.rcars-dev.svc.cluster.local:8080`)
- [ ] SA token auth works: PH backend sends its SA token, RCARS validates via TokenReview, request succeeds
- [ ] MCP API key auth works: CC sends Bearer token, backend validates against Secret, MCP tools are accessible
- [ ] `ph_rcars_query` returns structured results for a test query
- [ ] Intake skill can run vetting phase end-to-end using the MCP tool
- [ ] Invalid API key returns 401
- [ ] RCARS unavailable returns a graceful error (not a hang or crash)
- [ ] Ansible deployer manages all secrets and config — manual `oc edit` not required
- [ ] Documentation complete: architecture, admin runbooks, CC setup guide, MCP tools reference

---

## Documentation Deliverables

Ship alongside code, not after.

| Document | Location | Contents |
|----------|----------|----------|
| PH-RCARS Integration Architecture | `docs/architecture/rcars-integration.md` | System diagram, data flow, auth boundaries, network topology |
| MCP Server Auth Guide | `docs/admin/mcp-auth.md` | API key lifecycle, create/revoke steps, Ansible var references |
| CC User Setup Guide | `docs/user/claude-code-setup.md` | MCP server config, how to get an API key, connectivity verification |
| RCARS Service Integration | `docs/admin/rcars-service-auth.md` | SA allowlist config, cross-namespace DNS, SA token verification |
| MCP Tools Reference | `docs/api/mcp-tools.md` | Each tool's purpose, parameters, return shape, example usage |

---

## Open Questions

1. **Exact PH backend ServiceAccount name** — need to check the portal deployment to get the correct SA name for the RCARS allowlist.
2. **RCARS SA token auth testing** — the code path exists in RCARS middleware but may not have been tested with cross-namespace SA tokens. Verify during implementation.
3. **NetworkPolicies** — check both `publishing-house-dev` and `rcars-dev` namespaces for restrictive policies that could block cross-namespace traffic.
4. **MCP Secret refresh** — decide whether the backend hot-reloads the API key Secret or requires a pod restart. Hot-reload is nicer but adds complexity; pod restart is fine for a handful of keys.
