# SparkyFitness — Design

**Date** : 2026-05-26
**Namespace** : `selfhosted`
**Hostname** : `fitness.${SECRET_DOMAIN}` (envoy-internal)
**Integration target** : Tandoor (`default` namespace) as external food/recipe provider

## 1. Purpose

Deploy [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness) (self-hosted MyFitnessPal alternative) into the `selfhosted` namespace and let it consume Tandoor recipes as a nutrition data source. Connection happens per-user in the SparkyFitness UI by pasting Tandoor's in-cluster URL plus a personal API token.

## 2. Scope

**In scope**
- HelmRelease (bjw-s `app-template` 4.6.2) packaging postgres + server + frontend + garmin + mcp in a single pod
- ExternalSecret pulling 4 fields from a 1Password item `sparkyfitness`
- HTTPRoute on `envoy-internal` with Gatus + Pushover monitoring
- CiliumNetworkPolicy for SparkyFitness ingress
- Patch to Tandoor's existing CiliumNetworkPolicy to allow cross-namespace ingress from SparkyFitness
- VolSync (Kopia → R2) for `postgres-data` and `uploads` PVCs

**Out of scope (v1)**
- OIDC (no IdP in cluster yet)
- SMTP / password reset emails
- Other external providers (OpenFoodFacts, FatSecret, etc.) — user can add later via UI
- Custom Prometheus metrics / dashboards
- Public exposure via Cloudflare Tunnel (internal only)

## 3. Architecture

### 3.1 Pod layout (single `Deployment` named `sparkyfitness`)

| Container | Image | Loopback port | Purpose |
|-----------|-------|---------------|---------|
| `init-db` (initContainer) | `postgres:18.3-alpine` | — | `pg_isready` gate |
| `postgres` | `postgres:18.3-alpine` | 5432 | DB; `PGDATA=/var/lib/postgresql/data/pgdata` |
| `server` | `codewithcj/sparkyfitness_server:v0.16.6.3` | 3010 | Node API; runs migrations on boot |
| `frontend` | `codewithcj/sparkyfitness:v0.16.6.3` | 80 | nginx; proxies `/api/*` to `localhost:3010` |
| `garmin` | `codewithcj/sparkyfitness_garmin:v0.16.6.3` | 8000 | Python microservice (upstream marks WIP) |
| `mcp` | `codewithcj/sparkyfitness_mcp:v0.16.6.3` | 3001 | MCP server for external automation |

All inter-container comms go through `localhost`, mirroring upstream `docker-compose.prod.yml` service names but collapsed onto a single network namespace.

### 3.2 Kubernetes resources

- `Service sparkyfitness` — ports `http:80` (→ frontend) and `mcp:3001` (→ mcp)
- `HTTPRoute app` — hostname `fitness.${SECRET_DOMAIN}`, `parentRef envoy-internal`, Gatus annotation with Pushover alert (`[STATUS] < 500`)
- `PersistentVolumeClaim postgres-data` — 2Gi, `ceph-block`, mounted only on `postgres`
- `PersistentVolumeClaim uploads` — 5Gi, `ceph-block`, mounted on `server` at `/app/SparkyFitnessServer/uploads`
- `PersistentVolumeClaim backup` — 2Gi, `ceph-block`, mounted on `server` at `/app/SparkyFitnessServer/backup` (not VolSync-backed; derivable from DB dump)

### 3.3 Probes

- `postgres` : `tcpSocket :5432`
- `server` : `tcpSocket :3010`
- `frontend` : `httpGet GET /` on `:80` (liveness + readiness + startup)
- `garmin` : `tcpSocket :8000`
- `mcp` : `tcpSocket :3001`

SparkyFitness exposes no documented `/health` endpoint, so TCP/root probes are used.

### 3.4 Resources (initial — to be revisited after 7d Prometheus audit)

