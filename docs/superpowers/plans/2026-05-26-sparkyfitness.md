# SparkyFitness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy SparkyFitness (self-hosted nutrition tracker) into the `selfhosted` namespace and authorize it to call Tandoor in the `default` namespace as a recipe/food data provider. The final manual integration step (per-user Tandoor API token in SparkyFitness UI) is documented but performed by the operator after Flux has reconciled.

**Architecture:** Single bjw-s `app-template` HelmRelease with one `Deployment` containing five containers (`postgres`, `server`, `frontend`, `garmin`, `mcp`) sharing localhost. Secrets injected via ExternalSecret from a new 1Password item. CiliumNetworkPolicy allows ingress from envoy-internal; Tandoor's existing CNP is patched to allow ingress from this new app. VolSync (Kopia → NFS) backs up `postgres-data` and `uploads` PVCs.

**Tech Stack:** Flux CD, Kustomize, bjw-s app-template 4.6.2, postgres:18.3-alpine, codewithcj/sparkyfitness{_server,_garmin,_mcp}:v0.16.6.3, External Secrets Operator + 1Password Connect, Cilium L3/L4 NetworkPolicy, VolSync + Kopia, Envoy Gateway.

**Spec:** `docs/superpowers/specs/2026-05-26-sparkyfitness-design.md`

---

## Pre-flight (one-time, operator only)

### Task 0: Create 1Password item `sparkyfitness`

**Files:** none (1Password CLI only)

- [ ] **Step 1: Generate the four secret values**

```bash
op_postgres=$(openssl rand -base64 32)
op_app_db=$(openssl rand -base64 32)
op_enc=$(openssl rand -hex 32)            # 64 hex chars
op_auth=$(openssl rand -base64 48)
echo "POSTGRES_PASSWORD=$op_postgres"
echo "APP_DB_PASSWORD=$op_app_db"
echo "API_ENCRYPTION_KEY=$op_enc"
echo "BETTER_AUTH_SECRET=$op_auth"
```

Save the four values somewhere safe in case the 1Password create command fails mid-way.

- [ ] **Step 2: Create the 1Password item**

```bash
op item create \
  --category=login \
  --title=sparkyfitness \
  --vault=Homelab \
  POSTGRES_PASSWORD="$op_postgres" \
  APP_DB_PASSWORD="$op_app_db" \
  API_ENCRYPTION_KEY="$op_enc" \
  BETTER_AUTH_SECRET="$op_auth"
```

Adjust `--vault=` if the default 1Password vault used by `ClusterSecretStore onepassword` differs. Inspect with `kubectl -n external-secrets get clustersecretstore onepassword -o yaml` if unsure.

- [ ] **Step 3: Verify the item is readable**

```bash
op item get sparkyfitness --fields POSTGRES_PASSWORD,APP_DB_PASSWORD,API_ENCRYPTION_KEY,BETTER_AUTH_SECRET
```

Expected: all four values print non-empty. If a field is empty, re-create the item (per memory [[project_1password_bootstrap_secrets]] — `op item get`, not `op document get`).

---

## Phase 1: Authorize cross-namespace ingress on Tandoor

This phase runs first so when SparkyFitness comes up it can already reach Tandoor.

### Task 1: Patch Tandoor CiliumNetworkPolicy

**Files:**
- Modify: `kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml:13-23`

- [ ] **Step 1: Add the SparkyFitness matchLabels under the existing `:80` ingress rule**

Edit the file so the first `fromEndpoints` block (the one with `toPorts: 80`) becomes:

```yaml
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: sparkyfitness
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
```

(Only the new 3-line `sparkyfitness` block is added; everything else is untouched.)

- [ ] **Step 2: Validate YAML and Kustomize build**

```bash
yq eval '.spec.ingress[0].fromEndpoints' kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml
kustomize build kubernetes/apps/default/tandoor/app | yq eval 'select(.kind=="CiliumNetworkPolicy")'
```

Expected: three `fromEndpoints` entries (network/envoy-internal, selfhosted/glance, selfhosted/sparkyfitness). `kustomize build` exits 0.

