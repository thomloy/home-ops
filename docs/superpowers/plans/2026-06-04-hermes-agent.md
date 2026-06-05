# Hermes Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing Ollama + Open-WebUI AI stack in the `ai/` namespace with a Hermes Agent deployment backed by Anthropic Claude.

**Architecture:** Delete `kubernetes/apps/ai/ollama/` and `kubernetes/apps/ai/open-webui/` directories, update `kubernetes/apps/ai/kustomization.yaml` index, add `kubernetes/apps/ai/hermes/` with a bjw-s `app-template` 4.6.2 HelmRelease running two containers in one pod (`gateway` + `dashboard`) that share a 5Gi `ceph-block` PVC, an ExternalSecret pulling `ANTHROPIC_API_KEY` from 1Password, and a CiliumNetworkPolicy allowing ingress from envoy-internal. Post-merge: manually delete the two orphan PVCs.

**Tech Stack:** Flux CD, Kustomize, bjw-s app-template 4.6.2, `docker.io/nousresearch/hermes-agent:v2026.5.29.2` (Debian 13 + Python 3.13 + Node 22 + s6-overlay), External Secrets Operator + 1Password Connect, Cilium NetworkPolicy, Envoy Gateway.

**Spec:** `docs/superpowers/specs/2026-06-04-hermes-agent-design.md`

**Pre-flight facts already gathered** (skip re-discovery):
- Hermes image entrypoint is `/init` (s6-overlay PID 1) → routes via `/opt/hermes/docker/main-wrapper.sh` → executes `hermes <args>` from container CMD
- Container MUST start as root (UID 0) to allow the s6 stage2 hook to remap the internal `hermes` user to `HERMES_UID`/`HERMES_GID` (default 10000); after remap, s6-setuidgid drops to non-root. Setting `runAsNonRoot: true` with an arbitrary UID **breaks the container**
- Dashboard is gated by `HERMES_DASHBOARD` env var in s6-rc mode, but the docker-compose pattern (which we follow) runs dashboard as a SEPARATE container with `command: ["dashboard", "--host", ...]` — bypassing the env-var gate
- Anthropic provider plugin reads `ANTHROPIC_API_KEY` from env (or fallbacks `ANTHROPIC_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`)
- No documented health endpoint on `gateway` → skip probes for that container
- Default dashboard port (per upstream `docker/s6-rc.d/dashboard/run`) needs verification at impl time; the spec uses 9119 — the implementer should boot the image once and confirm via `docker logs` what port the dashboard binds when started with `--host 0.0.0.0`

---

## Pre-flight (operator one-time)

### Task 0 : Create 1Password item `hermes`

**Files:** none (1Password CLI or web UI)

- [ ] **Step 1 : Generate an Anthropic API key**

Visit https://console.anthropic.com → API Keys → Create Key (name it `homelab-hermes`). Copy the value (`sk-ant-api03-...`, ~108 chars). It is shown only once.

- [ ] **Step 2 : Create the 1P item**

Either via the 1Password desktop app or via `op item create`:

```bash
op item create \
  --category=password \
  --title=hermes \
  --vault=kubernetes \
  api_token="sk-ant-api03-<your-key-here>"
```

- [ ] **Step 3 : Verify**

```bash
op item get hermes --vault=kubernetes --fields api_token | head -c 16
echo
```

Expected: starts with `sk-ant-api03-`. If not readable, re-create. Item must exist BEFORE merging the PR.

---

## Phase 1 : Branch + repo edits

### Task 1 : Create feature branch

**Files:** none

- [ ] **Step 1 : Branch from main**

```bash
cd /home/kryzql/home-ops
git checkout main
git pull --ff-only
git checkout -b feat/hermes-agent
```

### Task 2 : Delete the ollama directory

**Files:**
- Delete: entire `kubernetes/apps/ai/ollama/` directory tree

- [ ] **Step 1 : Remove the directory and stage the deletion**

```bash
cd /home/kryzql/home-ops
git rm -r kubernetes/apps/ai/ollama
git status --short | head
```

