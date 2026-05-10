# Obsidian LiveSync (CouchDB) — Design Spec

**Date** : 2026-05-10
**Status** : Draft, awaiting user review
**Owner** : thomloy

## Goal

Déployer un backend CouchDB self-hosted sur le cluster Talos pour permettre la synchronisation temps-réel multi-device des vaults Obsidian via le plugin **Self-hosted LiveSync** (vrtmrz). Le sync est interne au LAN/Tailscale uniquement (pas d'exposition publique).

## Non-goals

- Pas d'exposition externe via Cloudflare Tunnel (interne-only assumé)
- Pas de cluster CouchDB multi-nœud (single-node suffit pour usage perso)
- Pas de gestion automatique des vaults / databases (création manuelle dans Obsidian)
- Pas de Web UI Fauxton publique (accessible uniquement aux admins via le hostname interne)

## Context

- Cluster Talos 1.12.7 + Kubernetes 1.35.4, GitOps via Flux
- Pattern dominant : bjw-s `app-template` chart, OCIRepository + HelmRelease, ExternalSecret (1Password), VolSync Kopia
- Routing interne via Envoy Gateway (parent `envoy-internal` ns `network`), HTTPRoute auto-géré par app-template
- Storage : Rook-Ceph (block) + NFS NAS pour backups VolSync
- Obsidian client : desktop (Linux) + mobile (Android/iOS), plugin LiveSync dispo sur les deux

## Architecture

```
┌────────────────────────────┐
│ Obsidian client (desktop / │
│ mobile, plugin LiveSync)   │
└──────────────┬─────────────┘
               │ HTTPS (LAN/Tailscale)
               │ obsidian.${SECRET_DOMAIN}:443
               ▼
┌────────────────────────────┐
│ Envoy Gateway (internal)   │   ns: network
│ HTTPRoute → CouchDB:5984   │
└──────────────┬─────────────┘
               ▼
┌────────────────────────────┐
│ CouchDB 3.4 (single-node)  │   ns: selfhosted
│ Helm: bjw-s app-template   │
│ PVC ceph-block 20Gi        │
│ Admin creds : ExtSecret    │
└──────────────┬─────────────┘
               │ scheduled 03:30
               ▼
┌────────────────────────────┐
│ VolSync Kopia → NFS NAS    │
└────────────────────────────┘
```

## Components

### Filesystem layout

```
kubernetes/apps/selfhosted/obsidian-livesync/
├── ks.yaml                          # Flux Kustomization (depends on rook-ceph + volsync)
└── app/
    ├── kustomization.yaml
    ├── ocirepository.yaml           # bjw-s app-template OCI ref
    ├── helmrelease.yaml             # CouchDB single-pod via app-template
    ├── externalsecret.yaml          # admin creds depuis 1Password (item: obsidian-livesync)
    ├── ciliumnetworkpolicy.yaml     # ingress depuis envoy-internal + egress NAS
    └── volsync.yaml                 # ReplicationSource Kopia → NFS NAS
```

### CouchDB HelmRelease

| Aspect | Valeur |
|---|---|
| Chart | bjw-s `app-template` (pinned via OCIRepository) |
| Container image | `docker.io/library/couchdb:3.4.x` (pin SHA256 + `# renovate:` annotation) |
| Replicas | 1, strategy `Recreate` |
| User/Group | runAsUser/runAsGroup `5984` (couchdb container default), fsGroup `5984` |
| Probes | TCP `5984` (liveness, startup) + httpGet `/_up` (readiness — endpoint CouchDB natif) |
| readOnlyRootFilesystem | `true` (CouchDB n'écrit qu'à `/opt/couchdb/data` PVC + `/tmp` emptyDir) |
| Annotations | `reloader.stakater.com/auto: "true"` (recharge sur changement secret/configmap), Gatus pushover via `route` annotation |
| TZ env | `Europe/Paris` (cohérent autres apps) |
| capabilities drop | `["ALL"]` |
| Resources | requests `cpu: 50m / mem: 256Mi`, limits `mem: 1Gi` |
| Service | ClusterIP, port `5984` |
| Route | `envoy-internal`, hostname `obsidian.${SECRET_DOMAIN}` |
| Persistence | PVC `ceph-block` 20Gi → `/opt/couchdb/data` |
| Persistence config | configMap → `/opt/couchdb/etc/local.d/local.ini` (CORS + LiveSync tuning) |
| Env | `COUCHDB_USER` + `COUCHDB_PASSWORD` from `obsidian-livesync-secret` |

### CouchDB `local.ini` (mounted via persistence configMap)

```ini
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

Justification : valeurs recommandées par la doc officielle Self-hosted LiveSync (`vrtmrz/obsidian-livesync` setup_own_server.md). Sans CORS + headers ad hoc, les clients Obsidian mobile/desktop ne peuvent pas authentifier ni synchroniser.

### ExternalSecret

Item 1Password (`kubernetes` vault) **à créer manuellement par l'utilisateur AVANT le merge Flux** (sinon le HelmRelease bloque sur le secret manquant) :
- name : `obsidian-livesync`
- fields :
  - `username` (admin CouchDB, ex: `admin`)
  - `password` (≥ 24 chars random)

Mapped to k8s secret `obsidian-livesync-secret` :
- `COUCHDB_USER` ← `username`
- `COUCHDB_PASSWORD` ← `password`

### CiliumNetworkPolicy

- **ingress** : depuis pods Envoy Gateway (label `gateway.networking.k8s.io/gateway-name=envoy-internal`) sur 5984/TCP, plus stanza ingress kube-dns par cohérence avec le pattern repo
- **egress** : aucune règle déclarée → autorisé par défaut (pattern documenté en mémoire `feedback_cilium_toentities_world` et `feedback_cilium_socketlb` : les egress rules sont fragiles en mode Cilium socketLB+DSR ; seul `immich` les utilise et avec un workaround spécifique)

### VolSync ReplicationSource

| Aspect | Valeur |
|---|---|
| copyMethod | Snapshot (CSI snapshot ceph-block puis backup) |
| sourcePVC | `obsidian-livesync` (le PVC CouchDB) |
| trigger schedule | `30 3 * * *` (cohérent avec autres apps) |
| repository | NFS `/mnt/HDD1X4/VolsyncKopia` (pattern existant) |
| retain | hourly 24, daily 30, weekly 12, monthly 6 (pattern par défaut du repo) |
| KOPIA_PASSWORD / REPOSITORY | via ExternalSecret `volsync-template` (réutilisé) |

### Flux Kustomization (`ks.yaml`)

- `dependsOn` : `rook-ceph-cluster` (ns `rook-ceph`) + `volsync` (ns `volsync-system`) — pattern repo (les autres apps `selfhosted` ne référencent pas `external-secrets-stores` ou `healthChecks`, ces dépendances sont assumées implicitement par l'ordre de bootstrap)
- targetNamespace : `selfhosted`
- pas de `healthChecks` ni `wait: true` (pattern repo : `wait: false`, monitoring via Gatus)

## Data flow

1. Obsidian client → POST/GET HTTPS sur `https://obsidian.${SECRET_DOMAIN}/<db>`
2. DNS interne (UDM Pro Max) résout vers IP Envoy internal Gateway (192.168.42.110)
3. Envoy Gateway termine TLS, route HTTP vers Service `obsidian-livesync:5984` namespace `selfhosted`
4. CouchDB authentifie avec basic auth, lit/écrit dans la base
5. PVC stocké sur Ceph (3 replicas)
6. Quotidien à 03:30 : VolSync snapshot → Kopia push vers NFS NAS
7. Tailscale users : utilisent l'hostname interne ; subnet routing 192.168.42.0/24 doit être actif côté Tailscale (déjà en place selon CLAUDE.md)

## Error handling & operational concerns

- **CouchDB OOM** : limit 1Gi devrait suffire pour vault perso. À monitorer via Prom (kube-state-metrics) ; alerte si memory_working_set > 80% sustained
- **PVC fill** : 20Gi avec retention LiveSync par défaut tient des années pour vaults perso. Alerte VolumeUsage > 85% (existante via kube-prometheus-stack)
- **CORS regression** : si LiveSync échoue à se connecter, vérifier en premier `local.ini` monté correctement et `enable_cors=true`
- **Backup integrity** : Kopia checks intégrés ; alertes Gatus existantes sur les VolSync jobs
- **Single point of failure** : single-replica + pod sur 1 node. Acceptable pour usage perso (vault répliqué côté clients de toute façon). Si node down → re-scheduling sur autre node (PVC ceph-block multi-attach false, mais Recreate strategy gère)

## Security

- TLS terminé à Envoy Gateway (cert wildcard cert-manager/Let's Encrypt déjà en place)
- Basic Auth CouchDB obligatoire (`require_valid_user = true`)
- E2EE optionnel côté plugin LiveSync (passphrase client, CouchDB ne voit que des blobs chiffrés)
- Pas d'exposition externe → 0 attack surface depuis Internet
- Pod hardening : `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `runAsNonRoot: true`
- CORS limité aux origins Obsidian connus
- NetworkPolicy deny-by-default

## Testing & validation

Post-deploy checklist :
1. `kubectl -n selfhosted get hr obsidian-livesync` → ready
2. `kubectl -n selfhosted exec deploy/obsidian-livesync -- curl -s -u admin:<pwd> http://localhost:5984/_up` → `{"status":"ok"}`
3. Depuis LAN : `curl -k https://obsidian.${SECRET_DOMAIN}/_up` → `{"status":"ok"}`
4. CORS preflight : `curl -X OPTIONS -H "Origin: app://obsidian.md" -H "Access-Control-Request-Method: POST" https://obsidian.${SECRET_DOMAIN}/<db>` → status 204 + `access-control-allow-origin` header
5. Plugin LiveSync se connecte sans erreur depuis desktop + mobile
6. Snapshot VolSync premier run réussit (`kubectl -n selfhosted get replicationsource obsidian-livesync -o yaml | yq '.status.lastSyncTime'`)

## Out of scope

- Migration de vault Obsidian existant (à faire manuellement via plugin si besoin)
- Self-test automatisé du sync (pas de fixture)
- Calendar sync — déjà couvert par Nextcloud Calendar (séparé)

## Open follow-ups (non bloquants pour ce spec)

- Considérer dashboard Grafana CouchDB (exporter `gesellix/couchdb-prometheus-exporter`)
- Si scaling devient nécessaire (peu probable) : passer à clustering CouchDB officiel
