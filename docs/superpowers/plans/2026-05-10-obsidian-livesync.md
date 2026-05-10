# Obsidian LiveSync (CouchDB) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déployer CouchDB 3.4.3 single-node sur le cluster Talos pour synchroniser les vaults Obsidian via le plugin Self-hosted LiveSync, accessible interne/Tailscale uniquement à `obsidian.${SECRET_DOMAIN}`.

**Architecture:** Helm via bjw-s `app-template` (OCIRepository + HelmRelease), PVC `ceph-block` 20Gi, configMap pour `local.ini` (CORS + tuning LiveSync), ExternalSecret pour admin creds (1Password), HTTPRoute sur `envoy-internal`, CiliumNetworkPolicy ingress depuis le Gateway, VolSync Kopia daily vers NFS NAS.

**Tech Stack:** Kubernetes 1.35.4 + Talos 1.12.7, Flux 2.8.3, Cilium 0.19, Envoy Gateway, Rook-Ceph, VolSync+Kopia, External Secrets + 1Password, CouchDB 3.4.3.

**Spec source:** `docs/superpowers/specs/2026-05-10-obsidian-livesync-design.md`

---

## File structure

```
kubernetes/apps/selfhosted/obsidian-livesync/
├── ks.yaml                          # NEW
└── app/
    ├── kustomization.yaml           # NEW
    ├── ocirepository.yaml           # NEW
    ├── configmap.yaml               # NEW (CouchDB local.ini)
    ├── externalsecret.yaml          # NEW
    ├── helmrelease.yaml             # NEW
    ├── ciliumnetworkpolicy.yaml     # NEW
    └── volsync.yaml                 # NEW
kubernetes/apps/selfhosted/kustomization.yaml  # MODIFY (add ./obsidian-livesync/ks.yaml)
```

---

## Task 0: Pré-requis 1Password (manual, user)

**Files:** none

- [ ] **Step 1: Créer item 1Password** dans le vault `kubernetes` (celui pointé par le ClusterSecretStore `onepassword`)

```
Item name: obsidian-livesync
Fields:
  username = admin
  password = <chaîne aléatoire ≥ 24 chars, par ex. via `openssl rand -base64 32`>
```

- [ ] **Step 2: Vérifier disponibilité**

```bash
op item get obsidian-livesync --vault kubernetes --fields username 2>&1 | head -3
```
Expected: la chaîne `admin` (ou la valeur que tu as choisie). Si `not found` → pas créé, ne pas continuer.

- [ ] **Step 3: Note password localement** (secret manager, pas dans le repo) pour l'injecter dans le plugin Obsidian post-deploy.

---

## Task 1: Créer le répertoire app

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/` (dir)

- [ ] **Step 1: mkdir**

```bash
mkdir -p kubernetes/apps/selfhosted/obsidian-livesync/app
```

- [ ] **Step 2: Vérifier**

```bash
ls -la kubernetes/apps/selfhosted/obsidian-livesync/app
```
Expected: dossier existe, vide.

---

## Task 2: OCIRepository (chart bjw-s app-template)

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/ocirepository.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/source.toolkit.fluxcd.io/ocirepository_v1.json
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: obsidian-livesync
spec:
  interval: 15m
  layerSelector:
    mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
    operation: copy
  ref:
    tag: 4.6.2
  url: oci://ghcr.io/bjw-s-labs/helm/app-template
```

- [ ] **Step 2: Validation YAML**

```bash
yq eval . kubernetes/apps/selfhosted/obsidian-livesync/app/ocirepository.yaml >/dev/null && echo OK
```
Expected: `OK`.

---