Expected: shows `D` (deleted) entries for each file under `kubernetes/apps/ai/ollama/`. No `M` or `??` entries from this command.

### Task 3 : Delete the open-webui directory

**Files:**
- Delete: entire `kubernetes/apps/ai/open-webui/` directory tree

- [ ] **Step 1 : Remove the directory and stage the deletion**

```bash
git rm -r kubernetes/apps/ai/open-webui
git status --short | head
```

Expected: shows `D` entries for each file under `kubernetes/apps/ai/open-webui/` (plus the previous Task 2 deletions).

### Task 4 : Update `ai/kustomization.yaml`

**Files:**
- Modify: `kubernetes/apps/ai/kustomization.yaml`

The current `resources:` list contains `./namespace.yaml`, `./ollama/ks.yaml`, `./open-webui/ks.yaml`. Replace it so it lists `./namespace.yaml` and `./hermes/ks.yaml`.

- [ ] **Step 1 : Write the new content**

Overwrite `kubernetes/apps/ai/kustomization.yaml` with :

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: ai

components:
  - ../../components/alerts
  - ../../components/sops

resources:
  - ./namespace.yaml
  - ./hermes/ks.yaml
```

- [ ] **Step 2 : Sanity check**

```bash
yq eval '.resources' /home/kryzql/home-ops/kubernetes/apps/ai/kustomization.yaml
```

Expected:
```yaml
- ./namespace.yaml
- ./hermes/ks.yaml
```

(no `ollama` or `open-webui` entries)

### Task 5 : Create the hermes app directory + Kustomize index

**Files:**
- Create: `kubernetes/apps/ai/hermes/app/kustomization.yaml`

- [ ] **Step 1 : Make the directories**

```bash
mkdir -p kubernetes/apps/ai/hermes/app
```

- [ ] **Step 2 : Write `kubernetes/apps/ai/hermes/app/kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

Note: this references files that do not exist yet; they are created in Tasks 6-9. This is intentional — Kustomize will only be built after all are present.

### Task 6 : Create the Flux Kustomization (`ks.yaml`)

**Files:**
- Create: `kubernetes/apps/ai/hermes/ks.yaml`

- [ ] **Step 1 : Write the manifest**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: hermes
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: hermes
  dependsOn:
    - name: rook-ceph-cluster
      namespace: rook-ceph
  interval: 1h
  path: "./kubernetes/apps/ai/hermes/app"
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: ai
  timeout: 5m
  wait: false
```

### Task 7 : Create the OCIRepository

**Files:**
- Create: `kubernetes/apps/ai/hermes/app/ocirepository.yaml`

- [ ] **Step 1 : Write the manifest** (same `app-template` version as every other selfhosted app)

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/source.toolkit.fluxcd.io/ocirepository_v1.json
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: hermes
spec:
  interval: 15m
  layerSelector:
    mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
    operation: copy
  ref:
    tag: 4.6.2
  url: oci://ghcr.io/bjw-s-labs/helm/app-template
```

### Task 8 : Create the ExternalSecret

**Files:**
- Create: `kubernetes/apps/ai/hermes/app/externalsecret.yaml`

- [ ] **Step 1 : Write the manifest**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: hermes-secret
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: hermes-secret
    creationPolicy: Owner
  data:
    - secretKey: ANTHROPIC_API_KEY
      remoteRef:
        key: hermes
        property: api_token
```

### Task 9 : Create the CiliumNetworkPolicy

**Files:**
- Create: `kubernetes/apps/ai/hermes/app/ciliumnetworkpolicy.yaml`

- [ ] **Step 1 : Write the manifest**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: hermes
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: hermes
      app.kubernetes.io/instance: hermes
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "9119"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
```

No `egress` block — defaults to allow. Per memory [[feedback_cilium_toentities_world]], avoid `toEntities: world` + `toPorts` (broken under DSR).

### Task 10 : Create the HelmRelease

**Files:**
- Create: `kubernetes/apps/ai/hermes/app/helmrelease.yaml`

