# Hermes Agent — Design

**Date** : 2026-06-04
**Namespace** : `ai`
**Hostname** : `hermes.${SECRET_DOMAIN}` (envoy-internal)
**Replaces** : Ollama + Open-WebUI (both deleted)

## 1. Purpose

Deploy [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research's self-improving autonomous agent framework) as the sole AI workload in the `ai` namespace, backed by Anthropic Claude via direct API. Remove the existing Ollama + Open-WebUI stack (local LLM serving + chat UI) since the new workflow uses a cloud LLM and Hermes' own dashboard.

## 2. Scope

**In scope**
- New `kubernetes/apps/ai/hermes/` directory with full app-template HelmRelease + ExternalSecret + CNP + OCIRepository
- Update `kubernetes/apps/ai/kustomization.yaml` to drop `./ollama/ks.yaml` and `./open-webui/ks.yaml`, add `./hermes/ks.yaml`
- Delete the on-disk directories `kubernetes/apps/ai/ollama/` and `kubernetes/apps/ai/open-webui/`
- Post-merge manual cleanup of orphan PVCs (`ollama-models` 50Gi, `open-webui-data` 5Gi)
- New 1Password item `hermes` with `api_token` field (operator action before merge)

**Out of scope**
- Forward-auth in front of the dashboard (deferred; rely on envoy-internal perimeter)
- Migration of Open-WebUI chat history (user explicitly chose to discard)
- VolSync backup of the new `hermes-data` PVC (optional later; the data is config + memory caches, easily rebuildable)
- Tuning Hermes' provider list to anything beyond Anthropic (defer)

## 3. Architecture

### 3.1 Pod layout

Single `Deployment` named `hermes`, two containers sharing the same pod (network namespace + PVC) :

| Container | Image | Command | Listens on | Purpose |
|-----------|-------|---------|------------|---------|
| `gateway` | `docker.io/nousresearch/hermes-agent:v2026.5.29.2` | default `["gateway", "run"]` | localhost (internal) | Agent runtime (s6-overlay PID 1, supervises gateway process, runs tools, talks to Anthropic) |
| `dashboard` | same | `["dashboard", "--host", "0.0.0.0", "--no-open"]` | `:9119` | Admin web UI (skill editor, conversation viewer, config) |

Both containers mount the same `/opt/data` PVC. The shared pod network namespace means `dashboard` can reach `gateway` over `localhost`.

### 3.2 Kubernetes resources

- `Service hermes` — port `http: 9119` → container `dashboard`
- `HTTPRoute app` — hostname `hermes.${SECRET_DOMAIN}`, parentRef `envoy-internal` (namespace `network`), Gatus annotation with Pushover alert (`[STATUS] < 500`), `backendRefs: name=hermes, port=http`
- `PersistentVolumeClaim hermes-data` — 5Gi `ceph-block` RWO, mounted at `/opt/data` on both containers
- `Service` only exposes `:9119` (dashboard); `gateway` doesn't need a Service since it's not consumed by other in-cluster apps

### 3.3 Probes

- `dashboard` : `httpGet GET /` on `:9119` (liveness + readiness + startup)
- `gateway` : no documented health endpoint. Use `tcpSocket` on a known internal port, OR skip probes entirely (Kubernetes default = container always considered ready). Decision at implementation time after inspecting what port the gateway binds internally.

### 3.4 Resources (initial)

| Container | Requests | Limit |
|-----------|----------|-------|
| gateway | 256Mi / 100m | 1.5Gi |
| dashboard | 128Mi / 50m | 512Mi |

Hermes invokes Playwright headless browsers on demand for the browser tool. Spikes to 1–2Gi RAM are possible. Revisit after 7 days of Prometheus data per [[feedback_ram_audit_peak_understates]] (apply ≥ 2× observed peak).

### 3.5 Reloader

Annotation `reloader.stakater.com/auto: "true"` on the controller — rolls the pod when the secret changes (e.g., API key rotation).

## 4. Secrets

### 4.1 1Password item `hermes`

| Field | Source / generation |
|-------|---------------------|
| `api_token` | Anthropic API key created at https://console.anthropic.com → Settings → API Keys → Create. Format `sk-ant-api03-...`, ~108 chars. |

Operator creates the item in vault `kubernetes` **before merge**, otherwise ExternalSecret stays `Ready=False` and the pod CrashLoops on missing env var.

### 4.2 ExternalSecret `hermes-secret`

```yaml
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

### 4.3 Env mapping

`gateway` container :
```yaml
envFrom:
  - secretRef: { name: hermes-secret }
```

That single inclusion gives the gateway process `ANTHROPIC_API_KEY`. Hermes' Anthropic provider plugin (`plugins/model-providers/anthropic/__init__.py`) reads `env_vars=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")` — the first match is used.

`dashboard` container needs the same key (to inspect / edit credentials in the UI). Same `envFrom` block.

No `${VAR}` Flux postBuild substitution needed for the secret — `envFrom` reads directly at container start.

## 5. Networking

### 5.1 CiliumNetworkPolicy `hermes`

```yaml
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
          - { port: "9119", protocol: TCP }
  - fromEndpoints:
      - matchLabels:
          k8s:io.kubernetes.pod.namespace: kube-system
          k8s:k8s-app: kube-dns
```

No `egress` block → defaults to allow. Hermes needs egress to :
- `api.anthropic.com:443`
- `accounts.google.com`, `aistudio.google.com` (if user adds Gemini later)
- Various tool endpoints (web search, GitHub API, etc., depending on enabled skills)
- Cluster DNS (kube-dns)

The implicit allow-all egress covers all of these without enumerating. Per [[feedback_cilium_toentities_world]] we avoid `toEntities: world` + `toPorts` (broken under DSR).

### 5.2 Authentication

**No application-level auth**. Relying on the envoy-internal perimeter :
- `hermes.${SECRET_DOMAIN}` is published to UDM Pro DNS (internal-only, not public)
- Only reachable via LAN (`192.168.42.0/24`) or Tailscale tailnet subnet route
- Same pattern as Tandoor, Paperless, Actual Budget, etc. on this cluster

Hermes' upstream docs explicitly warn against `--host 0.0.0.0 --insecure` on internet-facing hosts. Our deployment IS using `0.0.0.0` and IS skipping `--insecure` (we don't pass that flag at all). The acceptable risk is that anyone on LAN or with a valid Tailscale credential could reach the dashboard. Documented and accepted for homelab solo operator.