## Task 3: ConfigMap CouchDB `local.ini`

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/configmap.yaml`

Le fichier `local.ini` est monté dans `/opt/couchdb/etc/local.d/` et active CORS + le tuning recommandé par le plugin LiveSync.

- [ ] **Step 1: Écrire le fichier**

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: obsidian-livesync-config
data:
  local.ini: |
    [couchdb]
    single_node = true
    max_document_size = 50000000

    [chttpd]
    require_valid_user = true
    max_http_request_size = 4294967296
    enable_cors = true

    [chttpd_auth]
    require_valid_user = true
    authentication_redirect = /_utils/session.html

    [httpd]
    WWW-Authenticate = Basic realm="couchdb"
    enable_cors = true

    [cors]
    credentials = true
    origins = app://obsidian.md,capacitor://localhost,http://localhost
    headers = accept, authorization, content-type, origin, referer
    methods = GET, PUT, POST, HEAD, DELETE
    max_age = 3600
```

- [ ] **Step 2: Validation**

```bash
yq eval '.data."local.ini"' kubernetes/apps/selfhosted/obsidian-livesync/app/configmap.yaml | grep -E "enable_cors|origins" | head -3
```
Expected: les 3 lignes attendues (deux `enable_cors = true` + `origins = ...`).

---

## Task 4: ExternalSecret (admin creds → COUCHDB_USER/PASSWORD)

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/externalsecret.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: obsidian-livesync
spec:
  refreshInterval: 12h
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: obsidian-livesync-secret
    creationPolicy: Owner
    template:
      data:
        COUCHDB_USER: "{{ .username }}"
        COUCHDB_PASSWORD: "{{ .password }}"
  dataFrom:
    - extract:
        key: obsidian-livesync
```

- [ ] **Step 2: Validation**

```bash
yq eval . kubernetes/apps/selfhosted/obsidian-livesync/app/externalsecret.yaml >/dev/null && echo OK
```
Expected: `OK`.

---

## Task 5: HelmRelease (CouchDB via app-template)

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/helmrelease.yaml`

- [ ] **Step 1: Écrire le fichier** (image SHA pinned, déjà résolue : `couchdb:3.4.3@sha256:0e3999e6f460dea5051824c80a8709a877fe4ebe4c31c1490026f1c238deb665`)

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: obsidian-livesync
spec:
  interval: 1h
  chartRef:
    kind: OCIRepository
    name: obsidian-livesync
  values:
    controllers:
      obsidian-livesync:
        replicas: 1
        strategy: Recreate
        annotations:
          reloader.stakater.com/auto: "true"
        pod:
          securityContext:
            runAsUser: 5984
            runAsGroup: 5984
            fsGroup: 5984
            fsGroupChangePolicy: OnRootMismatch
            seccompProfile:
              type: RuntimeDefault
        containers:
          app:
            image:
              repository: docker.io/library/couchdb
              tag: 3.4.3@sha256:0e3999e6f460dea5051824c80a8709a877fe4ebe4c31c1490026f1c238deb665
            env:
              TZ: Europe/Paris
              COUCHDB_USER:
                valueFrom:
                  secretKeyRef:
                    name: obsidian-livesync-secret
                    key: COUCHDB_USER
              COUCHDB_PASSWORD:
                valueFrom:
                  secretKeyRef:
                    name: obsidian-livesync-secret
                    key: COUCHDB_PASSWORD
            probes:
              liveness:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 5984
                  initialDelaySeconds: 30
                  periodSeconds: 10
                  timeoutSeconds: 3
                  failureThreshold: 3
              readiness:
                enabled: true
                custom: true
                spec:
                  httpGet:
                    path: /_up
                    port: 5984
                  initialDelaySeconds: 10
                  periodSeconds: 10
                  timeoutSeconds: 3
                  failureThreshold: 3
              startup:
                enabled: true
                custom: true
                spec:
                  tcpSocket:
                    port: 5984
                  failureThreshold: 30
                  periodSeconds: 5
            securityContext:
              allowPrivilegeEscalation: false
              readOnlyRootFilesystem: true
              capabilities:
                drop:
                  - ALL
            resources:
              requests:
                cpu: 50m
                memory: 256Mi
              limits:
                memory: 1Gi
    service:
      app:
        controller: obsidian-livesync
        ports:
          http:
            port: 5984
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
          - obsidian.${SECRET_DOMAIN}
        parentRefs:
          - name: envoy-internal
            namespace: network
    persistence:
      data:
        type: persistentVolumeClaim
        accessMode: ReadWriteOnce
        size: 20Gi
        storageClass: ceph-block
        globalMounts:
          - path: /opt/couchdb/data
      config:
        type: configMap
        name: obsidian-livesync-config
        globalMounts:
          - path: /opt/couchdb/etc/local.d/local.ini
            subPath: local.ini
            readOnly: true
      tmp:
        type: emptyDir
        globalMounts:
          - path: /tmp