- [ ] **Step 1 : Write the manifest**

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: hermes
spec:
  chartRef:
    kind: OCIRepository
    name: hermes
  interval: 1h
  maxHistory: 3
  install:
    remediation:
      retries: 3
  upgrade:
    cleanupOnFail: true
    remediation:
      retries: 3
  uninstall:
    keepHistory: false
  values:
    controllers:
      hermes:
        annotations:
          reloader.stakater.com/auto: "true"
        containers:
          gateway:
            image:
              repository: docker.io/nousresearch/hermes-agent
              tag: "v2026.5.29.2"
            command:
              - gateway
              - run
            envFrom:
              - secretRef:
                  name: hermes-secret
            env:
              HERMES_UID: "10000"
              HERMES_GID: "10000"
              HERMES_HOME: /opt/data
              TZ: Europe/Paris
            resources:
              requests:
                memory: 256Mi
                cpu: 100m
              limits:
                memory: 1536Mi
          dashboard:
            image:
              repository: docker.io/nousresearch/hermes-agent
              tag: "v2026.5.29.2"
            command:
              - dashboard
              - --host
              - 0.0.0.0
              - --no-open
            envFrom:
              - secretRef:
                  name: hermes-secret
            env:
              HERMES_UID: "10000"
              HERMES_GID: "10000"
              HERMES_HOME: /opt/data
              TZ: Europe/Paris
            probes:
              liveness: &dashboardProbe
                enabled: true
                custom: true
                spec:
                  httpGet:
                    path: /
                    port: 9119
                  initialDelaySeconds: 30
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *dashboardProbe
              startup:
                enabled: true
                custom: true
                spec:
                  httpGet:
                    path: /
                    port: 9119
                  failureThreshold: 60
                  periodSeconds: 5
            resources:
              requests:
                memory: 128Mi
                cpu: 50m
              limits:
                memory: 512Mi

    defaultPodOptions:
      securityContext:
        seccompProfile:
          type: RuntimeDefault

    service:
      app:
        controller: hermes
        ports:
          http:
            port: 9119

    route:
      app:
        annotations:
          gatus.home-operations.com/endpoint: |-
            alerts:
              - type: pushover
            conditions: ["[STATUS] < 500"]
            ui:
              hide-hostname: true
        hostnames:
          - "hermes.${SECRET_DOMAIN}"
        parentRefs:
          - name: envoy-internal
            namespace: network
        rules:
          - backendRefs:
              - name: hermes
                port: 9119

    persistence:
      data:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 5Gi
        storageClass: ceph-block
        advancedMounts:
          hermes:
            gateway:
              - path: /opt/data
            dashboard:
              - path: /opt/data

    disableDefaultSecurityContext: All
```

Notes about specific choices in this file (for the reviewer):
- `disableDefaultSecurityContext: All` — Hermes' container MUST start as root for the s6 stage2 hook to remap the internal `hermes` user. The default bjw-s pattern sets `runAsNonRoot: true` which breaks this image. We mirror the same pattern already used for `tandoor` and `sparkyfitness` in this repo.
- `gateway` container has NO probes — Hermes upstream provides no documented health endpoint for the gateway process. Skipping is the documented fallback in the spec §3.3.
- `dashboard` probe path `GET /` on port `9119` is the assumed dashboard root. If the actual port differs (verified at impl time via Task 11 smoke test logs), update the port value and re-validate before committing.
- `HERMES_HOME: /opt/data` matches the Dockerfile ENV but is set explicitly here because the Dockerfile note says `/init` scrubs env before invoking CMD; main-wrapper.sh repopulates via `with-contenv`, but setting it on the K8s container side is safer and explicit.

### Task 11 : Local docker smoke test (validate port + image works)

**Files:** none (read-only validation using docker)

- [ ] **Step 1 : Pull the image and boot the dashboard for 12s, capture logs**

```bash
timeout 12 docker run --rm --name hermes-dashboard-check \
  -e HERMES_UID=10000 -e HERMES_GID=10000 -e HERMES_HOME=/opt/data \
  -e ANTHROPIC_API_KEY=dummy \
  -p 19119:9119 \
  docker.io/nousresearch/hermes-agent:v2026.5.29.2 \
  dashboard --host 0.0.0.0 --no-open 2>&1 | tail -40
