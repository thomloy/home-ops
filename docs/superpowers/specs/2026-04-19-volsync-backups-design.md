# VolSync Backups — Design Spec

**Date:** 2026-04-19
**Status:** Approved

---

## Goal

Add VolSync backup coverage to all apps that have Ceph PVCs but no backup today. Target: 13 apps. Constraint: stay within Cloudflare S3 free tier (10 GB/month) — use NAS NFS as repository instead of S3.

---

## Scope

### Apps to back up (13 PVCs)

| App | Namespace | PVC name | runAsUser |
|-----|-----------|----------|-----------|
| paperless | selfhosted | paperless | 33 (www-data) |
| emby | media | emby | 1000 |
| audiobookshelf | media | audiobookshelf | 1000 |
| navidrome | media | navidrome | 1000 |
| atuin | default | atuin | 1000 |
| radarr | downloads | radarr | 1000 |
| sonarr | downloads | sonarr | 1000 |
| bazarr | downloads | bazarr | 1000 |
| lidarr | downloads | lidarr | 1000 |
| readarr | downloads | readarr | 1000 |
| prowlarr | downloads | prowlarr | 1000 |
| qbittorrent | downloads | qbittorrent | 1000 |
| sabnzbd | downloads | sabnzbd | 1000 |

### Excluded

- **immich**: library PVC is on NAS (NFS), not Ceph — nothing to snapshot. PostgreSQL covered by CNPG barman → Cloudflare S3.
- **nextcloud**: PostgreSQL covered by CNPG barman → Cloudflare S3.
- **actual-budget**: already has VolSync configured.

---

## Architecture

### Repository

NAS NFS share: `/mnt/HDD1X4/VolsyncKopia` (already used by actual-budget as reference pattern).

Each app gets its own Kopia repository subdirectory, keyed by secret (no collision risk).

### Pattern (per app)

```yaml
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: <app>
spec:
  sourcePVC: <app>
  trigger:
    schedule: "<cron>"
  kopia:
    accessModes: [ReadWriteOnce]
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: <uid>
      runAsGroup: <uid>
      fsGroup: <uid>
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: <app>-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

Each app also gets an ExternalSecret that creates `<app>-volsync-secret` (REPOSITORY_PASSWORD from 1Password).

### Staggered schedule (avoid I/O spikes)

| Time | Apps |
|------|------|
| `30 2 * * *` | paperless (documents — highest priority) |
| `30 3 * * *` | emby, audiobookshelf, navidrome, atuin |
| `30 4 * * *` | radarr, sonarr, bazarr, lidarr, readarr, prowlarr, qbittorrent, sabnzbd |

### Retention policy

- `hourly: 24` — last 24 hourly snapshots
- `daily: 7` — last 7 daily snapshots

No weekly/monthly to limit NAS disk usage.

---

## File layout

Each app gets a single new file:

```
kubernetes/apps/<namespace>/<app>/app/volsync.yaml
```

No changes to existing `helmrelease.yaml`, `kustomization.yaml` (volsync.yaml is picked up automatically by Flux since kustomization.yaml uses `resources: [.]`).

Exception: if `kustomization.yaml` lists explicit files, add `volsync.yaml` to the list.

---

## Secrets

One 1Password item per app: `<app>-volsync` containing field `REPOSITORY_PASSWORD`.

ExternalSecret template (reuse existing ClusterSecretStore `onepassword`):

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: <app>-volsync-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: <app>-volsync-secret
  data:
    - secretKey: REPOSITORY_PASSWORD
      remoteRef:
        key: <app>-volsync
        property: REPOSITORY_PASSWORD
```

---

## Sizing estimate

Arr stack configs: ~100 MB each × 8 = 800 MB
Media apps (emby/audiobookshelf/navidrome): ~500 MB each = 1.5 GB
paperless data: ~2 GB
atuin: ~100 MB

Total raw: ~4.5 GB. With zstd-fastest + dedup, estimate 2–3 GB active on NAS. Well within NAS capacity (4×4TB ZFS). No S3 usage — free tier not touched.
