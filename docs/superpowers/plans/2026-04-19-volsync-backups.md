# VolSync Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VolSync ReplicationSource backups to 13 apps that have Ceph PVCs but no backup today, using the NAS NFS Kopia repository.

**Architecture:** Each app gets a `volsync.yaml` file containing an ExternalSecret (creates `<app>-volsync-secret` from the shared `volsync-template` 1Password item) and a ReplicationSource (Kopia, copyMethod:Snapshot, NFS repository on NAS). All kustomization.yaml files list resources explicitly, so `volsync.yaml` must be added to each. Schedules are staggered to avoid I/O spikes.

**Tech Stack:** VolSync, Kopia, Ceph VolumeSnapshot, NFS (TrueNAS), External Secrets Operator, 1Password

---

## Reference Pattern

The existing `kubernetes/apps/selfhosted/actual-budget/app/volsync.yaml` is the canonical example:

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: actual-budget-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: actual-budget-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: actual-budget
spec:
  sourcePVC: actual-budget
  trigger:
    schedule: "30 2 * * *"
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
    repository: actual-budget-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

---

## Schedule Summary

| Time (cron) | Apps |
|-------------|------|
| `30 2 * * *` | paperless |
| `30 3 * * *` | emby, audiobookshelf, navidrome, atuin |
| `30 4 * * *` | radarr, sonarr, bazarr, lidarr, readarr, prowlarr, qbittorrent, sabnzbd |

---

## Task 1: paperless (selfhosted, uid 33)

**Files:**
- Create: `kubernetes/apps/selfhosted/paperless/app/volsync.yaml`
- Modify: `kubernetes/apps/selfhosted/paperless/app/kustomization.yaml`

- [ ] **Step 1: Create volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: paperless-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: paperless-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: paperless
spec:
  sourcePVC: paperless
  trigger:
    schedule: "30 2 * * *"
  kopia:
    accessModes:
      - ReadWriteOnce
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: 33
      runAsGroup: 33
      fsGroup: 33
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: paperless-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

Write to: `kubernetes/apps/selfhosted/paperless/app/volsync.yaml`

- [ ] **Step 2: Add volsync.yaml to kustomization.yaml**

Current `kubernetes/apps/selfhosted/paperless/app/kustomization.yaml`:
```yaml
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

Add `- ./volsync.yaml` at the end of the resources list.

- [ ] **Step 3: Validate YAML**

```bash
kubectl apply --dry-run=client -f kubernetes/apps/selfhosted/paperless/app/volsync.yaml
```

Expected: `externalsecret.external-secrets.io/paperless-volsync created (dry run)` and `replicationsource.volsync.backube/paperless created (dry run)`

- [ ] **Step 4: Commit**

```bash
git add kubernetes/apps/selfhosted/paperless/app/volsync.yaml kubernetes/apps/selfhosted/paperless/app/kustomization.yaml
git commit -m "feat(paperless): add VolSync backup"
```

---

## Task 2: media apps — emby, audiobookshelf, navidrome (media namespace, uid 1000)

**Files:**
- Create: `kubernetes/apps/media/emby/app/volsync.yaml`
- Modify: `kubernetes/apps/media/emby/app/kustomization.yaml`
- Create: `kubernetes/apps/media/audiobookshelf/app/volsync.yaml`
- Modify: `kubernetes/apps/media/audiobookshelf/app/kustomization.yaml`
- Create: `kubernetes/apps/media/navidrome/app/volsync.yaml`
- Modify: `kubernetes/apps/media/navidrome/app/kustomization.yaml`

- [ ] **Step 1: Create kubernetes/apps/media/emby/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: emby-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: emby-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: emby
spec:
  sourcePVC: emby
  trigger:
    schedule: "30 3 * * *"
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
    repository: emby-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 2: Add volsync.yaml to kubernetes/apps/media/emby/app/kustomization.yaml**

Current resources:
```yaml
resources:
  - ./ocirepository.yaml
  - ./pvc.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

Add `- ./volsync.yaml` at the end.

- [ ] **Step 3: Create kubernetes/apps/media/audiobookshelf/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: audiobookshelf-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: audiobookshelf-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: audiobookshelf
spec:
  sourcePVC: audiobookshelf
  trigger:
    schedule: "30 3 * * *"
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
    repository: audiobookshelf-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 4: Add volsync.yaml to kubernetes/apps/media/audiobookshelf/app/kustomization.yaml**

Current resources:
```yaml
resources:
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

Add `- ./volsync.yaml` at the end.

- [ ] **Step 5: Create kubernetes/apps/media/navidrome/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: navidrome-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: navidrome-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: navidrome
spec:
  sourcePVC: navidrome
  trigger:
    schedule: "30 3 * * *"
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
    repository: navidrome-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 6: Add volsync.yaml to kubernetes/apps/media/navidrome/app/kustomization.yaml**

Current resources:
```yaml
resources:
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

Add `- ./volsync.yaml` at the end.