- [ ] **Step 3: Commit (do not push yet — push together with Phase 2 to land atomically)**

```bash
git add kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml
git commit -m "feat(tandoor): allow ingress from selfhosted/sparkyfitness"
```

---

## Phase 2: SparkyFitness manifests

Build the application directory bottom-up so each commit is self-contained and reviewable.

### Task 2: Create directory + Kustomize index

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/kustomization.yaml`

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p kubernetes/apps/selfhosted/sparkyfitness/app
```

- [ ] **Step 2: Write `kustomization.yaml`**

`kubernetes/apps/selfhosted/sparkyfitness/app/kustomization.yaml`:

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./volsync.yaml
  - ./ciliumnetworkpolicy.yaml
```

Note: this references files that do not exist yet — that is intentional. They are created in Tasks 3-7.

- [ ] **Step 3: Do not commit yet** — wait until Task 8.

### Task 3: OCIRepository for app-template

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/ocirepository.yaml`

- [ ] **Step 1: Write the manifest** (copy the version pinned by Tandoor for consistency)

`kubernetes/apps/selfhosted/sparkyfitness/app/ocirepository.yaml`:

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/source.toolkit.fluxcd.io/ocirepository_v1.json
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: sparkyfitness
spec:
  interval: 15m
  layerSelector:
    mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
    operation: copy
  ref:
    tag: 4.6.2
  url: oci://ghcr.io/bjw-s-labs/helm/app-template
```

### Task 4: ExternalSecret

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/externalsecret.yaml`

- [ ] **Step 1: Write the manifest**

`kubernetes/apps/selfhosted/sparkyfitness/app/externalsecret.yaml`:

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: sparkyfitness-secret
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: sparkyfitness-secret
    creationPolicy: Owner
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: sparkyfitness
        property: POSTGRES_PASSWORD
    - secretKey: APP_DB_PASSWORD
      remoteRef:
        key: sparkyfitness
        property: APP_DB_PASSWORD
    - secretKey: API_ENCRYPTION_KEY
      remoteRef:
        key: sparkyfitness
        property: API_ENCRYPTION_KEY
    - secretKey: BETTER_AUTH_SECRET
      remoteRef:
        key: sparkyfitness
        property: BETTER_AUTH_SECRET
```

### Task 5: HelmRelease

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/helmrelease.yaml`

- [ ] **Step 1: Write the manifest**