| Container | Requests | Limit |
|-----------|----------|-------|
| postgres | 128Mi / 20m | 256Mi |
| server | 256Mi / 50m | 768Mi |
| frontend | 32Mi / 10m | 96Mi |
| garmin | 128Mi / 20m | 384Mi |
| mcp | 96Mi / 10m | 256Mi |

Apply ≥2× observed peak after first week (see [[feedback_ram_audit_peak_understates]]).

## 4. Secrets

### 4.1 1Password item `sparkyfitness`

| Field | Generator | Notes |
|-------|-----------|-------|
| `POSTGRES_PASSWORD` | `openssl rand -base64 32` | postgres superuser, used by server for migrations |
| `APP_DB_PASSWORD` | `openssl rand -base64 32` | limited app user `sparky_app` |
| `API_ENCRYPTION_KEY` | `openssl rand -hex 32` | 64-char hex — encrypts stored provider API tokens |
| `BETTER_AUTH_SECRET` | `openssl rand -base64 48` | session signing + TOTP encryption — **NEVER rotate** once users enable 2FA |

### 4.2 ExternalSecret `sparkyfitness-secret`

Pulls all 4 fields from `ClusterSecretStore onepassword` (creationPolicy: `Owner`). Bootstrap pattern follows [[project_1password_bootstrap_secrets]] — create the item via `op item create sparkyfitness ...` before first reconcile.

### 4.3 Env mapping (server container)

```
envFrom:
  - secretRef: { name: sparkyfitness-secret }
env:
  TZ: Europe/Paris
  NODE_ENV: production
  SPARKY_FITNESS_LOG_LEVEL: INFO
  SPARKY_FITNESS_DB_USER: sparky
  SPARKY_FITNESS_DB_NAME: sparkyfitness
  SPARKY_FITNESS_DB_HOST: localhost
  SPARKY_FITNESS_DB_PORT: "5432"
  SPARKY_FITNESS_APP_DB_USER: sparky_app
  SPARKY_FITNESS_DB_PASSWORD: ${POSTGRES_PASSWORD}        # from secret
  SPARKY_FITNESS_APP_DB_PASSWORD: ${APP_DB_PASSWORD}      # from secret
  SPARKY_FITNESS_API_ENCRYPTION_KEY: ${API_ENCRYPTION_KEY}# from secret
  BETTER_AUTH_SECRET: ${BETTER_AUTH_SECRET}               # from secret
  SPARKY_FITNESS_FRONTEND_URL: https://fitness.${SECRET_DOMAIN}
  SPARKY_FITNESS_DISABLE_SIGNUP: "true"
  GARMIN_MICROSERVICE_URL: http://localhost:8000
```

The `${VAR}` lookups in `envFrom` are interpreted by the container, not by Flux postBuild — no escaping required (this is distinct from [[feedback_flux_postbuild_escape]] which applies to Flux variable substitution inside `args/command`).

`postgres` container only needs `POSTGRES_PASSWORD` via `secretKeyRef`. `frontend`, `garmin`, `mcp` get only their static envs (service host/port + ports).

## 5. Networking

### 5.1 New: `kubernetes/apps/selfhosted/sparkyfitness/app/ciliumnetworkpolicy.yaml`

```yaml
endpointSelector:
  matchLabels:
    app.kubernetes.io/name: sparkyfitness
    app.kubernetes.io/instance: sparkyfitness
ingress:
  - fromEndpoints:
      - matchLabels:
          k8s:io.kubernetes.pod.namespace: network
          gateway.networking.k8s.io/gateway-name: envoy-internal
    toPorts:
      - ports:
          - { port: "80", protocol: TCP }
          - { port: "3001", protocol: TCP }
  - fromEndpoints:
      - matchLabels:
          k8s:io.kubernetes.pod.namespace: kube-system
          k8s:k8s-app: kube-dns
```

No explicit egress rules — defaults to allow. Avoid `toEntities: world` + `toPorts` per [[feedback_cilium_toentities_world]] (broken under DSR).

### 5.2 Patch: `kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml`

Add to the existing `toPorts :80` ingress rule:

