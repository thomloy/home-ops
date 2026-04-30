# Crafty Controller — Minecraft Server Hosting

**Date:** 2026-04-30
**Namespace:** games (new)
**Status:** Approved

---

## Context

Host a Minecraft server in the cluster, accessible to a small group of players (3 initially) over Tailscale. The user wants a web UI to manage the server (start/stop, console, upload plugins/mods, schedule backups, manage whitelist) without touching YAML for day-to-day server administration.

The server starts as Paper (vanilla-compatible client, plugin-ready) and may later switch to a hybrid loader (Arclight / Mohist) when modpacks are introduced. Crafty Controller is the platform — it manages the Minecraft Java processes as child processes inside its own container.

This is the first consumer in the cluster of:
- The Tailscale operator's `loadBalancerClass: tailscale` Service type
- A `games` namespace (created here)

---

## Goals

- Single Minecraft server reachable at `minecraft.<tailnet>.ts.net:25565` for Tailscale peers, with whitelist enforced.
- Crafty Controller web UI reachable at `https://crafty.kryzql.space` over the internal gateway (LAN + Tailscale, no public DNS).
- World data on Rook-Ceph block storage with 3-replica durability.
- Daily VolSync backups to NFS NAS with extended retention (world data has long-tail value).
- All Minecraft content (worlds, plugins, mods, configs) lives in the PVC and is uploaded via the Crafty UI — accepted GitOps drift in exchange for the requested UX.
- Renovate-driven version bumps (manual approval, not auto-merge).

## Non-goals