`kubernetes/apps/selfhosted/sparkyfitness/app/helmrelease.yaml`:

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: sparkyfitness
spec:
  chartRef:
    kind: OCIRepository
    name: sparkyfitness
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
      sparkyfitness:
        annotations:
          reloader.stakater.com/auto: "true"
        containers:
          postgres:
            image:
              repository: postgres
              tag: "18.3-alpine"
            env:
              POSTGRES_USER: sparky
              POSTGRES_DB: sparkyfitness
              POSTGRES_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: sparkyfitness-secret
                    key: POSTGRES_PASSWORD
              PGDATA: /var/lib/postgresql/data/pgdata
            probes:
              liveness: &pgprobe
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 5432
                  initialDelaySeconds: 10
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *pgprobe
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 5432
                  failureThreshold: 30
                  periodSeconds: 5
            resources:
              requests:
                memory: 128Mi
                cpu: 20m
              limits:
                memory: 256Mi
          server:
            image:
              repository: codewithcj/sparkyfitness_server
              tag: "v0.16.6.3"
            envFrom:
              - secretRef:
                  name: sparkyfitness-secret
            env:
              TZ: Europe/Paris
              NODE_ENV: production
              SPARKY_FITNESS_LOG_LEVEL: INFO
              SPARKY_FITNESS_DB_USER: sparky
              SPARKY_FITNESS_DB_NAME: sparkyfitness
              SPARKY_FITNESS_DB_HOST: localhost
              SPARKY_FITNESS_DB_PORT: "5432"
              SPARKY_FITNESS_APP_DB_USER: sparky_app
              SPARKY_FITNESS_DB_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: sparkyfitness-secret
                    key: POSTGRES_PASSWORD
              SPARKY_FITNESS_APP_DB_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: sparkyfitness-secret
                    key: APP_DB_PASSWORD
              SPARKY_FITNESS_FRONTEND_URL: "https://fitness.${SECRET_DOMAIN}"
              SPARKY_FITNESS_DISABLE_SIGNUP: "true"
              GARMIN_MICROSERVICE_URL: http://localhost:8000
            probes:
              liveness: &srvprobe
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 3010
                  initialDelaySeconds: 15
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *srvprobe
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 3010
                  failureThreshold: 60
                  periodSeconds: 5
            resources:
              requests:
                memory: 256Mi
                cpu: 50m
              limits:
                memory: 768Mi
          frontend:
            image:
              repository: codewithcj/sparkyfitness
              tag: "v0.16.6.3"
            env:
              SPARKY_FITNESS_FRONTEND_URL: "https://fitness.${SECRET_DOMAIN}"
              SPARKY_FITNESS_SERVER_HOST: localhost
              SPARKY_FITNESS_SERVER_PORT: "3010"
            probes:
              liveness: &feprobe
                enabled: true
                custom: true
                spec:
                  httpGet:
                    path: /
                    port: 80
                  initialDelaySeconds: 0
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *feprobe
              startup:
                enabled: true
                custom: true
                spec:
                  httpGet:
                    path: /
                    port: 80
                  failureThreshold: 60
                  periodSeconds: 5
            resources:
              requests:
                memory: 32Mi
                cpu: 10m
              limits:
                memory: 96Mi
          garmin:
            image:
              repository: codewithcj/sparkyfitness_garmin
              tag: "v0.16.6.3"
            env:
              GARMIN_SERVICE_PORT: "8000"
              GARMIN_SERVICE_IS_CN: "false"
            probes:
              liveness: &gmprobe
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 8000
                  initialDelaySeconds: 20
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *gmprobe
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 8000
                  failureThreshold: 60
                  periodSeconds: 5
            resources:
              requests:
                memory: 128Mi
                cpu: 20m
              limits:
                memory: 384Mi
          mcp:
            image:
              repository: codewithcj/sparkyfitness_mcp
              tag: "v0.16.6.3"
            envFrom:
              - secretRef:
                  name: sparkyfitness-secret
            env:
              SPARKY_FITNESS_DB_USER: sparky
              SPARKY_FITNESS_DB_NAME: sparkyfitness
              SPARKY_FITNESS_DB_HOST: localhost
              SPARKY_FITNESS_DB_PORT: "5432"
              SPARKY_FITNESS_APP_DB_USER: sparky_app
              SPARKY_FITNESS_DB_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: sparkyfitness-secret
                    key: POSTGRES_PASSWORD
              SPARKY_FITNESS_APP_DB_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: sparkyfitness-secret
                    key: APP_DB_PASSWORD
              MCP_TRANSPORT: http
            probes:
              liveness: &mcpprobe
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 3001
                  initialDelaySeconds: 15
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 5
              readiness: *mcpprobe
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 3001
                  failureThreshold: 60
                  periodSeconds: 5
            resources:
              requests:
                memory: 96Mi
                cpu: 10m
              limits:
                memory: 256Mi

    defaultPodOptions:
      securityContext:
        seccompProfile:
          type: RuntimeDefault

    service:
      app:
        controller: sparkyfitness
        ports:
          http:
            port: 80
          mcp:
            port: 3001

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
          - "fitness.${SECRET_DOMAIN}"
        parentRefs:
          - name: envoy-internal
            namespace: network
        rules:
          - backendRefs:
              - name: sparkyfitness
                port: 80

    persistence:
      postgres-data:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 2Gi
        storageClass: ceph-block
        advancedMounts:
          sparkyfitness:
            postgres:
              - path: /var/lib/postgresql/data
      uploads:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 5Gi
        storageClass: ceph-block
        advancedMounts:
          sparkyfitness:
            server:
              - path: /app/SparkyFitnessServer/uploads
      backup:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 2Gi
        storageClass: ceph-block
        advancedMounts:
          sparkyfitness:
            server:
              - path: /app/SparkyFitnessServer/backup

    disableDefaultSecurityContext: All