```yaml
- matchLabels:
    k8s:io.kubernetes.pod.namespace: selfhosted
    app.kubernetes.io/name: sparkyfitness
```

This mirrors the existing `glance` entry exactly.

### 5.3 Functional connection (post-deploy, per-user, manual)

1. In **Tandoor** → *Settings → API → Personal API Tokens* → generate a token.
2. In **SparkyFitness** → *Settings → External Providers → Add Provider → Tandoor* → enter:
   - `base_url` : `http://tandoor.default.svc.cluster.local`
   - `app_key` : the Tandoor token from step 1
3. SparkyFitness encrypts `app_key` in its DB using `SPARKY_FITNESS_API_ENCRYPTION_KEY`.

No pre-seeding of provider config — Tandoor tokens are per-user, generated in Tandoor's UI.

## 6. Backups (VolSync)

Two `ReplicationSource` resources (`volsync.yaml`), modelled on `kubernetes/apps/default/tandoor/app/volsync.yaml` :

| Source PVC | Repo path | Schedule |
|------------|-----------|----------|
| `postgres-data` | `sparkyfitness/postgres-data` | `0 3 * * *` |
| `uploads` | `sparkyfitness/uploads` | `0 4 * * *` |

`runAsUser` must match the directory owner UID on the NFS repo to avoid root_squash (see [[project_truenas_nfs_root_squash]] and [[project_volsync_nfs_perms]]).

`backup` PVC is not VolSync-backed — it stores SparkyFitness's own in-app backups, which are redundant with a `postgres-data` snapshot.

## 7. Flux Kustomization (`ks.yaml`)

```yaml
metadata:
  name: sparkyfitness
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: sparkyfitness
  dependsOn:
    - { name: rook-ceph-cluster, namespace: rook-ceph }
    - { name: volsync,           namespace: volsync-system }
  interval: 1h
  path: ./kubernetes/apps/selfhosted/sparkyfitness/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: selfhosted
  timeout: 5m
  wait: false
```

Also append `./sparkyfitness/ks.yaml` to `kubernetes/apps/selfhosted/kustomization.yaml`.

## 8. File layout

```
kubernetes/apps/selfhosted/sparkyfitness/
├── ks.yaml
└── app/
    ├── ciliumnetworkpolicy.yaml
    ├── externalsecret.yaml
    ├── helmrelease.yaml
    ├── kustomization.yaml
    ├── ocirepository.yaml          # app-template 4.6.2
    └── volsync.yaml
```

Renovate auto-PRs will track:
- `codewithcj/sparkyfitness*` tags (3 images, pinned identically)
- `postgres:18.3-alpine` tag
- `app-template` OCI tag

## 9. Bootstrap order

1. Create 1Password item `sparkyfitness` with 4 fields.
2. Patch Tandoor CNP (commit + reconcile) so ingress will resolve from day one.
3. Add SparkyFitness directory + entry in selfhosted kustomization; commit.
4. Flux reconciles → ExternalSecret resolves → HelmRelease deploys → pod becomes ready.
5. Open `https://fitness.${SECRET_DOMAIN}`, register first user (becomes admin via order of registration; signup is then disabled).
6. Generate Tandoor API token; configure Tandoor provider in SparkyFitness UI; validate a recipe search.

## 10. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Garmin container is upstream-WIP | Run it but tolerate restart loops; can be disabled by setting `containers.garmin.enabled: false` later |
| RAM peaks during first week unmeasured | Resources set generously (2× rough guess); re-tune after 7d Prom data with ≥2× peak margin |
| Tandoor URL change (rename / namespace move) | Per-user config in SparkyFitness UI — fix in 30 seconds; not a Flux-managed dependency |
| `BETTER_AUTH_SECRET` rotation locks users out of 2FA | Documented in §4.1; 1Password item is the single source of truth |
| First user is admin by registration order | Acceptable for single-user homelab; `SPARKY_FITNESS_ADMIN_EMAIL` can be added later if needed |
