# Crafty Controller (Minecraft) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Crafty Controller (Minecraft server panel) into a new `games` namespace, exposing the web UI through `crafty.${SECRET_DOMAIN}` via the internal envoy gateway and the Minecraft port 25565 to the Tailscale tailnet (forwarded by the cluster's existing tailscale Pod).

**Architecture:** A two-container Pod (Crafty + nginx sidecar). The nginx sidecar listens on HTTP:8000 and reverse-proxies (with WebSocket headers and TLS verify off) to Crafty's hard-coded HTTPS:8443, because Crafty 4 has no HTTP-only mode. Persistence is on a 50 Gi Ceph RBD PVC created inline by the bjw-s app-template. Daily VolSync snapshots ship to the NFS NAS Kopia repo (extended retention). The existing `network/tailscale` Pod gets a `TS_SERVE_CONFIG` patch that forwards tailnet TCP/25565 to `crafty-minecraft.games.svc.cluster.local:25565`.

**Tech Stack:** Flux (OCIRepository + Kustomization), bjw-s `app-template` 4.6.2, Crafty Controller 4.4.7, nginx 1.27-alpine, Cilium NetworkPolicies, External Secrets + 1Password, VolSync + Kopia, Tailscale serve.

**Spec:** `docs/superpowers/specs/2026-04-30-crafty-minecraft-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `kubernetes/apps/games/namespace.yaml` | Namespace placeholder (renamed by parent kustomization) |
| Create | `kubernetes/apps/games/limitrange.yaml` | LimitRange (copy of `selfhosted`) |
| Create | `kubernetes/apps/games/kustomization.yaml` | Namespace root: includes alerts + sops components, lists `crafty/ks.yaml` |
| Create | `kubernetes/apps/games/crafty/ks.yaml` | Flux Kustomization with `dependsOn`, `targetNamespace: games` |
| Create | `kubernetes/apps/games/crafty/app/kustomization.yaml` | Resources index for `app/` |
| Create | `kubernetes/apps/games/crafty/app/ocirepository.yaml` | bjw-s `app-template` 4.6.2 |
| Create | `kubernetes/apps/games/crafty/app/configmap.yaml` | nginx.conf for the sidecar reverse proxy |
| Create | `kubernetes/apps/games/crafty/app/helmrelease.yaml` | Crafty + nginx-sidecar StatefulSet, two ClusterIP Services, inline 50 Gi PVC, HTTPRoute |
| Create | `kubernetes/apps/games/crafty/app/volsync.yaml` | ExternalSecret + ReplicationSource (extended retention) |
| Create | `kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml` | Ingress from envoy-internal + tailscale Pod, egress cluster + world |
| Create | `kubernetes/apps/network/tailscale/app/configmap.yaml` | `tailscale-serve` ConfigMap with `serve.json` |
| Modify | `kubernetes/apps/network/tailscale/app/helmrelease.yaml` | Mount serve-config ConfigMap, add `TS_SERVE_CONFIG` env |
| Modify | `kubernetes/apps/network/tailscale/app/kustomization.yaml` | Add `./configmap.yaml` to resources |

The cluster-level Flux entry (`kubernetes/flux/cluster/ks.yaml`) auto-discovers `kubernetes/apps/<ns>/`, so creating `kubernetes/apps/games/` is enough — no edit there.

`${SECRET_DOMAIN}` and `${NAS_IP}` are injected globally by `cluster-apps`'s `postBuild.substituteFrom: cluster-secrets`, so they are in scope for `games` automatically.

---

## Task 1: Bootstrap the `games` namespace

**Files:**
- Create: `kubernetes/apps/games/namespace.yaml`
- Create: `kubernetes/apps/games/limitrange.yaml`
- Create: `kubernetes/apps/games/kustomization.yaml`

- [ ] **Step 1: Create namespace.yaml**

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: _
  annotations:
    kustomize.toolkit.fluxcd.io/prune: disabled
```

The literal name `_` is rewritten to `games` by the parent kustomization's `namespace: games`, matching the existing `selfhosted` pattern.

- [ ] **Step 2: Create limitrange.yaml**