```

Notes:
- `${SECRET_DOMAIN}` is substituted by Flux postBuild at reconcile time — leave literal in YAML.
- `disableDefaultSecurityContext: All` matches the tandoor pattern; the upstream images require write access at non-standard paths.
- Three containers (`server`, `mcp`) each declare `SPARKY_FITNESS_DB_PASSWORD` explicitly even though `envFrom` already loads `POSTGRES_PASSWORD` — this is the rename, not a duplicate.

### Task 6: CiliumNetworkPolicy

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/ciliumnetworkpolicy.yaml`

- [ ] **Step 1: Write the manifest**

`kubernetes/apps/selfhosted/sparkyfitness/app/ciliumnetworkpolicy.yaml`:

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: sparkyfitness
spec:
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
            - port: "80"
              protocol: TCP
            - port: "3001"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
```

No `egress` block: defaults to allow. Per [[feedback_cilium_toentities_world]], do **not** add `toEntities: world` with `toPorts`.

### Task 7: VolSync

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/app/volsync.yaml`

- [ ] **Step 1: Write the manifest**

`kubernetes/apps/selfhosted/sparkyfitness/app/volsync.yaml`:

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: sparkyfitness-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: sparkyfitness-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: sparkyfitness-postgres-data
spec:
  sourcePVC: sparkyfitness-postgres-data
  trigger:
    schedule: "0 3 * * *"
  kopia:
    accessModes:
      - ReadWriteOnce
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: 999
      runAsGroup: 999
      fsGroup: 999
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: sparkyfitness-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
---
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: sparkyfitness-uploads
spec:
  sourcePVC: sparkyfitness-uploads
  trigger:
    schedule: "30 3 * * *"
  kopia:
    accessModes:
      - ReadWriteOnce
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: 999
      runAsGroup: 999
      fsGroup: 999
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: sparkyfitness-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

(`runAsUser: 999` matches the tandoor template; if mover fails with NFS permission errors, see [[project_volsync_nfs_perms]] / [[project_truenas_nfs_root_squash]] and chown the repo dir on the NAS.)

### Task 8: Flux Kustomization (`ks.yaml`) + register in selfhosted index

**Files:**
- Create: `kubernetes/apps/selfhosted/sparkyfitness/ks.yaml`
- Modify: `kubernetes/apps/selfhosted/kustomization.yaml:19` (append one line)

- [ ] **Step 1: Write `ks.yaml`**

`kubernetes/apps/selfhosted/sparkyfitness/ks.yaml`:

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: sparkyfitness
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: sparkyfitness
  dependsOn:
    - name: rook-ceph-cluster
      namespace: rook-ceph
    - name: volsync
      namespace: volsync-system
  interval: 1h
  path: "./kubernetes/apps/selfhosted/sparkyfitness/app"
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: selfhosted
  timeout: 5m
  wait: false
```

- [ ] **Step 2: Append to `kubernetes/apps/selfhosted/kustomization.yaml`**

Add the line `- ./sparkyfitness/ks.yaml` to the `resources:` list (after the existing `obsidian-livesync` entry):

```yaml
resources:
  - ./limitrange.yaml
  - ./namespace.yaml
  - ./it-tools/ks.yaml
  - ./bentopdf/ks.yaml
  - ./paperless/ks.yaml
  - ./glance/ks.yaml
  - ./immich/ks.yaml
  - ./nextcloud/ks.yaml
  - ./actual-budget/ks.yaml
  - ./obsidian-livesync/ks.yaml
  - ./sparkyfitness/ks.yaml