- [ ] **Step 7: Validate YAML**

```bash
kubectl apply --dry-run=client -f kubernetes/apps/media/emby/app/volsync.yaml
kubectl apply --dry-run=client -f kubernetes/apps/media/audiobookshelf/app/volsync.yaml
kubectl apply --dry-run=client -f kubernetes/apps/media/navidrome/app/volsync.yaml
```

Expected: each prints `externalsecret ... created (dry run)` and `replicationsource ... created (dry run)`

- [ ] **Step 8: Commit**

```bash
git add kubernetes/apps/media/emby/app/volsync.yaml kubernetes/apps/media/emby/app/kustomization.yaml
git add kubernetes/apps/media/audiobookshelf/app/volsync.yaml kubernetes/apps/media/audiobookshelf/app/kustomization.yaml
git add kubernetes/apps/media/navidrome/app/volsync.yaml kubernetes/apps/media/navidrome/app/kustomization.yaml
git commit -m "feat(media): add VolSync backup for emby, audiobookshelf, navidrome"
```

---

## Task 3: atuin (default namespace, uid 1000)

**Files:**
- Create: `kubernetes/apps/default/atuin/app/volsync.yaml`
- Modify: `kubernetes/apps/default/atuin/app/kustomization.yaml`

- [ ] **Step 1: Create volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: atuin-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: atuin-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: atuin
spec:
  sourcePVC: atuin
  trigger:
    schedule: "30 3 * * *"
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
    repository: atuin-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

Write to: `kubernetes/apps/default/atuin/app/volsync.yaml`

- [ ] **Step 2: Add volsync.yaml to kustomization.yaml**

Current `kubernetes/apps/default/atuin/app/kustomization.yaml`:
```yaml
resources:
  - ./helmrelease.yaml
  - ./ocirepository.yaml
  - ./ciliumnetworkpolicy.yaml
```

Add `- ./volsync.yaml` at the end.

- [ ] **Step 3: Validate YAML**

```bash
kubectl apply --dry-run=client -f kubernetes/apps/default/atuin/app/volsync.yaml
```

Expected: `externalsecret.../atuin-volsync created (dry run)` and `replicationsource.../atuin created (dry run)`

- [ ] **Step 4: Commit**

```bash
git add kubernetes/apps/default/atuin/app/volsync.yaml kubernetes/apps/default/atuin/app/kustomization.yaml
git commit -m "feat(atuin): add VolSync backup"
```

---

## Task 4: arr stack — radarr, sonarr, bazarr, lidarr, readarr, prowlarr (downloads, uid 1000)

**Files:**
- Create: `kubernetes/apps/downloads/radarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/radarr/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/sonarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/sonarr/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/bazarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/bazarr/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/lidarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/lidarr/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/readarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/readarr/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/prowlarr/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/prowlarr/app/kustomization.yaml`

All are identical except the app name. Schedule: `30 4 * * *`.

- [ ] **Step 1: Create kubernetes/apps/downloads/radarr/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: radarr-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: radarr-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: radarr
spec:
  sourcePVC: radarr
  trigger:
    schedule: "30 4 * * *"
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
    repository: radarr-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 2: Add volsync.yaml to kubernetes/apps/downloads/radarr/app/kustomization.yaml**

Current resources include `ocirepository, externalsecret, helmrelease, ciliumnetworkpolicy`. Add `- ./volsync.yaml` at the end.

- [ ] **Step 3: Create kubernetes/apps/downloads/sonarr/app/volsync.yaml**

Same as radarr but replace every `radarr` → `sonarr`.

- [ ] **Step 4: Add volsync.yaml to kubernetes/apps/downloads/sonarr/app/kustomization.yaml**

Add `- ./volsync.yaml` at the end of the resources list.

- [ ] **Step 5: Create kubernetes/apps/downloads/bazarr/app/volsync.yaml**

Same as radarr but replace every `radarr` → `bazarr`.

- [ ] **Step 6: Add volsync.yaml to kubernetes/apps/downloads/bazarr/app/kustomization.yaml**

Current resources: `ocirepository, helmrelease, ciliumnetworkpolicy`. Add `- ./volsync.yaml` at the end.

- [ ] **Step 7: Create kubernetes/apps/downloads/lidarr/app/volsync.yaml**

Same as radarr but replace every `radarr` → `lidarr`.

- [ ] **Step 8: Add volsync.yaml to kubernetes/apps/downloads/lidarr/app/kustomization.yaml**

Add `- ./volsync.yaml` at the end of the resources list.

- [ ] **Step 9: Create kubernetes/apps/downloads/readarr/app/volsync.yaml**

Same as radarr but replace every `radarr` → `readarr`.

- [ ] **Step 10: Add volsync.yaml to kubernetes/apps/downloads/readarr/app/kustomization.yaml**

Add `- ./volsync.yaml` at the end of the resources list.

- [ ] **Step 11: Create kubernetes/apps/downloads/prowlarr/app/volsync.yaml**