```yaml
---
apiVersion: v1
kind: LimitRange
metadata:
  name: limits
spec:
  limits:
    - type: Container
      default:
        memory: 256Mi
      defaultRequest:
        cpu: 10m
        memory: 64Mi
      max:
        memory: 8Gi
```

(Identical to `kubernetes/apps/selfhosted/limitrange.yaml`.)

- [ ] **Step 3: Create kustomization.yaml**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: games
components:
  - ../../components/alerts
  - ../../components/sops
resources:
  - ./limitrange.yaml
  - ./namespace.yaml
  - ./crafty/ks.yaml
```

- [ ] **Step 4: Verify locally with flux-local**

Run:
```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/allenporter/flux-local:v8.1.0 \
  test --enable-helm --path kubernetes
```
Expected: no errors related to `games`. The new resources should appear in the build output.

- [ ] **Step 5: Commit**

```bash
git add kubernetes/apps/games/namespace.yaml \
        kubernetes/apps/games/limitrange.yaml \
        kubernetes/apps/games/kustomization.yaml
git commit -m "feat(games): bootstrap namespace"
```

---

## Task 2: Create Flux Kustomization (`ks.yaml`) for Crafty

**Files:**
- Create: `kubernetes/apps/games/crafty/ks.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crafty
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: crafty
  dependsOn:
    - name: rook-ceph-cluster
      namespace: rook-ceph
    - name: volsync
      namespace: volsync-system
    - name: onepassword
      namespace: external-secrets
  interval: 1h
  path: "./kubernetes/apps/games/crafty/app"
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: games
  timeout: 5m
  wait: false
```

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/ks.yaml
git commit -m "feat(crafty): add Flux Kustomization"
```

---

## Task 3: Create OCIRepository for bjw-s app-template

**Files:**
- Create: `kubernetes/apps/games/crafty/app/ocirepository.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/source.toolkit.fluxcd.io/ocirepository_v1.json
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: crafty
spec:
  interval: 15m
  layerSelector:
    mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
    operation: copy
  ref:
    tag: 4.6.2
  url: oci://ghcr.io/bjw-s-labs/helm/app-template
```

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/app/ocirepository.yaml
git commit -m "feat(crafty): add OCIRepository (app-template)"
```

---

## Task 4: Create the nginx sidecar ConfigMap

**Files:**
- Create: `kubernetes/apps/games/crafty/app/configmap.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: crafty-nginx
data:
  nginx.conf: |
    user nginx;
    worker_processes 1;
    error_log /var/log/nginx/error.log warn;
    pid /tmp/nginx.pid;

    events {
      worker_connections 1024;
    }

    http {
      include /etc/nginx/mime.types;
      default_type application/octet-stream;
      sendfile on;
      keepalive_timeout 65;

      # tmp paths writable by non-root
      client_body_temp_path /tmp/client_body;
      proxy_temp_path /tmp/proxy;
      fastcgi_temp_path /tmp/fastcgi;
      uwsgi_temp_path /tmp/uwsgi;
      scgi_temp_path /tmp/scgi;

      server {
        listen 8000;
        server_name _;

        # Required so nginx allows arbitrary file uploads
        # (plugins, mods, world imports via Crafty UI)
        client_max_body_size 0;

        location / {
          proxy_http_version 1.1;
          proxy_redirect off;

          # WebSocket headers — Crafty UI streams server console over WS
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection $http_connection;

          proxy_set_header X-Forwarded-Proto https;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header Host $http_host;

          proxy_pass https://127.0.0.1:8443;
          proxy_ssl_verify off;
          proxy_ssl_server_name on;

          proxy_buffering off;

          # Long timeouts for long-lived UI connections (log streams, large uploads)
          proxy_connect_timeout 3600s;
          proxy_read_timeout    3600s;
          proxy_send_timeout    3600s;
          send_timeout          3600s;
        }
      }
    }
```

The config closely mirrors the upstream `config_examples/nginx.conf.example` from the Crafty repository, with the front-end SSL termination block removed (gateway terminates TLS).

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/app/configmap.yaml
git commit -m "feat(crafty): add nginx sidecar ConfigMap"
```

---

## Task 5: Create the HelmRelease