```

- [ ] **Step 2: Validation YAML**

```bash
yq eval . kubernetes/apps/selfhosted/obsidian-livesync/app/helmrelease.yaml >/dev/null && echo OK
yq eval '.spec.values.persistence.data.size' kubernetes/apps/selfhosted/obsidian-livesync/app/helmrelease.yaml
```
Expected: `OK` puis `20Gi`.

---

## Task 6: CiliumNetworkPolicy

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/ciliumnetworkpolicy.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: obsidian-livesync
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: obsidian-livesync
      app.kubernetes.io/instance: obsidian-livesync
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "5984"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
```

- [ ] **Step 2: Validation YAML**

```bash
yq eval . kubernetes/apps/selfhosted/obsidian-livesync/app/ciliumnetworkpolicy.yaml >/dev/null && echo OK
```
Expected: `OK`.

---

## Task 7: VolSync (ExternalSecret + ReplicationSource)

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/volsync.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas-ebx.pages.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: obsidian-livesync-volsync
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: obsidian-livesync-volsync-secret
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
  name: obsidian-livesync
spec:
  sourcePVC: obsidian-livesync
  trigger:
    schedule: "30 3 * * *"
  kopia:
    accessModes:
      - ReadWriteOnce
    compression: zstd-fastest
    copyMethod: Snapshot
    moverSecurityContext:
      runAsUser: 5984
      runAsGroup: 5984
      fsGroup: 5984
    moverVolumes:
      - mountPath: repository
        volumeSource:
          nfs:
            path: /mnt/HDD1X4/VolsyncKopia
            server: ${NAS_IP}
    parallelism: 2
    repository: obsidian-livesync-volsync-secret
    retain:
      hourly: 24
      daily: 30
      weekly: 12
      monthly: 6
    storageClassName: ceph-block
    volumeSnapshotClassName: csi-ceph-blockpool
```

- [ ] **Step 2: Validation YAML**

```bash
yq eval -s '.metadata.name' kubernetes/apps/selfhosted/obsidian-livesync/app/volsync.yaml
```
Expected: 2 docs YAML — `obsidian-livesync-volsync` (ExternalSecret) et `obsidian-livesync` (ReplicationSource).

---

## Task 8: Kustomization de l'app

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/app/kustomization.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./configmap.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
  - ./volsync.yaml
```

- [ ] **Step 2: Validation kustomize build**

```bash
cd /home/kryzql/home-ops && kustomize build kubernetes/apps/selfhosted/obsidian-livesync/app 2>&1 | head -20
```
Expected: rendu YAML valide (HelmRelease, ConfigMap, ExternalSecret×2, CNP, ReplicationSource, OCIRepository). Aucune erreur.

---

## Task 9: Flux Kustomization (`ks.yaml`)

**Files:**
- Create: `kubernetes/apps/selfhosted/obsidian-livesync/ks.yaml`

- [ ] **Step 1: Écrire le fichier**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: obsidian-livesync
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: obsidian-livesync
  dependsOn:
    - name: rook-ceph-cluster
      namespace: rook-ceph
    - name: volsync
      namespace: volsync-system
  interval: 1h
  path: "./kubernetes/apps/selfhosted/obsidian-livesync/app"
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: selfhosted
  timeout: 5m
  wait: false