echo "exit code: $?"
docker rm -f hermes-dashboard-check 2>/dev/null
```

Expected:
- exit code 124 (SIGTERM from timeout = server was running at the timeout point)
- log lines containing the dashboard's bind address — look for something like `listening on 0.0.0.0:9119` (or whichever port). Verify the port matches 9119.

If a different port appears, update Task 9 (CNP `toPorts`), Task 10 (Service port, route port, dashboard probe port) before continuing.

- [ ] **Step 2 : Boot the gateway briefly to verify image runs**

```bash
timeout 10 docker run --rm --name hermes-gateway-check \
  -e HERMES_UID=10000 -e HERMES_GID=10000 -e HERMES_HOME=/opt/data \
  -e ANTHROPIC_API_KEY=dummy \
  docker.io/nousresearch/hermes-agent:v2026.5.29.2 \
  gateway run 2>&1 | tail -20
echo "exit code: $?"
docker rm -f hermes-gateway-check 2>/dev/null
```

Expected: exit 124 OR a clean log showing the gateway started and is waiting for input. No `ERROR` lines on startup unrelated to the dummy API key (a 401 from Anthropic when the gateway tries to validate the key is acceptable and expected; a Python traceback at startup is not).

### Task 12 : Pre-commit validation (`kustomize build` + grep gate)

**Files:** none

- [ ] **Step 1 : `kustomize build` for the new app directory**

```bash
kustomize build /home/kryzql/home-ops/kubernetes/apps/ai/hermes/app | wc -l
```

Expected: > 100 lines (the manifest expands to a few hundred lines after templating).

- [ ] **Step 2 : `kustomize build` for the ai parent directory**

```bash
kustomize build /home/kryzql/home-ops/kubernetes/apps/ai | grep -c "name: hermes"
```

Expected: `>= 1` (the hermes Kustomization is referenced).

- [ ] **Step 3 : Grep gate for orphan ollama/open-webui references**

```bash
grep -rl "ollama\|open-webui" /home/kryzql/home-ops/kubernetes/apps/ai/ 2>&1
```

Expected: no output. The `ai/` tree must contain zero references to either app after the deletion.

- [ ] **Step 4 : Optional flux-local diff if installed**

```bash
which flux-local && flux-local diff ks --path . --branch main --all-namespaces 2>&1 | head -100 || echo "flux-local not installed, skip"
```

Expected: shows ollama + open-webui resources being deleted, hermes resources being created. Skip if flux-local is not installed; CI runs it on the PR.

### Task 13 : Commit everything

**Files:** none

- [ ] **Step 1 : Verify the staged change set**

```bash
cd /home/kryzql/home-ops
git status --short | head -30
```

Expected: many `D` entries under `kubernetes/apps/ai/ollama/` and `kubernetes/apps/ai/open-webui/`, plus `??` entries for the new files under `kubernetes/apps/ai/hermes/`, plus `M kubernetes/apps/ai/kustomization.yaml`.

- [ ] **Step 2 : Stage all changes**

```bash
git add kubernetes/apps/ai/
git status --short | head -30
```

Expected: same files as above, now all in the staged area.

- [ ] **Step 3 : Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ai): replace ollama + open-webui with hermes-agent (Anthropic backend)

- Delete kubernetes/apps/ai/ollama/ and kubernetes/apps/ai/open-webui/
  directories along with their entries in ai/kustomization.yaml
- Add kubernetes/apps/ai/hermes/ with bjw-s app-template HelmRelease
  (1 pod, 2 containers: gateway + dashboard, shared /opt/data PVC),
  ExternalSecret pulling ANTHROPIC_API_KEY from 1Password item `hermes`,
  CiliumNetworkPolicy allowing ingress from envoy-internal on :9119
- Hostname: hermes.${SECRET_DOMAIN}
- Image: docker.io/nousresearch/hermes-agent:v2026.5.29.2

Post-merge manual cleanup: kubectl -n ai delete pvc ollama-models open-webui-data

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline main..HEAD
```