Future: forward-auth via Authelia / Authentik can be added by extending the HTTPRoute with a `RequestHeaderModifier` filter or moving auth into envoy. Out of scope here.

## 6. File layout

```
kubernetes/apps/ai/hermes/
├── ks.yaml                                # Flux Kustomization, namespace=ai
└── app/
    ├── ciliumnetworkpolicy.yaml
    ├── externalsecret.yaml
    ├── helmrelease.yaml
    ├── kustomization.yaml                 # Kustomize index
    └── ocirepository.yaml                 # bjw-s app-template 4.6.2
```

Plus modifications to existing files :
- `kubernetes/apps/ai/kustomization.yaml` — drop ollama/open-webui entries, add hermes
- Delete entire directories `kubernetes/apps/ai/ollama/`, `kubernetes/apps/ai/open-webui/`

## 7. Flux Kustomization (ks.yaml)

```yaml
metadata:
  name: hermes
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: hermes
  dependsOn:
    - { name: rook-ceph-cluster, namespace: rook-ceph }
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

No `dependsOn: volsync` because we're not snapshotting `hermes-data` (deferred). No `dependsOn: external-secrets` because ESO is up at namespace creation time (already cluster-wide).

## 8. Bootstrap order (operator + Flux)

1. Operator : create 1Password item `hermes` in vault `kubernetes`, field `api_token` = freshly created Anthropic API key
2. Implementation PR landed on `main` :
   - Adds `kubernetes/apps/ai/hermes/` directory
   - Deletes `kubernetes/apps/ai/ollama/` and `kubernetes/apps/ai/open-webui/` directories
   - Edits `kubernetes/apps/ai/kustomization.yaml`
3. Flux reconciles `cluster-apps` → prunes the ollama + open-webui Kustomizations → cascade-deletes their HelmReleases → Helm uninstall removes managed resources
4. Flux reconciles → creates `hermes` Kustomization → applies OCIRepository, ExternalSecret, HelmRelease
5. ExternalSecret pulls `api_token` from 1P → creates `hermes-secret`
6. Helm install creates Deployment + Service + HTTPRoute + PVC + CNP
7. Pod reaches 2/2 Ready
8. Operator : manual `kubectl -n ai delete pvc ollama-models open-webui-data` to release 55Gi Ceph storage
9. Operator : browser test `https://hermes.${SECRET_DOMAIN}` → dashboard loads, configure default model = Claude

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Image `:v2026.5.29.2` is from a fast-moving repo (179k stars, daily commits) and may have bugs | Pinned tag, Renovate auto-PRs on bumps; rollback = git revert |
| Hermes' `gateway` has no documented health endpoint | Skip the liveness/readiness probes for that container (default = always ready); rely on k8s Deployment's restart policy to recover from real crashes |
| Dashboard exposed without auth on tailnet | Documented accepted risk; mitigation = if user wants auth later, add forward-auth in a follow-up |
| Anthropic API key compromise via dashboard exposure | If suspected, rotate the key in console.anthropic.com, update 1P item, force-sync ExternalSecret |
| PVCs not auto-deleted with Helm uninstall | Documented manual `kubectl delete pvc` step in §8 |
| Playwright browsers in image add ~500MB+ to image size → slow first pull | One-time cost; image is cached on nodes after first pull |
| 5Gi `hermes-data` undersized if memory store grows | Resizable later via Ceph block volume expansion (`kubectl edit pvc hermes-data` → spec.resources.requests.storage) |
| No backup on `hermes-data` | Accepted; data is rebuildable (config from defaults, memory regrows from conversations) |

## 10. Out-of-scope follow-ups

- VolSync backup of `hermes-data` if conversation memory becomes valuable
- Forward-auth (Authelia / Authentik / pocketid) — would require deploying an IdP first
- Adding other LLM providers (Gemini, OpenRouter) for fallback / multi-model workflows
- Enabling Hermes' messaging gateways (Telegram, Discord, Slack) — none configured in this PR; if added, each needs its own secret + CNP egress consideration
- Adopting Hermes' `--insecure` flag with TLS termination inside the pod (only useful if removing envoy-internal in front)