```

- [ ] **Step 2: Validation YAML**

```bash
yq eval . kubernetes/apps/selfhosted/obsidian-livesync/ks.yaml >/dev/null && echo OK
```
Expected: `OK`.

---

## Task 10: Référencer dans `selfhosted/kustomization.yaml`

**Files:**
- Modify: `kubernetes/apps/selfhosted/kustomization.yaml`

- [ ] **Step 1: Ajouter `./obsidian-livesync/ks.yaml` à la liste `resources:`**

Le fichier après modification :

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: selfhosted
components:
  - ../../components/alerts
  - ../../components/sops
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
```

- [ ] **Step 2: Validation kustomize build au niveau parent**

```bash
cd /home/kryzql/home-ops && kustomize build kubernetes/apps/selfhosted 2>&1 | grep -E "kind: Kustomization" | wc -l
```
Expected: nombre = 10 (les 9 apps existantes + obsidian-livesync).

---

## Task 11: Validation flux-local (offline diff)

**Files:** none

- [ ] **Step 1: Lancer flux-local diff**

```bash
cd /home/kryzql/home-ops && flux-local diff ks --path kubernetes 2>&1 | grep -A20 "obsidian" | head -50
```
Expected : nouveaux objets `+` listés (pas de `-` sur les apps existantes). Si erreur de schéma → corriger avant commit.

- [ ] **Step 2: Build complet sans erreur**

```bash
cd /home/kryzql/home-ops && flux-local build ks --path kubernetes 2>&1 | tail -5
```
Expected : `Build completed successfully` ou équivalent, pas d'erreur.

---

## Task 12: Commit Git

**Files:** all created above

- [ ] **Step 1: Stager les changements**

```bash
cd /home/kryzql/home-ops && git add kubernetes/apps/selfhosted/obsidian-livesync/ kubernetes/apps/selfhosted/kustomization.yaml
```

- [ ] **Step 2: Vérifier le diff**

```bash
git diff --cached --stat
```
Expected: 8 nouveaux fichiers + 1 modifié (`selfhosted/kustomization.yaml`).

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(obsidian-livesync): self-host CouchDB for Obsidian sync plugin

Deploy CouchDB 3.4.3 single-node via bjw-s app-template, internal-only
(envoy-internal Gateway, hostname obsidian.${SECRET_DOMAIN}). Storage:
20Gi ceph-block. CORS + LiveSync tuning via configMap-mounted local.ini.
Daily VolSync Kopia backups to NFS NAS.

Spec: docs/superpowers/specs/2026-05-10-obsidian-livesync-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Vérifier l'état**

```bash
git log --oneline -1 && git status
```
Expected: nouveau commit + working tree clean.

---

## Task 13: Post-Flux validation (après merge + reconcile)

> Cette tâche s'exécute **après** que l'utilisateur ait pull + Flux ait reconcilié (≤ 5 minutes après le push).

**Files:** none

- [ ] **Step 1: Forcer la réconciliation Flux**

```bash
flux reconcile kustomization flux-system --with-source && \
flux reconcile kustomization obsidian-livesync -n flux-system
```

- [ ] **Step 2: Vérifier HelmRelease ready**

```bash
kubectl -n selfhosted get hr obsidian-livesync
```
Expected: `READY=True`, `STATUS=Helm install/upgrade succeeded`.

- [ ] **Step 3: Vérifier pod running**

```bash
kubectl -n selfhosted get pod -l app.kubernetes.io/name=obsidian-livesync
```
Expected: `READY=1/1`, `STATUS=Running`.

- [ ] **Step 4: Healthcheck CouchDB depuis le pod**

```bash
ADMIN=$(kubectl -n selfhosted get secret obsidian-livesync-secret -o jsonpath='{.data.COUCHDB_USER}' | base64 -d)
PWD=$(kubectl -n selfhosted get secret obsidian-livesync-secret -o jsonpath='{.data.COUCHDB_PASSWORD}' | base64 -d)
kubectl -n selfhosted exec deploy/obsidian-livesync -- curl -s -u "$ADMIN:$PWD" http://localhost:5984/_up
```
Expected: `{"status":"ok","seeds":{}}`.