**Files:**
- Create: `kubernetes/apps/games/crafty/app/helmrelease.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: crafty
spec:
  chartRef:
    kind: OCIRepository
    name: crafty
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
      crafty:
        type: statefulset
        annotations:
          reloader.stakater.com/auto: "true"
        statefulset:
          volumeClaimTemplates: []   # PVC defined under persistence.data below
        pod:
          terminationGracePeriodSeconds: 60
          securityContext:
            runAsUser: 1000
            runAsGroup: 1000
            fsGroup: 1000
            fsGroupChangePolicy: OnRootMismatch
            seccompProfile:
              type: RuntimeDefault
        containers:
          app:
            image:
              # renovate: datasource=docker depName=registry.gitlab.com/crafty-controller/crafty-4
              repository: registry.gitlab.com/crafty-controller/crafty-4
              tag: "4.4.7"
            env:
              TZ: Europe/Paris
            probes:
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 8443
                  failureThreshold: 30
                  periodSeconds: 10
              liveness: &probes
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 8443
                  periodSeconds: 30
                  timeoutSeconds: 5
                  failureThreshold: 3
              readiness: *probes
            resources:
              requests:
                cpu: 250m
                memory: 1Gi
              limits:
                memory: 6Gi
            securityContext:
              allowPrivilegeEscalation: false
              capabilities:
                drop: [ALL]
              readOnlyRootFilesystem: false
          proxy:
            image:
              # renovate: datasource=docker depName=nginx
              repository: nginx
              tag: 1.27-alpine
            resources:
              requests:
                cpu: 10m
                memory: 16Mi
              limits:
                memory: 64Mi
            securityContext:
              allowPrivilegeEscalation: false
              runAsNonRoot: true
              runAsUser: 101         # nginx alpine default uid
              runAsGroup: 101
              capabilities:
                drop: [ALL]
              readOnlyRootFilesystem: true

    service:
      app:
        controller: crafty
        primary: true
        ports:
          http:
            port: 8000
            targetPort: 8000
      minecraft:
        controller: crafty
        ports:
          mc:
            port: 25565
            protocol: TCP
            targetPort: 25565

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
          - crafty.${SECRET_DOMAIN}
        parentRefs:
          - name: envoy-internal
            namespace: network
        rules:
          - backendRefs:
              - identifier: app
                port: http

    persistence:
      data:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 50Gi
        storageClass: ceph-block
        advancedMounts:
          crafty:
            app:
              - path: /crafty/servers
                subPath: servers
              - path: /crafty/backups
                subPath: backups
              - path: /crafty/import
                subPath: import
              - path: /crafty/logs
                subPath: logs
              - path: /crafty/app/config
                subPath: app-config
      nginx-config:
        type: configMap
        name: crafty-nginx
        advancedMounts:
          crafty:
            proxy:
              - path: /etc/nginx/nginx.conf
                subPath: nginx.conf
                readOnly: true
      nginx-tmp:
        type: emptyDir
        advancedMounts:
          crafty:
            proxy:
              - path: /tmp
                subPath: tmp
              - path: /var/cache/nginx
                subPath: cache
              - path: /var/log/nginx
                subPath: log
```

Notes for the engineer:

- `controllers.crafty.type: statefulset` chooses StatefulSet over the default Deployment, giving a stable pod name `crafty-0`.
- `persistence.data` with `type: persistentVolumeClaim` makes the chart create a PVC named `crafty` (matches the spec).
- `app-config` subPath is mounted onto `/crafty/app/config` so Crafty's first-boot copy of `config_original/*.json` lands on the persistent volume (otherwise the bootstrap admin-creds file would live in the image's read-only layer and not be retrievable from logs/UI properly).
- `nginx-tmp` emptyDir is required because `proxy` runs with `readOnlyRootFilesystem: true` and nginx writes to `/tmp`, `/var/cache/nginx`, `/var/log/nginx`.
- Source IPs from clients won't be preserved; Crafty's whitelist is by Mojang username, which is what we rely on.
- Probes are TCP on 8443 (Crafty's actual listener); nginx has no probes — pod-level health is driven by the `app` container.

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/app/helmrelease.yaml
git commit -m "feat(crafty): add HelmRelease (Crafty + nginx sidecar)"
```

---

## Task 6: Create the volsync ExternalSecret + ReplicationSource

**Files:**
- Create: `kubernetes/apps/games/crafty/app/volsync.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: crafty-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: crafty-volsync-secret
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
  name: crafty
spec:
  sourcePVC: crafty
  trigger:
    schedule: "0 4 * * *"
  kopia:
    accessModes:
      - ReadWriteOnce
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: 1000
      runAsGroup: 1000
      fsGroup: 1000
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: crafty-volsync-secret
    retain:
      hourly: 24
      daily: 30
      weekly: 12
      monthly: 6
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/app/volsync.yaml
git commit -m "feat(crafty): add VolSync ExternalSecret and ReplicationSource"
```

---

## Task 7: Create the CiliumNetworkPolicy

**Files:**
- Create: `kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: crafty
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: crafty
      app.kubernetes.io/instance: crafty
  ingress:
    # Web UI from envoy-internal gateway
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "8000"
              protocol: TCP
    # Minecraft TCP from the existing tailscale Pod (forwarded by tailscale serve)
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            app.kubernetes.io/name: tailscale
      toPorts:
        - ports:
            - port: "25565"
              protocol: TCP
    # DNS
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
  egress:
    # cluster + world without toPorts: required to avoid the DSR/toPorts
    # bug recorded in memory `feedback_cilium_toentities_world.md`. The
    # `world` entity covers Crafty's outbound HTTPS to GitLab/PaperMC/
    # CurseForge/Modrinth for plugin and mod downloads; `cluster` covers
    # in-pod loopback (proxy → Crafty) and DNS lookups.
    - toEntities:
        - cluster
        - world
```

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml
git commit -m "feat(crafty): add CiliumNetworkPolicy"
```

---

## Task 8: Create the app/kustomization.yaml index

**Files:**
- Create: `kubernetes/apps/games/crafty/app/kustomization.yaml`

- [ ] **Step 1: Create the file**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./configmap.yaml
  - ./helmrelease.yaml
  - ./volsync.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Step 2: Validate the entire `games` Kustomization with flux-local**

Run:
```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/allenporter/flux-local:v8.1.0 \
  build cluster --path kubernetes/apps/games \
  --enable-helm --output yaml > /tmp/games-build.yaml
```
Expected: clean YAML output, includes Namespace `games`, HelmRelease `crafty`, OCIRepository `crafty`, ConfigMap `crafty-nginx`, ExternalSecret `crafty-volsync`, ReplicationSource `crafty`, CiliumNetworkPolicy `crafty`. Inspect with `grep -E 'kind:|name:' /tmp/games-build.yaml | head -60`.

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/games/crafty/app/kustomization.yaml
git commit -m "feat(crafty): add resources index kustomization"
```

---

## Task 9: Patch the existing `tailscale` Pod for serve-config

**Files:**
- Create: `kubernetes/apps/network/tailscale/app/configmap.yaml`
- Modify: `kubernetes/apps/network/tailscale/app/helmrelease.yaml`
- Modify: `kubernetes/apps/network/tailscale/app/kustomization.yaml`

- [ ] **Step 1: Create the serve-config ConfigMap**

`kubernetes/apps/network/tailscale/app/configmap.yaml`:

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: tailscale-serve
data:
  serve.json: |
    {
      "TCP": {
        "25565": {
          "TCPForward": "crafty-minecraft.games.svc.cluster.local:25565"
        }
      }
    }
```

- [ ] **Step 2: Add the ConfigMap to the kustomization**

Read the current file first:
```bash
cat kubernetes/apps/network/tailscale/app/kustomization.yaml
```

Add `./configmap.yaml` to the `resources:` list. Final content (preserve any existing entries; the additional entry order doesn't matter, but keep it before `helmrelease.yaml` for readability):

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./rbac.yaml
  - ./externalsecrets.yaml
  - ./configmap.yaml
  - ./helmrelease.yaml
```

If the file structure is different from this template (different existing entries), preserve the existing entries verbatim and just add `./configmap.yaml` to the list.

- [ ] **Step 3: Patch `helmrelease.yaml` to mount the ConfigMap and set TS_SERVE_CONFIG**

In `kubernetes/apps/network/tailscale/app/helmrelease.yaml`, modify the `containers.app.env` block (currently containing `TS_KUBE_SECRET`, `TS_USERSPACE`, `TS_AUTH_ONCE`, `TS_HOSTNAME`, `TS_EXTRA_ARGS`) to add `TS_SERVE_CONFIG`. The full new env block:

```yaml
            env:
              TS_KUBE_SECRET: tailscale-state
              TS_USERSPACE: "true"
              TS_AUTH_ONCE: "true"
              TS_HOSTNAME: homelab
              TS_EXTRA_ARGS: "--advertise-exit-node"
              TS_SERVE_CONFIG: /etc/tsconfig/serve.json
```

Then add a `persistence` block at the same nesting level as `controllers` and `defaultPodOptions` (i.e. directly under `values:`). If `persistence` already exists, merge the entries:

```yaml
    persistence:
      tsconfig:
        type: configMap
        name: tailscale-serve
        advancedMounts:
          tailscale:
            app:
              - path: /etc/tsconfig
                readOnly: true
```

- [ ] **Step 4: Validate with flux-local**

```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/allenporter/flux-local:v8.1.0 \
  build cluster --path kubernetes/apps/network/tailscale \
  --enable-helm --output yaml | grep -A2 TS_SERVE_CONFIG
```
Expected output includes:
```
              - name: TS_SERVE_CONFIG
                value: /etc/tsconfig/serve.json
```

- [ ] **Step 5: Commit**

```bash
git add kubernetes/apps/network/tailscale/app/configmap.yaml \
        kubernetes/apps/network/tailscale/app/helmrelease.yaml \
        kubernetes/apps/network/tailscale/app/kustomization.yaml
git commit -m "feat(tailscale): forward TCP/25565 to crafty via TS_SERVE_CONFIG"
```

---

## Task 10: Push and reconcile

- [ ] **Step 1: Push the branch / merge to main**

If you are working on a branch:
```bash
git push -u origin <branch>
gh pr create --title "feat(games): add Crafty Controller (Minecraft)" --fill
```
Wait for the `flux-local` PR check to pass, then merge.

If you are working directly on `main`:
```bash
git push origin main
```

- [ ] **Step 2: Force a Flux reconcile**

```bash
flux --namespace flux-system reconcile kustomization flux-system --with-source
```

- [ ] **Step 3: Wait for the games Kustomization to apply**

```bash
flux get kustomizations -A | grep -E 'crafty|tailscale|games'
```
Expected: all `True` Ready within ~3 minutes (depending on dependencies).

- [ ] **Step 4: Watch pod come up**

```bash
kubectl -n games get pods -w
```
Expected: `crafty-0` reaches `2/2 Running` within ~90 seconds (Crafty cold-start ~30-60s plus image pull on first deploy).

---

## Task 11: Manual 1Password item + capture admin password

- [ ] **Step 1: Create the 1Password item**

In 1Password (default vault), create a new item named `crafty` with two fields:
- `craftyAdminUser` = `admin`
- `craftyAdminPassword` = (leave empty for now)

This is a human-side reference vault — no cluster resource consumes it.

- [ ] **Step 2: Capture the bootstrap admin password from logs**

```bash
kubectl -n games logs crafty-0 -c app | grep -iE 'password|credentials' | head -20
```
Expected output includes a line like `Your default login is...` with a generated password. Copy it.

- [ ] **Step 3: Log into the UI and rotate the password**

Browse to `https://crafty.${SECRET_DOMAIN}` (resolve `${SECRET_DOMAIN}` from your repo's cluster-secrets — the URL ends with whatever domain Flux has configured). Log in as `admin` with the captured password. Go to **Profile → Change Password** and set a new strong password. Update the `craftyAdminPassword` field in the 1Password `crafty` item.

---

## Task 12: Acceptance checks

- [ ] **Step 1: Pod, PVC, services**

```bash
kubectl -n games get pods,pvc,svc
```
Expected:
- `pod/crafty-0` `2/2 Running`
- `pvc/crafty` `Bound 50Gi`
- `service/crafty` `ClusterIP` `8000/TCP`
- `service/crafty-minecraft` `ClusterIP` `25565/TCP`

- [ ] **Step 2: DNS and HTTPS**

```bash
dig +short crafty.${SECRET_DOMAIN} @192.168.42.99
curl -sI https://crafty.${SECRET_DOMAIN}/ | head -5
```
Expected: DNS resolves to `192.168.42.110`. HTTPS HEAD returns `HTTP/2 200` (or 302 redirect to `/login`) with valid TLS chain.

- [ ] **Step 3: Tailscale serve forwarding**

```bash
kubectl -n network exec deploy/tailscale -- tailscale serve status
```
Expected output includes a TCP forward on port 25565 → `crafty-minecraft.games.svc.cluster.local:25565`.

If the command fails with `serve: not supported in userspace mode` or similar, see the **Risks** section of the spec — fallback is to drop `TS_USERSPACE: "true"` from the tailscale HelmRelease and grant a TUN device (out of scope for this plan).

- [ ] **Step 4: Create a Paper server in Crafty**

In the UI:
1. Click **Create new server**
2. Choose **Paper**, version `LATEST` (latest stable)
3. RAM: 4 G min, 4 G max
4. Server port: `25565`
5. Start the server

Watch the console — Paper should download, agree to EULA prompt (Crafty handles automatically when `accept_eula` is set; click the toggle if asked).

- [ ] **Step 5: Enable whitelist**

In the server's settings:
- Set `enforce-whitelist=true`
- Add your players' Mojang usernames to the whitelist

- [ ] **Step 6: Connect from a Tailscale peer**

From a Minecraft client on a peer device (laptop on the tailnet):
- Address: `homelab.<tailnet>.ts.net:25565` (replace `<tailnet>` with your tailnet name)
- Connect — should land in the world.

- [ ] **Step 7: Verify VolSync (after 24 h)**

```bash
kubectl -n games get replicationsource crafty -o wide
```
Expected: `LAST_SYNC` is recent (within last 24 h), `STATUS: Idle`.

On the NAS, list the Kopia repository directory:
```bash
ssh ${NAS_IP} ls -lh /mnt/HDD1X4/VolsyncKopia/crafty
```
Expected: a `kopia.repository` file plus a `p` (pack) directory tree with recent timestamps.

---

## Self-Review

The spec at `docs/superpowers/specs/2026-04-30-crafty-minecraft-design.md` covers Goals, Architecture, Files, Flux Kustomization, HelmRelease (containers, resources, probes, persistence, services, route), nginx ConfigMap, Storage, Backups, Secrets, Networking (gateway + tailscale + CNP), Renovate, Acceptance Criteria, Risks. Tasks above:

- Tasks 1–2: namespace bootstrap + Flux Kustomization (covers Spec "Files", "Flux Kustomization")
- Task 3: OCIRepository (Spec "HelmRelease" intro)
- Task 4: nginx ConfigMap (Spec "ConfigMap: nginx sidecar")
- Task 5: HelmRelease (Spec "HelmRelease" full body — containers, resources, probes, persistence, services, route)
- Task 6: VolSync (Spec "Backups (VolSync)")
- Task 7: CiliumNetworkPolicy (Spec "Networking → CiliumNetworkPolicy")
- Task 8: kustomization index + flux-local validation
- Task 9: tailscale Pod patch (Spec "Networking → Tailscale (Minecraft port)")
- Task 10: push + reconcile
- Task 11: 1Password item + admin password capture (Spec "Secrets")
- Task 12: Acceptance criteria 1–9 from the spec

No spec section is unrepresented. There are no placeholders ("TBD", "implement later") in the plan — every step contains the actual file content or the actual command to run. Type/path consistency: PVC name `crafty` everywhere; Service names `crafty` (port 8000) and `crafty-minecraft` (port 25565); ConfigMap `crafty-nginx` mounted at `/etc/nginx/nginx.conf`; ConfigMap `tailscale-serve` mounted at `/etc/tsconfig/`.

The bjw-s app-template field names used (`controllers.<name>.type`, `containers`, `service.<key>.controller`, `persistence.<key>.advancedMounts.<controller>.<container>`) are validated against the existing `paperless` and `actual-budget` HelmReleases in this repo.