Same as radarr but replace every `radarr` → `prowlarr`.

- [ ] **Step 12: Add volsync.yaml to kubernetes/apps/downloads/prowlarr/app/kustomization.yaml**

Current resources: `ciliumnetworkpolicy, externalsecret, helmrelease, ocirepository`. Add `- ./volsync.yaml` at the end.

- [ ] **Step 13: Validate YAML**

```bash
for app in radarr sonarr bazarr lidarr readarr prowlarr; do
  kubectl apply --dry-run=client -f kubernetes/apps/downloads/$app/app/volsync.yaml
done
```

Expected: each prints two `created (dry run)` lines.

- [ ] **Step 14: Commit**

```bash
git add kubernetes/apps/downloads/radarr/app/volsync.yaml kubernetes/apps/downloads/radarr/app/kustomization.yaml
git add kubernetes/apps/downloads/sonarr/app/volsync.yaml kubernetes/apps/downloads/sonarr/app/kustomization.yaml
git add kubernetes/apps/downloads/bazarr/app/volsync.yaml kubernetes/apps/downloads/bazarr/app/kustomization.yaml
git add kubernetes/apps/downloads/lidarr/app/volsync.yaml kubernetes/apps/downloads/lidarr/app/kustomization.yaml
git add kubernetes/apps/downloads/readarr/app/volsync.yaml kubernetes/apps/downloads/readarr/app/kustomization.yaml
git add kubernetes/apps/downloads/prowlarr/app/volsync.yaml kubernetes/apps/downloads/prowlarr/app/kustomization.yaml
git commit -m "feat(downloads): add VolSync backup for arr stack"
```

---

## Task 5: qbittorrent and sabnzbd (downloads, uid 1000)

**Files:**
- Create: `kubernetes/apps/downloads/qbittorrent/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/qbittorrent/app/kustomization.yaml`
- Create: `kubernetes/apps/downloads/sabnzbd/app/volsync.yaml`
- Modify: `kubernetes/apps/downloads/sabnzbd/app/kustomization.yaml`

- [ ] **Step 1: Create kubernetes/apps/downloads/qbittorrent/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: qbittorrent-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: qbittorrent-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: qbittorrent
spec:
  sourcePVC: qbittorrent
  trigger:
    schedule: "30 4 * * *"
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
    repository: qbittorrent-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 2: Add volsync.yaml to kubernetes/apps/downloads/qbittorrent/app/kustomization.yaml**

Current resources: `externalsecret, ocirepository, helmrelease, ciliumnetworkpolicy`. Add `- ./volsync.yaml` at the end.

- [ ] **Step 3: Create kubernetes/apps/downloads/sabnzbd/app/volsync.yaml**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: sabnzbd-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: sabnzbd-volsync-secret
    template:
      data:
        KOPIA_PASSWORD: "{{ .KOPIA_PASSWORD }}"
        KOPIA_REPOSITORY: filesystem:///mnt/repository
  dataFrom:
    - extract:
        key: volsync-template
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/volsync.backube/replicationsource_v1alpha1.json
apiVersion: volsync.backube/v1alpha1
kind: ReplicationSource
metadata:
  name: sabnzbd
spec:
  sourcePVC: sabnzbd
  trigger:
    schedule: "30 4 * * *"
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
    repository: sabnzbd-volsync-secret
    retain:
      hourly: 24
      daily: 7
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 4: Add volsync.yaml to kubernetes/apps/downloads/sabnzbd/app/kustomization.yaml**

Current resources: `externalsecret, helmrelease, ocirepository, ciliumnetworkpolicy`. Add `- ./volsync.yaml` at the end.

- [ ] **Step 5: Validate YAML**

```bash
kubectl apply --dry-run=client -f kubernetes/apps/downloads/qbittorrent/app/volsync.yaml
kubectl apply --dry-run=client -f kubernetes/apps/downloads/sabnzbd/app/volsync.yaml
```

Expected: each prints two `created (dry run)` lines.

- [ ] **Step 6: Commit**

```bash
git add kubernetes/apps/downloads/qbittorrent/app/volsync.yaml kubernetes/apps/downloads/qbittorrent/app/kustomization.yaml
git add kubernetes/apps/downloads/sabnzbd/app/volsync.yaml kubernetes/apps/downloads/sabnzbd/app/kustomization.yaml
git commit -m "feat(downloads): add VolSync backup for qbittorrent and sabnzbd"
```

---

## Post-implementation verification

After Flux reconciles (wait ~5 minutes after push):

```bash
# Check all ReplicationSources are created
kubectl get replicationsource -A

# Check ExternalSecrets resolved
kubectl get externalsecret -A | grep volsync

# After the scheduled time, check a completed backup
kubectl get replicationsource -n selfhosted paperless -o jsonpath='{.status}'
```

Expected for a successful run: `.status.lastSyncTime` set, `.status.latestMoverStatus.result: Successful`.