- [ ] **Step 5: Healthcheck via la route Envoy depuis le LAN**

```bash
curl -k -s "https://obsidian.${SECRET_DOMAIN}/_up"
```
Expected: `{"status":"ok"}` (pas d'auth requis sur `/_up`). Remplacer `${SECRET_DOMAIN}` par la vraie valeur du domaine interne.

- [ ] **Step 6: CORS preflight**

```bash
curl -i -k -s -X OPTIONS \
  -H "Origin: app://obsidian.md" \
  -H "Access-Control-Request-Method: POST" \
  "https://obsidian.${SECRET_DOMAIN}/" 2>&1 | head -20
```
Expected: header `access-control-allow-origin: app://obsidian.md` + status 204 ou 200.

- [ ] **Step 7: Premier run VolSync** (peut prendre quelques minutes — le snapshot Ceph + push initial Kopia)

```bash
kubectl -n selfhosted get replicationsource obsidian-livesync -o jsonpath='{.status.lastSyncTime}{"\n"}{.status.latestMoverStatus.result}'
```
Expected (après premier 03:30 ou trigger manuel) : timestamp + `Successful`. Si vide → `kubectl -n selfhosted patch replicationsource obsidian-livesync --type=merge -p '{"spec":{"trigger":{"manual":"first-run"}}}'` puis re-vérifier.

---

## Task 14: Configuration côté Obsidian (manual, user)

**Files:** none

- [ ] **Step 1: Installer le plugin** "Self-hosted LiveSync" (vrtmrz) dans Obsidian (desktop + mobile)

- [ ] **Step 2: Ouvrir le wizard** Settings → Self-hosted LiveSync → "Setup Wizard"

- [ ] **Step 3: Renseigner URL + creds**

```
Server URI:  https://obsidian.<SECRET_DOMAIN>
Username:    <admin from 1Password>
Password:    <password from 1Password>
Database:    obsidiandb
```

- [ ] **Step 4: Test connection** dans le wizard → doit afficher "Connected"

- [ ] **Step 5: Activer E2EE** (recommandé) → générer/enregistrer une passphrase forte (à conserver hors-cluster, sinon perte des données chiffrées)

- [ ] **Step 6: Lancer la première synchro** depuis desktop puis ouvrir mobile et configurer le même server / database / passphrase

- [ ] **Step 7: Vérifier sync bidirectionnel** : créer une note sur desktop, vérifier qu'elle apparaît sur mobile dans les secondes qui suivent.

---

## Spec coverage check

| Spec section | Implémenté par |
|---|---|
| Filesystem layout | Tasks 1-10 |
| CouchDB image / SHA pin | Task 5 |
| 20Gi PVC ceph-block | Task 5 |
| local.ini CORS + tuning | Task 3 |
| ExternalSecret 1Password | Task 4 |
| Pod hardening (rootRO, dropALL, runAsNonRoot) | Task 5 |
| HTTPRoute envoy-internal | Task 5 (`route.app`) |
| CiliumNetworkPolicy | Task 6 |
| VolSync Kopia daily NFS | Task 7 |
| Flux Kustomization + dependsOn | Task 9 |
| Référencement parent | Task 10 |
| Post-deploy validation | Task 13 |
| Plugin client config | Task 14 |

Tous les éléments du spec sont couverts.

---

## Rollback

Si la HelmRelease ne devient jamais ready (`kubectl -n selfhosted describe hr obsidian-livesync` → erreur persistante) :

```bash
git revert <commit-sha> && git push
```

ou pour annuler en local avant push :

```bash
git reset --hard HEAD~1
```

Le PVC `obsidian-livesync` (s'il a été créé) sera retenu (`prune: true` au niveau Flux Kustomization, mais Ceph PVC a une `reclaimPolicy: Delete`). Pour préserver les données : annoter le PVC avec `kubernetes.io/persistent-volume-protection` ou le PV avec `Retain` avant le revert.
