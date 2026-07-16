# MCP Authentication

Publishing House has two authentication boundaries:

- **External (API keys):** Claude Code users authenticate to the MCP endpoint with Bearer API keys. Keys are SHA-256 hashed and stored in a Kubernetes Secret.
- **Internal (SA tokens):** The PH Central backend authenticates to the RCARS API using its Kubernetes ServiceAccount token. Kubernetes manages token lifecycle automatically.

## API Key Authentication (External)

The Publishing House MCP endpoint (`/mcp`) uses API key authentication for external Claude Code users. Keys are SHA-256 hashed and stored in a Kubernetes Secret that is volume-mounted into the backend pod. The FastMCP `ApiKeyAuth` Middleware validates every tool call before dispatch.

This section covers the full API key lifecycle: generation, distribution, revocation, and troubleshooting.

### Key Generation

Follow these steps to create a new API key for a user.

#### Step 1: Generate the raw key

```bash
openssl rand -hex 32
```

This produces a 64-character hex string (256 bits of entropy). Save this value -- you will give it to the user in Step 5.

#### Step 2: Hash the key

```bash
echo -n "<raw-key>" | sha256sum | awk '{print $1}'
```

Replace `<raw-key>` with the actual key from Step 1. This produces the SHA-256 hash that gets stored in the Secret.

#### Step 3: Add the hash to Ansible vars

Edit `ansible/vars/dev.yml` (or `ansible/vars/prod.yml` for production) in the `rhdp-publishing-house-central` repo. Add the hashed value to the `mcp_api_keys` dictionary:

```yaml
mcp_api_keys:
  nate: "<sha256-hash-from-step-2>"
  prakhar: "<sha256-hash>"
```

The key name (e.g., `nate`) is an admin identifier for bookkeeping -- it tells you who has this key. It is not used for authentication.

**Never commit `dev.yml` or `prod.yml` to git.** These files are gitignored. Only `.example` files are tracked.

#### Step 4: Deploy

Run the Ansible deployer to update the Secret and restart the backend pod:

```bash
cd rhdp-publishing-house-central && ansible-playbook ansible/deploy.yml -e env=dev --tags apply
```

The `apply` tag updates manifests (Secrets, ConfigMaps, Deployments) without triggering a rebuild. The backend pod restarts to pick up the new key file (D-01: no hot-reload in Phase 1). Only use `--tags deploy` if you also need to rebuild code and run migrations.

#### Step 5: Distribute the raw key

Give the **raw key** (from Step 1) to the user. They will add it to their Claude Code MCP configuration. See the [Claude Code Setup Guide](../user/getting-started.md) for user-facing instructions.

**Never share the SHA-256 hash.** The hash is the stored credential; the raw key is the user credential.

### Key Revocation

To revoke a user's API key:

1. Remove the user's entry from `mcp_api_keys` in `ansible/vars/dev.yml`
2. Apply the change:
   ```bash
   cd rhdp-publishing-house-central && ansible-playbook ansible/deploy.yml -e env=dev --tags apply
   ```
3. The backend pod restarts and loads the updated key file. The revoked key is immediately invalid.

### Key Rotation

To rotate a key (e.g., if a key may have been compromised):

1. Generate a new key (Steps 1-2 above)
2. Replace the old hash with the new hash in `ansible/vars/dev.yml`
3. Redeploy (Step 4)
4. Give the new raw key to the user (Step 5)

The old key becomes invalid as soon as the pod restarts with the updated Secret.

### Key Storage

API keys are stored in a Kubernetes Secret named `ph-mcp-api-keys` in the `publishing-house-central-dev` namespace. The Secret is volume-mounted into the backend pod at `/etc/ph/mcp-api-keys/keys.yaml`.

#### File format

```yaml
user-name: "sha256:<hex-digest>"
another-user: "sha256:<hex-digest>"
```

Each entry maps an admin-chosen key name to a `sha256:`-prefixed hex digest. The backend strips the `sha256:` prefix when loading keys and compares against the hash of the incoming raw key.

#### How validation works

1. Claude Code sends `Authorization: Bearer <raw-key>` in the MCP request
2. The `ApiKeyAuth` Middleware extracts the raw key from the header
3. The middleware computes `hashlib.sha256(raw_key.encode()).hexdigest()`
4. The middleware compares the computed hash against each stored hash using `hmac.compare_digest()` (timing-safe)
5. If any stored hash matches, the tool call proceeds. If none match, a `ToolError` is raised

### Ansible Integration

The API key Secret is defined in Central's Ansible infrastructure template (`ansible/templates/manifests-infra.yaml.j2`). The template iterates over the `mcp_api_keys` dictionary from vars and generates the Secret content using `dict2items`:

```yaml
stringData:
  keys.yaml: |
{% for key in mcp_api_keys | default({}) | dict2items %}
    {{ key.key }}: "sha256:{{ key.value }}"
{% endfor %}
```

The `mcp_api_keys` variable lives in env-specific vars files (`vars/dev.yml`, `vars/prod.yml`) which are gitignored.

### Troubleshooting

#### "Authentication required: missing or invalid Authorization header"

**Cause:** The request does not have an `Authorization` header or it does not start with `Bearer `.

**Fix:** Verify the Claude Code MCP config includes the `headers` block with `Authorization: Bearer <key>`. See the [Claude Code Setup Guide](../user/getting-started.md).

#### "Authentication failed: invalid API key"

**Cause:** The raw key does not match any stored hash.

**Possible reasons:**
- The key was revoked (removed from vars and redeployed)
- The key was rotated (replaced with a new key)
- The key was entered incorrectly in the user's MCP config (whitespace, truncation)
- The key hash was generated incorrectly (e.g., missing `-n` flag on `echo`)

**Fix:** Verify the raw key matches the expected hash:
```bash
echo -n "<raw-key>" | sha256sum | awk '{print $1}'
```
Compare the output with the value stored in `ansible/vars/dev.yml`.

#### "No valid keys loaded" or empty key file

**Cause:** The key file was not found at the expected mount path, or the file is empty.

**Possible reasons:**
- The Secret does not exist in the namespace
- The volume mount path does not match the configured key file path
- The `mcp_api_keys` dictionary is empty in the Ansible vars

**Fix:**
1. Verify the Secret exists:
   ```bash
   oc get secret ph-mcp-api-keys -n publishing-house-central-dev
   ```
2. Verify the file exists inside the pod:
   ```bash
   oc exec deployment/ph-central-backend -n publishing-house-central-dev -- cat /etc/ph/mcp-api-keys/keys.yaml
   ```
3. Verify `mcp_api_keys` is not empty in `ansible/vars/dev.yml`

#### Key change not taking effect

**Cause:** The backend pod has not restarted after a key change.

**Fix:** The backend reads the key file at startup only (D-01). After updating keys and redeploying, verify the pod restarted:
```bash
oc get pods -l app=ph-central,component=backend -n publishing-house-central-dev
```
The pod age should be recent (seconds/minutes, not hours/days).

## Service Account Token Authentication (Internal)

The PH Central backend authenticates to the RCARS API using its Kubernetes ServiceAccount (SA) token. This is a cluster-internal, zero-configuration authentication mechanism -- Kubernetes manages token creation, rotation, and injection automatically.

RCARS validates incoming SA tokens via the Kubernetes TokenReview API and checks the authenticated identity against a configured allowlist. No secrets need to be created or rotated manually.

### How It Works

1. Kubernetes auto-mounts a projected SA token into the PH backend pod at `/var/run/secrets/kubernetes.io/serviceaccount/token`
2. The PH `RCARSClient` reads this token from the filesystem on every request (never cached, because K8s rotates tokens automatically)
3. The client sends the token as `Authorization: Bearer <sa-token>` to RCARS
4. RCARS middleware submits the token to the Kubernetes TokenReview API for validation
5. If the token is valid, RCARS checks the authenticated identity against its SA allowlist
6. If the identity is in the allowlist, the request proceeds; otherwise it is rejected

### SA Allowlist Configuration

The SA allowlist controls which service accounts are permitted to call the RCARS API directly (bypassing the OAuth proxy auth path).

#### Current PH entry

```
system:serviceaccount:publishing-house-central-dev:default
```

This is the `default` ServiceAccount in the `publishing-house-central-dev` namespace, which the PH backend pod runs under.

#### Adding or removing entries

Edit `ansible/vars/dev.yml` in the `rcars-advisory` repo:

```yaml
rcars_sa_allowlist:
  - "system:serviceaccount:publishing-house-central-dev:default"
  # Add additional SAs as needed:
  # - "system:serviceaccount:other-namespace:service-name"
```

The format for each entry is:

```
system:serviceaccount:<namespace>:<serviceaccount-name>
```

#### Deploying changes

After editing the allowlist vars, run the RCARS Ansible deployer:

```bash
cd rcars-advisory/ansible && ansible-playbook deploy.yml -e @vars/dev.yml
```

This updates the `RCARS_SA_ALLOWLIST_STR` environment variable in the RCARS deployment and triggers a pod restart.

### Cross-Namespace DNS

The PH backend reaches RCARS via standard Kubernetes cross-namespace service DNS:

```
http://rcars-api.rcars-dev.svc.cluster.local:8080
```

This is the RCARS API ClusterIP Service in the `rcars-dev` namespace. No external Route is needed -- the call stays within the cluster.

#### DNS pattern

```
<service-name>.<namespace>.svc.cluster.local:<port>
```

### Verification

#### Verify cross-namespace connectivity

From the PH backend pod, test that RCARS is reachable:

```bash
oc exec deployment/ph-central-backend -n publishing-house-central-dev -- \
  curl -s http://rcars-api.rcars-dev.svc.cluster.local:8080/api/v1/health
```

Expected response:

```json
{"status": "ok"}
```

#### Verify SA token is being mounted

```bash
oc exec deployment/ph-central-backend -n publishing-house-central-dev -- \
  cat /var/run/secrets/kubernetes.io/serviceaccount/token | head -c 50
```

This should print the first 50 characters of a JWT-formatted token.

#### Verify SA identity

Check what SA the backend pod is running as:

```bash
oc get deployment ph-central-backend -n publishing-house-central-dev \
  -o jsonpath='{.spec.template.spec.serviceAccountName}'
```

If empty, the pod uses the `default` SA.

#### Verify RCARS allowlist includes PH SA

```bash
oc exec deployment/rcars-api -n rcars-dev -- env | grep SA_ALLOWLIST
```

The output should include `system:serviceaccount:publishing-house-central-dev:default`.

#### Verify authenticated RCARS call

From the PH backend pod, test authentication end-to-end:

```bash
oc exec deployment/ph-central-backend -n publishing-house-central-dev -- \
  bash -c 'TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token) && \
  curl -s -H "Authorization: Bearer $TOKEN" \
  http://rcars-api.rcars-dev.svc.cluster.local:8080/api/v1/health'
```

#### NetworkPolicy checks

Verify no NetworkPolicies are blocking cross-namespace traffic:

```bash
# Check for NetworkPolicies in the RCARS namespace
oc get networkpolicy -n rcars-dev

# Check for NetworkPolicies in the PH namespace
oc get networkpolicy -n publishing-house-central-dev
```

If restrictive policies exist, ensure they allow ingress from the `publishing-house-central-dev` namespace to the `rcars-api` service on port 8080.

### Troubleshooting

#### "Authentication required" from RCARS

**Cause:** The SA token is not being sent, or RCARS is not recognizing the token format.

**Check:**
1. Verify the SA token file exists in the pod (see verification commands above)
2. Verify the `RCARS_INTERNAL_URL` environment variable is set correctly in the PH backend deployment
3. Check RCARS logs for auth-related errors:
   ```bash
   oc logs deployment/rcars-api -n rcars-dev --tail=50 | grep -i auth
   ```

#### "SA not in allowlist" from RCARS

**Cause:** The PH SA identity is not in the `RCARS_SA_ALLOWLIST_STR` environment variable.

**Fix:**
1. Verify the allowlist value (see verification commands above)
2. Ensure the entry matches exactly: `system:serviceaccount:publishing-house-central-dev:default`
3. If missing, add it to `rcars_sa_allowlist` in `ansible/vars/dev.yml` and redeploy RCARS

#### DNS resolution failure

**Cause:** The cross-namespace service DNS name is incorrect, or the RCARS service does not exist.

**Check:**
```bash
# Verify RCARS service exists
oc get svc rcars-api -n rcars-dev

# Test DNS resolution from PH pod
oc exec deployment/ph-central-backend -n publishing-house-central-dev -- \
  nslookup rcars-api.rcars-dev.svc.cluster.local
```

#### Token rotation issues

SA tokens are automatically rotated by Kubernetes. The PH `RCARSClient` re-reads the token from the filesystem on every request, so rotation is transparent.

If you see intermittent auth failures that resolve on their own, this is likely a brief window during token rotation. No action is needed -- the next request will use the new token.

#### Connection timeout to RCARS

**Cause:** RCARS pod is not running, or there is a network issue between namespaces.

**Check:**
```bash
# Verify RCARS pods are running
oc get pods -l app=rcars -n rcars-dev

# Check RCARS pod logs
oc logs deployment/rcars-api -n rcars-dev --tail=20
```

The PH `RCARSClient` retries transient failures 3 times with exponential backoff (1s, 2s, 4s). If RCARS is down for an extended period, the MCP tool returns a structured error and the intake skill offers to skip vetting.

## Related Documentation

- [RCARS Integration Architecture](../architecture/rcars-integration.md)
- [Claude Code Setup Guide](../user/getting-started.md)
- [Central Deployment](deployment.md)