- Multiple simultaneous Minecraft servers exposed externally (architecture supports it via Crafty UI, but only port 25565 is wired to Tailscale for now).
- Bedrock / Geyser cross-platform.
- BlueMap / Dynmap web map (optional post-MVP, installed as a plugin via UI).
- Velocity proxy / multi-server fleet.
- SSO / Authelia in front of Crafty (uses Crafty's built-in auth, consistent with all other selfhosted apps).
- Public exposure via Cloudflare Tunnel.

---

## Architecture

```
Tailscale peer ──► minecraft.<tailnet>.ts.net:25565
                          │
                          ▼
              ┌──────── games ns ────────┐
              │                          │
LAN/Tailscale │  Service: minecraft      │
client        │  type: LoadBalancer      │
   │          │  loadBalancerClass:      │
   │          │  tailscale (TCP 25565)   │
   │          │           │              │
   │          │           ▼              │
   │          │      ┌─────────┐         │
   │          │      │ Crafty  │ Pod     │
   │          │      │ pod     │         │
   ▼          │      │ + child │         │
192.168.42.110│      │ JVM(s)  │         │
envoy-internal│      └────┬────┘         │
(network ns)  │           │              │
   │  HTTPS   │  Service: crafty (ClusterIP, HTTP 8000)
   └──HTTPRoute──────►   │              │
              │           ▼              │
              │      ┌─────────┐         │
              │      │ PVC     │ 50Gi    │
              │      │ Ceph    │ RBD     │
              │      └────┬────┘         │
              └───────────┼──────────────┘
                          │ daily snapshot
                          ▼
              ┌── volsync-system ns ──┐
              │  ReplicationSource    │
              │  → Kopia mover        │
              │  → NFS NAS            │
              └───────────────────────┘
```

---

## Files

```
kubernetes/apps/games/
├── kustomization.yaml                # Namespace root, references ./crafty/ks.yaml + sops/alerts components
├── namespace.yaml                    # Namespace games
├── limitrange.yaml                   # Default container limits (copied from selfhosted)
└── crafty/
    ├── ks.yaml                       # Flux Kustomization
    └── app/
        ├── kustomization.yaml        # Resources index
        ├── ocirepository.yaml        # bjw-s app-template 4.6.2
        ├── helmrelease.yaml          # Crafty + nginx sidecar StatefulSet + 2 Services + inline PVC + HTTPRoute
        ├── configmap.yaml            # nginx.conf for the in-pod HTTPS-to-HTTP reverse proxy
        ├── volsync.yaml              # ExternalSecret (Kopia creds) + ReplicationSource (extended retention)
        └── ciliumnetworkpolicy.yaml  # Ingress + egress rules
```

The `volsync` Kustomize component is **not** included; pattern follows `actual-budget` (full inline definition for both ExternalSecret and ReplicationSource so retention can be customised).

A new `kubernetes/apps/games/` root entry must be referenced from the cluster-level Flux entry point (verified during plan writing).

---

## Flux Kustomization (`ks.yaml`)

- `targetNamespace: games`
- `dependsOn`:
  - `rook-ceph-cluster` (rook-ceph) — for the Ceph RBD PVC
  - `volsync` (volsync-system) — for the inline `ReplicationSource` to be reconciled
  - `external-secrets-stores` (external-secrets) — for the Kopia-credentials `ExternalSecret`
  - `tailscale` (network) — first consumer of `loadBalancerClass: tailscale`
- No Kustomize `components` entry (no volsync component, full inline definition).
- `interval: 1h`, `timeout: 5m`, `wait: false`, `prune: true` (matching repo defaults).

---

## HelmRelease (bjw-s app-template)

**Chart**: `oci://ghcr.io/bjw-s-labs/helm/app-template` tag `4.6.2` via OCIRepository.

**Containers** (two-container pod):

1. `app` — Crafty Controller
   ```
   # renovate: datasource=docker depName=registry.gitlab.com/crafty-controller/crafty-4
   registry.gitlab.com/crafty-controller/crafty-4:4.4.7
   ```
   Pinned tag, manual Renovate bump approval (not auto-merge — major Crafty versions can require DB migration).

2. `proxy` — nginx-alpine acting as in-pod HTTPS-to-HTTP reverse proxy
   ```
   # renovate: datasource=docker depName=nginx
   nginx:1.27-alpine
   ```
   Listens on `:8000` (plain HTTP), proxies to `https://127.0.0.1:8443` with TLS verify off and WebSocket headers. Pattern is taken directly from the upstream Crafty repository's `config_examples/nginx.conf.example`. Required because Crafty 4 has no HTTP-only mode and serves only HTTPS:8443 with a self-signed certificate.

**Controller**: `StatefulSet`, single replica. Chosen over `Deployment` for the stable pod name `crafty-0` (log retrieval ergonomics) and ordered shutdown semantics; both are functionally valid against an RWO PVC.

**Pod spec**:
- `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- `readOnlyRootFilesystem: false` (Crafty writes inside `/crafty/app/` at runtime)
- `seccompProfile: RuntimeDefault`
- `terminationGracePeriodSeconds: 60` (allow Crafty to gracefully stop child JVMs on SIGTERM)

**Resources** (per container):
- `app`: requests `cpu 250m / memory 1Gi`, limit `memory 6Gi` (no CPU limit). Sized for Crafty (~200 MiB) + 1 Paper server with `MEMORY=4G` + JVM headroom.
- `proxy`: requests `cpu 10m / memory 16Mi`, limit `memory 64Mi`. nginx is essentially free.

Bump `app` memory limit to ~10–12 GiB if a second server is started concurrently.

**Probes**:
- `app` (Crafty): TCP port 8443
  - `startupProbe`: TCP 8443, `failureThreshold: 30`, `periodSeconds: 10` (Crafty cold-start ~30–60s)
  - `livenessProbe`, `readinessProbe`: TCP 8443
- `proxy` (nginx): no probes (single nginx process, restarts via pod liveness if pod-wide failure)

**Persistence** (PVC created inline by app-template, name = `crafty` per app-template default):
```yaml
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
          - path: /crafty/backups
          - path: /crafty/import
          - path: /crafty/logs
  nginx-config:
    type: configMap
    name: crafty-nginx
    advancedMounts:
      crafty:
        proxy:
          - path: /etc/nginx/nginx.conf
            subPath: nginx.conf
```

**Services** (two distinct):
```yaml
service:
  app:                         # Web UI: gateway → nginx sidecar (port 8000) → Crafty HTTPS (8443)
    controller: crafty
    primary: true
    ports:
      http:
        port: 8000             # nginx sidecar listen port
        targetPort: 8000
  minecraft:                   # MC port via Tailscale operator
    controller: crafty
    type: LoadBalancer
    annotations:
      tailscale.com/hostname: minecraft
    spec:
      loadBalancerClass: tailscale
      externalTrafficPolicy: Local
    ports:
      mc:
        port: 25565
        protocol: TCP
        targetPort: 25565
```

**HTTPRoute** (generated by app-template):
```yaml
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
          - identifier: crafty
            port: http
```
`${SECRET_DOMAIN}` resolves to `kryzql.space` via Flux substitution — consistent with every other selfhosted app in the repo.

---

## ConfigMap: nginx sidecar (`crafty-nginx`)

A minimal nginx config that listens on port 8000 (HTTP) and reverse-proxies to `https://127.0.0.1:8443` with TLS verification disabled and full WebSocket header support. Pattern derived directly from the upstream Crafty repository's `config_examples/nginx.conf.example`, simplified to remove the SSL-termination front-end (TLS is terminated at the cluster gateway, not in-pod).

Key elements:
- `listen 8000;` (HTTP only, no TLS in-pod)
- `proxy_pass https://127.0.0.1:8443;`
- WebSocket headers: `Upgrade`, `Connection $http_connection`
- `proxy_ssl_verify off;` (Crafty's cert is self-signed, untrusted)
- `proxy_buffering off;`, `client_max_body_size 0;` (file uploads via UI: plugins/mods/imports)
- Long timeouts (`3600s`) — Crafty UI streams server logs over long-lived connections

The exact `nginx.conf` is provided verbatim in the implementation plan.

---

## Storage

**PVC** `crafty`:
- StorageClass: `ceph-block`
- Access mode: `ReadWriteOnce`
- Size: `50Gi`
- Created by the bjw-s app-template `persistence.data` block (matches `actual-budget` pattern).

**Why Ceph RBD**:
- Low-latency small writes (Minecraft chunk saves)
- 3-replica durability (survives single-node loss mid-game)
- Online expansion via `kubectl edit pvc` if storage tightens
- Consistent with paperless / immich / actual-budget pattern

**Layout** (managed by Crafty itself, documented for context):
```
/crafty/
├── servers/<uuid>/{server.jar, world/, plugins/, server.properties, ...}
├── backups/                    # Crafty-internal backups
├── import/                     # UI staging for uploads
└── logs/
```

**Sizing rationale**:
| Item | Estimate |
|---|---|
| Crafty app + SQLite DB | ~500 MiB |
| 1 Paper world (3 players, ~6 mo exploration) | 5–10 GiB |
| Crafty internal backups (3 rotations) | 15–25 GiB |
| Plugins/mods JARs | ~1 GiB |
| Headroom for a future second server | ~10 GiB |
| **Total** | **~40–50 GiB** |

---

## Backups (VolSync)

Defined entirely inline in `app/volsync.yaml` (no component), pattern of `actual-budget`. Two resources:

**1. `ExternalSecret` `crafty-volsync`** — pulls Kopia credentials from the shared 1Password item `volsync-template` and produces secret `crafty-volsync-secret` containing `KOPIA_PASSWORD` and `KOPIA_REPOSITORY=filesystem:///mnt/repository`.

**2. `ReplicationSource` `crafty`** — daily Ceph snapshot via `csi-ceph-blockpool` snapshot class, then a Kopia mover Pod uploads to NFS at `/mnt/HDD1X4/VolsyncKopia` on `${NAS_IP}`.

- `sourcePVC: crafty`
- `trigger.schedule: "0 4 * * *"` (04:00 daily, avoids overlap with paperless 02:30)
- `kopia.repository: crafty-volsync-secret`
- `moverSecurityContext`: runAsUser/runAsGroup/fsGroup `1000`
- `storageClassName: ceph-block`
- `volumeSnapshotClassName: csi-ceph-blockpool`
- `accessModes: [ReadWriteOnce]`
- `compression: zstd-fastest`
- `parallelism: 2`

**Retention** (longer than the typical repo default of 24h/7d, world data has long-tail value):
```yaml
retain:
  hourly: 24
  daily: 30
  weekly: 12
  monthly: 6
```

**Crash consistency**: Ceph snapshots are crash-consistent (equivalent to `kill -9` + reboot). Paper / Vanilla journals survive this without intervention. No pre-snapshot freeze required.

**Crafty internal backups** (zip of world via UI) and VolSync are complementary:
- Crafty UI: fast world-level restore
- VolSync: PVC-level disaster recovery

---

## Secrets

**One ExternalSecret deployed** — `crafty-volsync` for Kopia credentials (defined in `volsync.yaml`, see Backups section). No other ExternalSecret.

### Crafty admin password handling

Crafty 4.x generates a random `admin` password at first boot and prints it once to the pod logs. There is no upstream-supported environment variable to override it. Three options were evaluated:

1. **Manual** — fetch initial password from logs, log into UI, change it, archive in 1Password by hand. (Picked.)
2. **InitContainer patches `users.json` SQLite** — fragile across Crafty upgrades.
3. **PostStart calls Crafty REST API to reset password** — race condition with startup, complex.

Option 1 is a 5-minute one-time task. The chosen password is then archived in 1Password as a human-side vault entry, not consumed by any cluster resource. The user database itself is protected by VolSync backups (the SQLite DB lives in the PVC).

**1Password item to create manually post-deploy** (vault `default`):
- Name: `crafty`
- Fields:
  - `craftyAdminUser` = `admin`
  - `craftyAdminPassword` = ⟨user-chosen strong password set via Crafty UI⟩

---

## Networking

### Internal gateway (web UI)

```
client → 192.168.42.110:443 (envoy-internal, TLS *.kryzql.space)
       → HTTPRoute crafty.kryzql.space
       → Service ClusterIP crafty:8000 (plain HTTP in-cluster)
       → Pod nginx sidecar :8000 (plain HTTP)
       → loopback https://127.0.0.1:8443 (TLS, skip-verify) → Crafty
```

DNS `crafty.kryzql.space` is published to the UDM Pro Max via ExternalDNS internal provider — no Cloudflare record. Auth is Crafty's built-in login plus optional TOTP 2FA configurable in-app.

The HTTP hop between gateway and nginx sidecar is acceptable because (a) the pod has no external network path (CNP-enforced), (b) every other selfhosted app in this repo follows the same pattern. The HTTPS hop between nginx and Crafty is loopback within the pod's own network namespace — never visible on any wire.

### Tailscale (Minecraft port)

```
peer → minecraft.<tailnet>.ts.net:25565
     → Service LoadBalancer (loadBalancerClass: tailscale, hostname: minecraft)
     → Pod:25565 → Java child process
```

`externalTrafficPolicy: Local` to preserve client source IPs in Minecraft logs (helpful for ban management). Whitelist enforced inside Crafty as defense in depth — a Tailscale peer who somehow appears uninvited cannot join without being on the Mojang whitelist.

### CiliumNetworkPolicy

**Ingress**:
- From namespace `network` (envoy gateway pod identity) → port 8000/TCP
- From Tailscale operator pod identity → port 25565/TCP

**Egress**:
- DNS to kube-dns (CoreDNS)
- `toEntities: [cluster, world]` **without** `toPorts` — known-good pattern from immich. `toEntities: world` + `toPorts` is broken in DSR mode on this cluster (recorded in memory `feedback_cilium_toentities_world.md`).
- Crafty needs outbound HTTPS to download server JARs, plugins, mods (papermc.io, modrinth.com, curseforge.com, registry.gitlab.com, github.com).

---

## Renovate

```yaml
# helmrelease.yaml
# renovate: datasource=docker depName=registry.gitlab.com/crafty-controller/crafty-4
tag: 4.4.7
```

Auto-merge **disabled** for Crafty for at least the first few releases — DB schema changes between major versions warrant manual confirmation. Existing Renovate rules cover the bjw-s `app-template` chart bump cadence.

---

## Acceptance Criteria

1. `kubectl -n games get pods` → `crafty-0` Running, all probes passing.
2. `kubectl -n games get pvc crafty` → Bound, 50Gi.
3. `kubectl -n games get svc` → two Services; `minecraft` has an `EXTERNAL-IP` in the Tailscale CGNAT range (`100.x.x.x`).
4. `dig crafty.kryzql.space @192.168.42.99` → `192.168.42.110`.
5. Browser `https://crafty.kryzql.space` → Crafty login page, valid wildcard cert.
6. `kubectl -n games logs crafty-0 | grep -i password` returns the bootstrap admin password (one-time retrieval, then archived in 1Password and rotated via UI).
7. After 24 h: `kubectl -n games get replicationsource crafty` shows `LAST_SYNC` recent and `STATUS: Idle`; corresponding Kopia snapshot visible on the NAS NFS share.
8. Minecraft client connects from a Tailscale peer to `minecraft.<tailnet>.ts.net:25565` and joins the Paper server (after being added to the whitelist via Crafty UI).
9. CiliumNetworkPolicy `kubectl -n games describe cnp` shows expected ingress/egress; pod can `curl https://api.papermc.io/` (egress works), cannot reach a random pod in another namespace (ingress to others denied).

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| First consumer of Tailscale `loadBalancerClass` — operator bugs may surface | Validate the LoadBalancer Service comes up green before connecting clients; fallback is NodePort + Tailscale subnet routing if the operator path fails. |
| Pod kill leaves orphan Java processes | `terminationGracePeriodSeconds: 60` lets Crafty SIGTERM its children; on hard kill, Paper journal recovery handles it. |
| Crafty major-version upgrade breaks SQLite schema | Manual Renovate approval + VolSync J-1 backup + Flux rollback via `helmrelease.spec.chartRef.tag`. |
| World corruption on ungraceful node failure | Ceph 3-replica + daily VolSync snapshot. Granular restore via Crafty UI from internal backup, full-PVC restore via VolSync ReplicationDestination. |
| Malicious plugin/mod uploaded by user error | Out of scope (human responsibility); CNP egress restriction limits possible exfiltration. |

---

## Open Questions for Plan Writing

1. Confirm cluster-level Flux entry point picks up `kubernetes/apps/games/` automatically, or whether an explicit reference must be added.
2. Confirm `${SECRET_DOMAIN}` substitution variable is reachable from the `games` namespace context (Flux SOPS substitution scope).
3. Confirm exact Crafty 4.x default `config.yml` keys for HTTP-only mode (verified against upstream during implementation, not at design time).