Expected: exactly one commit on top of main.

---

## Phase 2 : Push + PR + merge

### Task 14 : Push and open PR

**Files:** none

- [ ] **Step 1 : Push**

```bash
git push -u origin feat/hermes-agent
```

- [ ] **Step 2 : Open PR**

```bash
gh pr create --base main --head feat/hermes-agent \
  --title "feat(ai): replace ollama + open-webui with hermes-agent" \
  --body "$(cat <<'EOF'
## Summary
- Removes the existing Ollama + Open-WebUI stack from \`ai/\` namespace
- Deploys Hermes Agent (Nous Research) using the upstream image \`docker.io/nousresearch/hermes-agent:v2026.5.29.2\`
- Uses Anthropic Claude as the LLM backend via direct API (no OpenRouter)
- Exposes only the dashboard on \`hermes.\${SECRET_DOMAIN}\` via envoy-internal; relies on the tailnet perimeter for auth (no application-level auth)

Spec: \`docs/superpowers/specs/2026-06-04-hermes-agent-design.md\`
Plan: \`docs/superpowers/plans/2026-06-04-hermes-agent.md\`

## Required operator action BEFORE merge
1Password vault \`kubernetes\` must contain an item named \`hermes\` with field \`api_token\` = a valid Anthropic API key. Otherwise ExternalSecret stays \`Ready=False\` and the pod CrashLoops.

## Test plan
- [x] Local \`docker run docker.io/nousresearch/hermes-agent:v2026.5.29.2 dashboard --host 0.0.0.0 --no-open\` survives 12s with no parse errors and binds on the expected port
- [ ] flux-local CI green
- [ ] After merge: ExternalSecret \`hermes-secret\` Ready=True, contains \`ANTHROPIC_API_KEY\`
- [ ] Pod \`hermes\` reaches 2/2 Running within ~3 min (image is ~2-3GB so first pull is slow)
- [ ] \`https://hermes.\${SECRET_DOMAIN}\` loads the dashboard UI
- [ ] Configure default model in dashboard = Claude → send a test message → reply comes back

## Post-merge manual cleanup
\`\`\`bash
kubectl -n ai delete pvc ollama-models open-webui-data
\`\`\`
Releases ~55Gi of Ceph block storage.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Task 15 : Watch CI

**Files:** none

- [ ] **Step 1 : Watch the PR checks**

```bash
gh pr checks --watch --interval 20
```

Expected: flux-local checks pass within ~3 min. Trivy may fail with the same install flake observed in prior PRs; if so, it's not blocking — proceed to merge if Flux Local + Image Pull are green.

### Task 16 : Merge (squash)

**Files:** none

- [ ] **Step 1 : Merge**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 2 : Sync local main**

```bash
git checkout main
git fetch origin
git reset --hard origin/main
```

---

## Phase 3 : Post-merge verification + cleanup

### Task 17 : Reconcile Flux + watch deletion + creation

**Files:** none

- [ ] **Step 1 : Reconcile**

```bash
flux reconcile source git flux-system
flux reconcile kustomization cluster-apps -n flux-system
```

- [ ] **Step 2 : Watch ollama + open-webui Kustomizations disappear**

```bash
kubectl get kustomization -n ai 2>&1
```

Expected: only `hermes` listed (or empty if hermes hasn't appeared yet). The previous `ollama` and `open-webui` Kustomizations are gone.

- [ ] **Step 3 : Watch hermes Kustomization appear and become Ready**

```bash
flux reconcile kustomization hermes -n ai
kubectl -n ai get kustomization hermes -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
echo
```

Expected: `True`.

### Task 18 : Verify ExternalSecret + HelmRelease + Pod

**Files:** none

- [ ] **Step 1 : ExternalSecret**

```bash
kubectl -n ai get externalsecret hermes-secret -o jsonpath='{.status.conditions[*]}'
echo
kubectl -n ai get secret hermes-secret -o jsonpath='{.data}' | jq 'keys'
```

Expected: `Ready=True`, secret has 1 key `ANTHROPIC_API_KEY`. If `Ready=False`, the 1P item may be missing (see Task 0).

- [ ] **Step 2 : HelmRelease**

```bash
kubectl -n ai get hr hermes -o jsonpath='{.status.conditions[?(@.type=="Ready")].status} {.status.conditions[?(@.type=="Ready")].message}'
echo
```

Expected: `True Helm install succeeded` (or `Helm upgrade succeeded` on rollouts).

- [ ] **Step 3 : Pod reaches 2/2**

```bash
kubectl -n ai get pods -l app.kubernetes.io/name=hermes -w
```

Wait until READY shows `2/2` (or whatever the container count is — should be 2 per the helmrelease). First pull is slow because the image is ~2-3GB; allow 3-5 min.

- [ ] **Step 4 : Pod logs sanity**

```bash
kubectl -n ai logs deploy/hermes -c gateway --tail=30
kubectl -n ai logs deploy/hermes -c dashboard --tail=30
```

Expected: no Python tracebacks. The gateway may complain about Anthropic API connectivity if the key is unset — verify via secret check (Task 18 Step 1).

### Task 19 : Browser smoke test

**Files:** none

- [ ] **Step 1 : Open the dashboard**

Browser → `https://hermes.<your-domain>` (replace `<your-domain>` literally with the value of `SECRET_DOMAIN`, e.g., `kryzql.space`).