```

- [ ] **Step 3: Verify Kustomize build for the app dir and the selfhosted index**

```bash
kustomize build kubernetes/apps/selfhosted/sparkyfitness/app | wc -l
kustomize build kubernetes/apps/selfhosted | grep -c sparkyfitness
```

Expected: app build produces > 100 lines (rendered manifests), selfhosted build references sparkyfitness at least once.

- [ ] **Step 4: Run flux-local diff against main if locally installed**

```bash
which flux-local && flux-local diff ks --path . --branch main --all-namespaces 2>&1 | head -80
```

Expected: shows new resources for SparkyFitness; no errors about missing variables or invalid schemas. Skip this step if flux-local is not installed — CI will run it on the PR.

- [ ] **Step 5: Commit everything (Phase 1 + Phase 2)**

Encrypted SOPS files (none in this PR) would need `git add -f`; here all files are plain YAML, so a normal add is fine. Per [[feedback_gitignore_sops]] we still verify nothing was silently skipped:

```bash
git status --short
git add kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/sparkyfitness/ \
        kubernetes/apps/selfhosted/kustomization.yaml
git status --short                                              # confirm nothing else was added
git commit -m "feat(selfhosted): add sparkyfitness with tandoor integration"
```

Verify the commit shows all expected files:

```bash
git show --stat HEAD
```

Expected: 8 files changed (1 tandoor CNP modification + 7 new files under sparkyfitness/).

---

## Phase 3: Deploy + verify

### Task 9: Push and let Flux reconcile

**Files:** none

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Force reconcile** (otherwise wait up to 1h interval)

```bash
flux reconcile source git flux-system
flux reconcile kustomization cluster-apps
flux reconcile kustomization sparkyfitness -n flux-system
```

Expected: each command exits 0 within ~30s.

- [ ] **Step 3: Verify ExternalSecret resolved**

```bash
kubectl -n selfhosted get externalsecret sparkyfitness-secret -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
echo
kubectl -n selfhosted get secret sparkyfitness-secret -o jsonpath='{.data}' | jq 'keys'
```

Expected: condition `True`; secret contains 4 keys (POSTGRES_PASSWORD, APP_DB_PASSWORD, API_ENCRYPTION_KEY, BETTER_AUTH_SECRET).

- [ ] **Step 4: Verify pod becomes ready**

```bash
kubectl -n selfhosted get pods -l app.kubernetes.io/name=sparkyfitness -w
```

Expected within ~3 minutes: `5/5  Running`. If any container is CrashLoopBackOff, jump to Task 10 troubleshooting.

- [ ] **Step 5: Verify postgres user `sparky_app` was created**

The server bootstrap creates the limited app user on first run. Confirm with:

```bash
kubectl -n selfhosted exec deploy/sparkyfitness -c postgres -- \
  psql -U sparky -d sparkyfitness -c '\du'
```

Expected: at least two roles listed (`sparky` superuser, `sparky_app`).

- [ ] **Step 6: Verify HTTPRoute and DNS**

```bash
kubectl -n selfhosted get httproute -l app.kubernetes.io/name=sparkyfitness
dig +short fitness.${SECRET_DOMAIN} @192.168.42.99
```

Replace `${SECRET_DOMAIN}` literally with your domain (e.g., from `kubernetes/components/sops` or your shell env). Expected: HTTPRoute Accepted; DNS resolves to the envoy-internal IP (`192.168.42.110`).

- [ ] **Step 7: Open the app in a browser**

Go to `https://fitness.<your-domain>`. Expected: SparkyFitness login/registration screen renders. Register the first account — it becomes the admin since no users exist yet.

### Task 10: Functional Tandoor integration test (manual)

**Files:** none

- [ ] **Step 1: Generate a Tandoor API token**

In Tandoor (`https://tandoor.<your-domain>`), open *Settings → API → API Tokens* → click *New* → name it `sparkyfitness` → copy the token.

- [ ] **Step 2: Add Tandoor as an external provider in SparkyFitness**

In SparkyFitness, navigate to *Settings → External Providers → Add Provider*. Choose **Tandoor** and fill:

- Base URL: `http://tandoor.default.svc.cluster.local`
- API Key: paste the Tandoor token from Step 1

Save.

- [ ] **Step 3: Test the integration**

