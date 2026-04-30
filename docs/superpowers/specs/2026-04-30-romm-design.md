# RomM (ROM library manager) — Design Spec

**Date:** 2026-04-30
**Namespace:** games (existing)
**Status:** Approved

---

## Context

Self-host **RomM** (https://github.com/rommapp/romm), a ROM library manager — Plex-like UI for retro game collections. Sits next to Crafty in the `games` namespace.

RomM's job: scan a directory tree of ROMs sorted by platform, fetch metadata (covers, synopsis, release date, genre) from IGDB, augment cover art via SteamGridDB, expose a web UI to browse, manage saves/states/screenshots, and (optionally) launch via emulator integrations.

Architecture-wise it's bigger than Crafty:
- One web app (FastAPI + Vue) with a Valkey cache controller in the same HelmRelease
- A dedicated CNPG PostgreSQL cluster
- A large NFS-backed `ReadWriteMany` volume for the ROM library
- 1Password-backed external secrets for IGDB / SteamGridDB / admin bootstrap
- Internal gateway exposure only (no Tailscale, no Cloudflare — ROMs are legal grey area)

---

## Goals

- Browse + manage the ROM collection at `https://romm.${SECRET_DOMAIN}` over the internal gateway (LAN + Tailscale).
- ROMs live on the TrueNAS NFS share, sized for 50–300 GB (typical retro-classic library through PSP era).
- Database on CNPG (1 instance, ceph-block 5 Gi), weekly volumeSnapshot backup.
- Application state (cover art cache, saves, screenshots, settings) on Ceph block 5 Gi PVC, daily VolSync to NFS NAS.
- Metadata enrichment via IGDB (synopsis/release/genre) and SteamGridDB (cover art).

## Non-goals

- ScreenScraper / TheGamesDB / MobyGames metadata sources — added later only if IGDB+SGDB coverage proves insufficient.
- OIDC / SSO — RomM's built-in auth is enough for 3-5 family users.
- Public exposure via Cloudflare Tunnel — never; ROMs are legal grey area.
- BarmanObjectStore (S3 PITR) backup of the CNPG cluster — `volumeSnapshot` is sufficient.
- Automatic backup of the ROM library via VolSync — TrueNAS ZFS snapshots handle this side, configured via TrueNAS UI (out of scope of this repo).
- HA Postgres (3-instance CNPG cluster) — homelab load is light, single instance with weekly snapshot is enough.

---

## Architecture

```
LAN/Tailscale ──► 192.168.42.110:443 (envoy-internal, TLS *.kryzql.space)
                        │
                        ▼
                 HTTPRoute romm.kryzql.space
                        │
                        ▼
              ┌──────── games ns ────────────┐
              │  Service: romm-app (HTTP 8080)│
              │           │                   │
              │           ▼                   │
              │   ┌──── Pod: romm ────┐      │
              │   │ container: app    │      │
              │   │ (rommapp/romm)    │      │
              │   └────┬───────┬──────┘      │
              │        │       │              │
              │        │       ▼              │
              │        │  Pod: romm-valkey   │
              │        │  (cache 6379)        │
              │        │                      │
              │        ▼                      │
              │   Pod: romm-postgres-1       │
              │   (CNPG, postgres 16)        │
              │        │                      │
              │        ▼                      │
              │   PVC romm-postgres-1        │
              │   Ceph block 5 Gi            │
              │                               │
              │   PVC romm-data              │
              │   Ceph block 5 Gi RWO        │
              │   (cover cache, saves,       │
              │    states, screenshots,      │
              │    config)                   │
              │                               │
              │   PVC romm-library           │
              │   ════════════════════════   │
              │   NFS RWX 500 Gi             │
              │   /mnt/HDD1X4/apps/romm/     │
              │     library                  │
              └───────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                                │
        ▼                                ▼
 VolSync ReplicationSource      CNPG ScheduledBackup
 → Kopia mover                  → volumeSnapshot
 → NFS NAS                      → Ceph CSI snapshot
 (daily, romm-data)             (weekly Sunday)
```

---

## Files

```
kubernetes/apps/games/                            # existing (Crafty already there)
├── kustomization.yaml                            # MODIFY: add ./romm/ks.yaml
└── romm/                                         # NEW
    ├── ks.yaml                                   # Flux Kustomization
    └── app/
        ├── kustomization.yaml                    # Resources index
        ├── ocirepository.yaml                    # bjw-s app-template 4.6.2
        ├── helmrelease.yaml                      # romm + valkey controllers
        ├── cluster.yaml                          # CNPG Cluster romm-postgres
        ├── scheduledbackup.yaml                  # CNPG ScheduledBackup volumeSnapshot weekly
        ├── pv.yaml                               # PV+PVC NFS RWX library
        ├── externalsecret.yaml                   # IGDB + SGDB + admin pwd from 1Password
        ├── volsync.yaml                          # ExternalSecret + ReplicationSource for romm-data
        └── ciliumnetworkpolicy.yaml              # Two CNPs: romm + romm-valkey
```

The `volsync` Kustomize component is **not** included; pattern follows Crafty / `actual-budget` (full inline definition for both ExternalSecret and ReplicationSource so retention can be customised).

---

## Flux Kustomization (`ks.yaml`)

- `targetNamespace: games`
- `dependsOn`:
  - `rook-ceph-cluster` (rook-ceph) — for the Ceph PVCs
  - `cloudnative-pg` (database) — for the CNPG operator (Cluster + ScheduledBackup)
  - `volsync` (volsync-system) — for the inline `ReplicationSource`
  - `onepassword` (external-secrets) — for the ExternalSecrets
- `interval: 1h`, `timeout: 5m`, `wait: false`, `prune: true`.

---

## HelmRelease (bjw-s app-template)

**Chart**: `oci://ghcr.io/bjw-s-labs/helm/app-template` tag `4.6.2`.

### Controller `romm`

```
# renovate: datasource=docker depName=docker.io/rommapp/romm
docker.io/rommapp/romm:3.X.Y
```

The exact tag is fixed at implementation time against the latest stable RomM 3.x. Manual Renovate approval initially (DB migrations between majors can be destructive); switch to auto-merge minor+patch after a few months of stability.

- `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`
- `allowPrivilegeEscalation: false`, `cap drop: [ALL]`, `seccompProfile: RuntimeDefault`
- `readOnlyRootFilesystem: false` (RomM writes temp files to `/tmp` and `/romm/.cache`)
- Resources: requests `cpu 200m / memory 1Gi`, limit `memory 4Gi` (no CPU limit). Bump to 6–8 Gi if scan freezes the pod on a large library.
- Probes: `startupProbe`/`livenessProbe`/`readinessProbe` HTTP GET `/api/heartbeat` on port 8080. Startup `failureThreshold: 30, periodSeconds: 10`.

**Env**:

```yaml
env:
  TZ: Europe/Paris
  REDIS_HOST: romm-valkey
  REDIS_PORT: "6379"
  ROMM_DB_DRIVER: postgresql
  DB_HOST: romm-postgres-rw
  DB_PORT: "5432"
  DB_NAME: romm
  DB_USER:
    valueFrom: { secretKeyRef: { name: romm-postgres-app, key: username } }
  DB_PASSWD:
    valueFrom: { secretKeyRef: { name: romm-postgres-app, key: password } }
  ROMM_AUTH_USERNAME:
    valueFrom: { secretKeyRef: { name: romm-secret, key: ROMM_AUTH_USERNAME } }
  ROMM_AUTH_PASSWORD:
    valueFrom: { secretKeyRef: { name: romm-secret, key: ROMM_AUTH_PASSWORD } }
  ROMM_AUTH_SECRET_KEY:
    valueFrom: { secretKeyRef: { name: romm-secret, key: ROMM_AUTH_SECRET_KEY } }
  IGDB_CLIENT_ID:
    valueFrom: { secretKeyRef: { name: romm-secret, key: IGDB_CLIENT_ID } }
  IGDB_CLIENT_SECRET:
    valueFrom: { secretKeyRef: { name: romm-secret, key: IGDB_CLIENT_SECRET } }
  STEAMGRIDDB_API_KEY:
    valueFrom: { secretKeyRef: { name: romm-secret, key: STEAMGRIDDB_API_KEY } }
```

### Controller `valkey`

```
# renovate: datasource=docker depName=ghcr.io/valkey-io/valkey
ghcr.io/valkey-io/valkey:9.0.3
```

- Resources: requests `cpu 50m / memory 64Mi`, limit `memory 256Mi`
- No persistence (cache only — restart resets, RomM rebuilds the queue at boot)
- Probe TCP 6379

### Services

```yaml
service:
  app:
    controller: romm
    primary: true
    ports:
      http:
        port: 8080
  valkey:
    controller: valkey
    ports:
      valkey:
        port: 6379
```

bjw-s app-template renders Service names as `<release>-<key>` when there are 2+ services (paperless precedent verified). Resulting names: `romm-app` (the primary, used by the HTTPRoute) and `romm-valkey` (referenced by `REDIS_HOST`). The CNPG cluster's services are `romm-postgres-rw` and `romm-postgres-r` regardless of this.

### HTTPRoute

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
      - romm.${SECRET_DOMAIN}
    parentRefs:
      - { name: envoy-internal, namespace: network }
    rules:
      - backendRefs:
          - { identifier: app, port: http }
```

### Persistence

```yaml
persistence:
  data:
    type: persistentVolumeClaim
    accessMode: ReadWriteOnce
    size: 5Gi
    storageClass: ceph-block
    advancedMounts:
      romm:
        app:
          - { path: /romm/resources, subPath: resources }
          - { path: /romm/assets, subPath: assets }
          - { path: /romm/config, subPath: config }
          - { path: /romm/.cache, subPath: cache }
  library:
    existingClaim: romm-library
    advancedMounts:
      romm:
        app:
          - { path: /romm/library }
```

---

## CNPG Postgres (`cluster.yaml` + `scheduledbackup.yaml`)

### Cluster

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: romm-postgres
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:16
  storage:
    storageClass: ceph-block
    size: 5Gi
  bootstrap:
    initdb:
      database: romm
      owner: romm
  backup:
    volumeSnapshot:
      className: csi-ceph-blockpool
  monitoring:
    enablePodMonitor: true
```

### ScheduledBackup

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: romm-postgres
spec:
  schedule: "0 0 3 * * 0"   # Sunday 03:00 (CNPG 6-field cron: sec min hour dom mon dow)
  backupOwnerReference: self
  cluster:
    name: romm-postgres
  method: volumeSnapshot
```

- 1 instance (homelab load, no HA need)
- `volumeSnapshot` uses Ceph CSI snapshot class `csi-ceph-blockpool` — same as VolSync uses elsewhere
- Auto-generated artifacts: Service `romm-postgres-rw` (consumed via `DATABASE_URL`), Secret `romm-postgres-app` with field `uri` containing the full PostgreSQL DSN
- No `barmanObjectStore` (no S3 backup) — accepting up to 6 days of data loss between snapshots; user state in RomM (saves/playtime/tags) is non-critical

### Restore strategy

If the cluster dies, recreate via:
```yaml
spec:
  bootstrap:
    recovery:
      backup:
        name: <Backup CR name from a previous ScheduledBackup>
```

### Snapshot retention

`ScheduledBackup` with `volumeSnapshot` has no native retention. With a 5 Gi DB and minimal write load, snapshot accumulation is slow (a snapshot is essentially a CoW reference + WAL delta). Reassess after 6 months: if it grows significantly, add a `CronJob` deleting `VolumeSnapshot` resources older than N weeks.

---

## Storage

### `romm-data` PVC (Ceph block, 5 Gi, RWO)

Created inline by the bjw-s app-template via `persistence.data` (matching `actual-budget` and Crafty pattern). Holds:

- `/romm/resources` — IGDB / SGDB cover art cache (~1–2 GB)
- `/romm/assets` — saves, savestates, screenshots (<1 GB)
- `/romm/config` — RomM settings file
- `/romm/.cache` — Python aiohttp cache (small, transient)

Online expansion via `kubectl edit pvc romm-data` if the user-generated content grows.

### `romm-library` PV+PVC (NFS, 500 Gi, RWX)

Pattern identical to `immich-library`. The PV references a path on TrueNAS via NFS:

```yaml
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: romm-library-pv
spec:
  capacity:
    storage: 500Gi
  accessModes: [ReadWriteMany]
  persistentVolumeReclaimPolicy: Retain
  nfs:
    server: ${NAS_IP}
    path: /mnt/HDD1X4/apps/romm/library
  claimRef:
    name: romm-library
    namespace: games
  storageClassName: ""
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: romm-library
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 500Gi
  volumeName: romm-library-pv
  storageClassName: ""
```

Mounted at `/romm/library` in the romm container.

### Manual NAS-side prep

The user must create the directory tree on TrueNAS before the first reconcile:
```
/mnt/HDD1X4/apps/romm/library/
├── roms/
│   ├── nes/
│   ├── snes/
│   ├── n64/
│   ├── psx/
│   └── ...     # one folder per platform; RomM auto-detects them
└── bios/       # optional, for emulators that need BIOS files
```
Permissions: `chown -R 1000:1000` so the pod (which runs as UID 1000) can write saves/screenshots back via `/romm/library/.romm/<...>`. (RomM may write metadata files directly into the library dir.)

### Backups

| Volume | Mechanism | Schedule | Retention |
|---|---|---|---|
| `romm-data` | VolSync ReplicationSource → Kopia → NFS NAS | `30 4 * * *` (04:30 daily) | 24h / 30d / 12w / 6m |
| `romm-postgres-1` | CNPG ScheduledBackup → volumeSnapshot (Ceph CSI) | `0 0 3 * * 0` (Sunday 03:00) | infinite (manual cleanup later) |
| `romm-library` | TrueNAS ZFS snapshots | configured TrueNAS-side | TrueNAS-side |

---

## Secrets

### 1Password item to create manually

Vault `default`, item `romm`, fields:

| Field | Value |
|---|---|
| `ROMM_AUTH_USERNAME` | `admin` (or any) |
| `ROMM_AUTH_PASSWORD` | strong password (1P generator) |
| `ROMM_AUTH_SECRET_KEY` | 64-character hex random string (`openssl rand -hex 32`) |
| `IGDB_CLIENT_ID` | from Twitch Dev Portal app `romm-homelab` |
| `IGDB_CLIENT_SECRET` | from Twitch Dev Portal — generate after creating the app |
| `STEAMGRIDDB_API_KEY` | from https://www.steamgriddb.com/profile/preferences/api |

### `externalsecret.yaml`

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: romm
spec:
  refreshInterval: 12h
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: romm-secret
    creationPolicy: Owner
    template:
      data:
        ROMM_AUTH_USERNAME: "{{ .ROMM_AUTH_USERNAME }}"
        ROMM_AUTH_PASSWORD: "{{ .ROMM_AUTH_PASSWORD }}"
        ROMM_AUTH_SECRET_KEY: "{{ .ROMM_AUTH_SECRET_KEY }}"
        IGDB_CLIENT_ID: "{{ .IGDB_CLIENT_ID }}"
        IGDB_CLIENT_SECRET: "{{ .IGDB_CLIENT_SECRET }}"
        STEAMGRIDDB_API_KEY: "{{ .STEAMGRIDDB_API_KEY }}"
  dataFrom:
    - extract:
        key: romm
```

### DB credentials — auto-generated

CNPG creates the secret `romm-postgres-app` with fields `username`, `password`, `host`, `port`, `dbname`, `uri`, `jdbc-uri`. We consume `username` and `password` from this secret, plus hard-coded `DB_HOST: romm-postgres-rw`, `DB_PORT: "5432"`, `DB_NAME: romm`, and `ROMM_DB_DRIVER: postgresql` env vars on the romm container — no manual ExternalSecret for DB creds. (RomM's upstream config reads discrete `DB_*` env vars; it does not parse a `DATABASE_URL`.)

### Bootstrap behaviour

`ROMM_AUTH_USERNAME` and `ROMM_AUTH_PASSWORD` are read at first start to create the admin user in DB. After the first start they are inert. Rotating the admin password later **must** be done via the RomM UI (Settings → Account), not by editing 1Password.

`ROMM_AUTH_SECRET_KEY` is load-bearing at every restart (signs JWT session tokens). Do not change unless rotating sessions deliberately.

`IGDB_*` and `STEAMGRIDDB_API_KEY` are load-bearing at runtime; safe to rotate.

### No CNPG backup secret

Since approach uses `volumeSnapshot` (not `barmanObjectStore`), no S3 credentials are needed.

---

## Networking (Cilium NetworkPolicy)

Two CiliumNetworkPolicies in `ciliumnetworkpolicy.yaml` (multi-document YAML, immich precedent):

### `romm` policy (for the romm controller pods)

**Ingress**:
- From namespace `network` with `gateway.networking.k8s.io/gateway-name: envoy-internal` → port 8080/TCP
- DNS from kube-dns

**Egress**:
- `toEntities: [cluster, world]` without `toPorts` (immich pattern, the documented DSR/`toPorts` workaround in memory `feedback_cilium_toentities_world.md`).
  - `cluster` covers in-pod traffic to `romm-valkey`, `romm-postgres-rw`
  - `world` covers IGDB, SteamGridDB, cover-art CDN downloads

### `romm-valkey` policy (for the valkey controller pod)

**Ingress** (only):
- From `romm` controller pods (in same namespace, labels `app.kubernetes.io/name: romm` AND `app.kubernetes.io/instance: romm`) → port 6379/TCP

The Postgres cluster is protected by CNPG's own NetworkPolicies (the operator manages those automatically) — we don't add any here.

---

## Renovate

```yaml
# helmrelease.yaml — romm container
# renovate: datasource=docker depName=docker.io/rommapp/romm
tag: 3.X.Y

# helmrelease.yaml — valkey container
# renovate: datasource=docker depName=ghcr.io/valkey-io/valkey
tag: 9.0.3
```

Auto-merge **disabled** initially for both (RomM major bumps may have destructive migrations; Valkey is stable but in a critical path).

---

## Acceptance Criteria

1. `kubectl -n games get pods` shows three Running pods: `romm-<hash>` 1/1, `romm-valkey-<hash>` 1/1, `romm-postgres-1` 1/1. (`romm-postgres-1` is the CNPG instance pod.)
2. `kubectl -n games get pvc` shows `romm-data` Bound 5Gi, `romm-library` Bound 500Gi, `romm-postgres-1` Bound 5Gi.
3. `kubectl -n games get cluster.postgresql.cnpg.io romm-postgres -o jsonpath='{.status.phase}'` returns `Cluster in healthy state`.
4. `dig +short romm.${SECRET_DOMAIN} @192.168.42.99` resolves to `192.168.42.110`.
5. `https://romm.${SECRET_DOMAIN}` returns the RomM login page with a valid wildcard TLS cert.
6. Login as `admin` with `ROMM_AUTH_PASSWORD` succeeds; admin lands on the dashboard.
7. RomM Settings → Configuration → IGDB and SteamGridDB show "connected" / "OK" status.
8. Drop a few ROMs into `/mnt/HDD1X4/apps/romm/library/roms/<platform>/` on the NAS and trigger a scan from the UI: cover art is fetched and displayed within a few minutes.
9. After Sunday 03:00 UTC: `kubectl -n games get volumesnapshot` lists at least one CNPG snapshot.
10. After Monday 04:30 UTC: `kubectl -n games get replicationsource romm` shows recent `LAST_SYNC` and `STATUS: Idle`; corresponding Kopia snapshot present on the NAS NFS share.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| RomM scan CPU/RAM-heavy on a large library | 4Gi limit covers 50–300 GB; bump to 6–8 Gi if scan OOMs |
| NFS latency slows scan | Acceptable — scan is one-shot, doesn't block the UI; subsequent reads use Ceph cache |
| Lost ROM file on NAS | Out of scope for this repo — rely on TrueNAS ZFS snapshots configured via the TrueNAS UI |
| Major RomM upgrade breaks DB schema | Manual Renovate approval, weekly volumeSnapshot for instant rollback, manual snapshot via `kubectl create backup ...` before known-risky bumps |
| IGDB rate limit (4 req/s) | RomM throttles automatically; first scan is slower but succeeds |
| Snapshot retention growth | Reassess in 6 months; if Ceph snapshot consumption is significant, add a CronJob deleting old `VolumeSnapshot` resources |
| Mojang-style auth bootstrap drift (admin password edited in 1P after first boot) | Documented: rotate admin via RomM UI, not 1P; 1P stays as human reference vault |

---

## Open Questions for Plan Writing

1. Confirm the exact latest stable RomM tag (3.x.y) at implementation time (against the RomM GitHub releases / Docker Hub).
2. Confirm the exact `valkey` image tag still matches what the rest of the repo uses (`9.0.3` per nextcloud/paperless at design time).
3. Verify that bjw-s app-template's service identifier semantics produce `romm-app` (not `romm`) when there are two services and one is `primary: true` — same trap that hit Crafty (`primary: true` made Crafty's primary service named just `crafty`, not `crafty-app`). The behaviour may differ here because we have two containers in two distinct controllers, both wired to services. Verified against `getByIdentifier` template logic during plan writing.
4. Confirm `${SECRET_DOMAIN}` and `${NAS_IP}` substitution variables are reachable from the `games` namespace context (they were for Crafty — should still hold).
5. Confirm the NAS share `/mnt/HDD1X4/apps/romm/library` is created with `1000:1000` ownership before the first reconcile.