Expected: the Hermes dashboard UI loads. May need a few seconds for the first request to warm up the dashboard process.

- [ ] **Step 2 : Configure the model**

In the dashboard → Settings → Model. Pick a Claude model (e.g., `claude-opus-4.7`). Save.

- [ ] **Step 3 : Test message**

Open a chat → send `hello`. Expected: a Claude reply arrives within ~10s.

### Task 20 : Manual PVC cleanup

**Files:** none

- [ ] **Step 1 : Confirm the orphan PVCs are still bound**

```bash
kubectl -n ai get pvc
```

Expected output includes (alongside the new `hermes-data` PVC):
- `ollama-models` 50Gi (Bound) — leftover
- `open-webui-data` 5Gi (Bound) — leftover

- [ ] **Step 2 : Delete them**

```bash
kubectl -n ai delete pvc ollama-models open-webui-data
```

- [ ] **Step 3 : Verify they're gone and the Ceph storage was released**

```bash
kubectl -n ai get pvc
kubectl get pv | grep -E "ollama|open-webui" || echo "PVs cleaned"
```

Expected: only `hermes-data` listed in `pvc`. The PVs backing the old PVCs are either gone (Delete reclaim policy on `ceph-block`) or in `Released` state pending the reclaimer; the script should print `PVs cleaned` after a brief wait.

---

## Rollback

If anything goes badly wrong:

```bash
git revert <merge-sha>
git push
flux reconcile source git flux-system
flux reconcile kustomization cluster-apps -n flux-system
```

This re-creates the `ollama` and `open-webui` Kustomizations and removes the `hermes` Kustomization. The original 50Gi `ollama-models` PVC and 5Gi `open-webui-data` PVC content was already deleted in Task 20 — those re-install fresh.

**Important:** Do NOT delete the 1Password item `hermes` during a rollback — leaving it allows a quick re-deploy later without re-creating the key.

## Follow-ups (out of scope)

- VolSync backup of `hermes-data` (if conversation memory becomes valuable)
- Forward-auth (Authelia/Authentik) in front of the dashboard
- Adding other LLM providers (Gemini, OpenRouter) to the secret + env mapping
- Enabling Hermes' messaging gateways (Telegram, Discord, Slack)
- Re-tune resource limits after 7 days per [[feedback_ram_audit_peak_understates]]