In SparkyFitness, open *Foods → Search* and select the Tandoor provider in the source dropdown. Search for a recipe name you know exists in your Tandoor instance.

Expected: results appear within ~2s. If you get an error, check:

```bash
kubectl -n selfhosted logs deploy/sparkyfitness -c server --tail=80
kubectl -n default   logs -l app.kubernetes.io/name=tandoor   --tail=80
```

Look for HTTP 401 (bad token), 403 (CNP blocking — confirm Phase 1 was applied), or connection refused (DNS / wrong base URL).

- [ ] **Step 4: Confirm Gatus is monitoring the endpoint**

```bash
kubectl -n observability logs -l app.kubernetes.io/name=gatus --tail=200 | grep -i sparky
```

Expected: a recent successful check for `fitness.<your-domain>`. If not present, wait ~5 minutes for Gatus to pick up the new annotated route.

### Task 11: Trigger first VolSync backup

**Files:** none

- [ ] **Step 1: Manually trigger the postgres backup ahead of cron**

```bash
kubectl -n selfhosted patch replicationsource sparkyfitness-postgres-data \
  --type=merge -p '{"spec":{"trigger":{"manual":"first-run"}}}'
```

- [ ] **Step 2: Watch the mover Job**

```bash
kubectl -n selfhosted get jobs -l volsync.backube/replication-source=sparkyfitness-postgres-data -w
```

Expected: Job runs to Completion. If it fails with NFS permission errors, apply the fix from [[project_volsync_nfs_perms]] (chown the kopia repo dir on the NAS to UID 999), then retry.

- [ ] **Step 3: Confirm snapshot in Kopia repo**

```bash
kubectl -n volsync-system exec deploy/volsync-kopia-maintenance -- \
  kopia snapshot list --json 2>/dev/null | jq '.[] | select(.source.path|test("sparkyfitness"))'
```

(Skip this step if you don't have a maintenance pod handy; the Job completion is sufficient verification.)

- [ ] **Step 4: Repeat for uploads**

```bash
kubectl -n selfhosted patch replicationsource sparkyfitness-uploads \
  --type=merge -p '{"spec":{"trigger":{"manual":"first-run"}}}'
kubectl -n selfhosted get jobs -l volsync.backube/replication-source=sparkyfitness-uploads -w
```

---

## Phase 4: Post-deploy follow-up

### Task 12: 7-day resource audit (calendar reminder)

**Files:** none

- [ ] **Step 1: Set a reminder for 2026-06-02**

Per [[feedback_ram_audit_peak_understates]], the 7d Prometheus peak understates real spikes. Use ≥2× observed peak when re-tuning.

- [ ] **Step 2: Pull memory/cpu peaks after one week**

```bash
# Run on or after 2026-06-02
for c in postgres server frontend garmin mcp; do
  echo "=== $c ==="
  # In Grafana / kube-prometheus-stack: pod=sparkyfitness*, container=$c
  # Or scrape from Prometheus directly:
  kubectl -n observability exec deploy/prometheus-operated -- promtool query instant http://localhost:9090 \
    "max_over_time(container_memory_working_set_bytes{namespace='selfhosted', pod=~'sparkyfitness.*', container='$c'}[7d])"
done
```

- [ ] **Step 3: Update HelmRelease resources block if peaks exceed 60% of limits**

Edit `kubernetes/apps/selfhosted/sparkyfitness/app/helmrelease.yaml`, set new `limits.memory` to `2 × observed_peak_MiB`, commit, and let Flux roll the deployment.

---

## Rollback

If the deployment misbehaves badly:

```bash
# Suspend Flux for this app
flux suspend kustomization sparkyfitness -n flux-system

# Optional: scale to zero while debugging
kubectl -n selfhosted scale deploy sparkyfitness --replicas=0

# Revert the commit if needed
git revert <commit-sha>
git push
flux resume kustomization sparkyfitness -n flux-system
```

The Tandoor CNP patch (Task 1) is harmless on its own — it can stay even if the SparkyFitness directory is removed; the matchLabels will just never match anything.
