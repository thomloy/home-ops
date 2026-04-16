# CiliumNetworkPolicy — namespace `selfhosted`

**Date:** 2026-04-16
**Scope:** namespace `selfhosted` (phase 2) + mises à jour rétroactives `downloads`

---

## Contexte

Suite de la phase 1 (downloads). Le namespace `selfhosted` contient des apps avec des données sensibles (photos Immich, documents Paperless, budget Actual Budget, fichiers Nextcloud). Il est aussi plus complexe car :
- Glance contacte des services dans 5 namespaces différents → nécessite des mises à jour rétroactives des policies downloads
- Immich utilise son chart officiel (pas bjw-s app-template) → labels non standard
- Nextcloud et Immich ont des CNPG clusters dans le même namespace (pods `app.kubernetes.io/name=postgresql`)
- Paperless a déjà une policy partielle (ingress seulement) → à compléter avec egress

---

## Labels réels des pods (kubectl get pods -n selfhosted)

| Pod | name | instance | controller |
|-----|------|----------|------------|
| actual-budget | actual-budget | actual-budget | actual-budget |
| bentopdf | bentopdf | bentopdf | bentopdf |
| glance | glance | glance | glance |
| immich-server | server | immich | main |
| immich-machine-learning | machine-learning | immich | main |
| immich-valkey | valkey | immich | main |
| it-tools | it-tools | it-tools | it-tools |
| nextcloud (app+cron) | nextcloud | nextcloud | nextcloud |
| nextcloud-valkey | nextcloud | nextcloud | valkey |
| paperless | paperless | paperless | paperless |
| paperless-redis | paperless | paperless | redis |
| paperless-tika | paperless | paperless | tika |
| paperless-gotenberg | paperless | paperless | gotenberg |
| immich-postgres-{1,2,3} | postgresql | immich-postgres | — (CNPG) |
| nextcloud-postgres-{1,2,3} | postgresql | nextcloud-postgres | — (CNPG) |

**CNPG pods** : pas de CiliumNetworkPolicy créée pour eux. Ils restent en trafic libre (réplication inter-pod, Barman S3 intacts).

---

## Ports de services (kubectl get svc -n selfhosted)

| Service | Port |
|---------|------|
| actual-budget | 5006 |
| bentopdf | 8080 |
| glance | 8080 |
| it-tools | 8080 |
| immich-server | 2283 (main), 8081 (metrics Prometheus) |
| immich-machine-learning | 3003 |
| immich-valkey | 6379 |
| immich-postgres-rw | 5432 |
| nextcloud-app | 80 |
| nextcloud-valkey | 6379 |
| nextcloud-postgres-rw | 5432 |
| paperless | 8000 |
| paperless-redis | 6379 |
| paperless-tika | 9998 |
| paperless-gotenberg | 3000 |

---

## Matrice de communication

| App | Ingress depuis | Egress vers | Internet |
|-----|---------------|-------------|---------|
| actual-budget (5006) | Gateway, Glance | DNS | ❌ |
| bentopdf (8080) | Gateway | DNS | ❌ |
| it-tools (8080) | Gateway, Glance | DNS | ❌ |
| glance (8080) | Gateway | DNS, internet, observability/prometheus:9090, observability/grafana:3000, media/emby:8096, media/audiobookshelf:80, downloads/radarr:7878, downloads/sonarr:8989, downloads/bazarr:80, downloads/prowlarr:80, downloads/sabnzbd:80, downloads/qbittorrent:8080, selfhosted/paperless:8000, selfhosted/it-tools:8080, selfhosted/actual-budget:5006, selfhosted/nextcloud:80, default/tandoor:80 | ✅ |
| immich-server (2283, 8081) | Gateway, Prometheus | DNS, immich-postgres:5432, immich-valkey:6379, immich-machine-learning:3003 | ❌ |
| immich-machine-learning (3003) | immich-server | DNS | ✅ (modèles ML) |
| immich-valkey (6379) | immich-server | DNS | ❌ |
| nextcloud (80) | Gateway, Glance | DNS, nextcloud-postgres:5432, nextcloud-valkey:6379 | ✅ |
| nextcloud-valkey (6379) | nextcloud (controller=nextcloud) | DNS | ❌ |
| paperless (8000) | Gateway, Glance | DNS, paperless-redis:6379, paperless-tika:9998, paperless-gotenberg:3000 | ❌ |
| paperless-redis (6379) | paperless (controller=paperless) | DNS | ❌ |
| paperless-tika (9998) | paperless (controller=paperless) | DNS | ❌ |
| paperless-gotenberg (3000) | paperless (controller=paperless) | DNS | ❌ |

---

## Mises à jour rétroactives — namespace `downloads`

Glance contacte 6 apps dans `downloads`. Leurs policies actuelles n'autorisent pas l'ingress depuis Glance. Chaque policy doit être mise à jour pour ajouter :

```yaml
- matchLabels:
    k8s:io.kubernetes.pod.namespace: selfhosted
    app.kubernetes.io/name: glance
```

| App downloads | Port concerné |
|---------------|---------------|
| radarr | 7878 |
| sonarr | 8989 |
| bazarr | 80 |
| prowlarr | 80 |
| sabnzbd | 80 |
| qbittorrent | 8080 |

---

## Cas particuliers

### Nextcloud-valkey — discrimination par `controller`

Les pods nextcloud-app et nextcloud-valkey ont le même `app.kubernetes.io/name=nextcloud`. Pour les distinguer :
- nextcloud-app : `app.kubernetes.io/controller: nextcloud`
- nextcloud-valkey : `app.kubernetes.io/controller: valkey`

### Paperless — policy existante à compléter

La policy existante couvre l'ingress (gateway + glance) mais pas l'egress. Elle sera remplacée par une version complète qui inclut les règles egress (redis, tika, gotenberg, DNS).

### Immich — chart officiel, labels non standard

- `endpointSelector` pour immich-server : `app.kubernetes.io/name=server, app.kubernetes.io/instance=immich`
- `endpointSelector` pour machine-learning : `app.kubernetes.io/name=machine-learning, app.kubernetes.io/instance=immich`
- `endpointSelector` pour valkey : `app.kubernetes.io/name=valkey, app.kubernetes.io/instance=immich`

### CNPG — ciblage via label Cilium

Pour autoriser l'egress des apps vers CNPG (via le service `*-postgres-rw` qui route vers le pod primary) :

```yaml
- toEndpoints:
    - matchLabels:
        k8s:io.kubernetes.pod.namespace: selfhosted
        cnpg.io/cluster: immich-postgres
```

---

## Structure des fichiers

```
kubernetes/apps/selfhosted/
├── actual-budget/app/ciliumnetworkpolicy.yaml   ← nouveau
├── bentopdf/app/ciliumnetworkpolicy.yaml        ← nouveau
├── it-tools/app/ciliumnetworkpolicy.yaml        ← nouveau
├── glance/app/ciliumnetworkpolicy.yaml          ← nouveau
├── immich/app/ciliumnetworkpolicy.yaml          ← nouveau (server + ML + valkey)
├── nextcloud/app/ciliumnetworkpolicy.yaml       ← nouveau (nextcloud + valkey)
└── paperless/app/ciliumnetworkpolicy.yaml       ← mise à jour (ajouter egress)

kubernetes/apps/downloads/
├── radarr/app/ciliumnetworkpolicy.yaml          ← mise à jour (ajouter Glance)
├── sonarr/app/ciliumnetworkpolicy.yaml          ← mise à jour
├── bazarr/app/ciliumnetworkpolicy.yaml          ← mise à jour
├── prowlarr/app/ciliumnetworkpolicy.yaml        ← mise à jour
├── sabnzbd/app/ciliumnetworkpolicy.yaml         ← mise à jour
└── qbittorrent/app/ciliumnetworkpolicy.yaml     ← mise à jour
```

---

## Matrice de flux réseau complète

| Source | Destination | Port | Proto | Justification |
|--------|-------------|------|-------|---------------|
| **selfhosted/actual-budget** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/bentopdf** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/it-tools** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/glance** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/glance** | internet (world) | * | TCP | Météo, GitHub, NAS:9100 |
| **selfhosted/glance** | observability/prometheus | 9090 | TCP | Métriques nodes |
| **selfhosted/glance** | observability/grafana | 3000 | TCP | Dashboard |
| **selfhosted/glance** | media/emby | 8096 | TCP | Intégration media |
| **selfhosted/glance** | media/audiobookshelf | 80 | TCP | Intégration media |
| **selfhosted/glance** | downloads/radarr | 7878 | TCP | Intégration downloads |
| **selfhosted/glance** | downloads/sonarr | 8989 | TCP | Intégration downloads |
| **selfhosted/glance** | downloads/bazarr | 80 | TCP | Intégration downloads |
| **selfhosted/glance** | downloads/prowlarr | 80 | TCP | Intégration downloads |
| **selfhosted/glance** | downloads/sabnzbd | 80 | TCP | Intégration downloads |
| **selfhosted/glance** | downloads/qbittorrent | 8080 | TCP | Intégration downloads |
| **selfhosted/glance** | selfhosted/paperless | 8000 | TCP | Intégration selfhosted |
| **selfhosted/glance** | selfhosted/it-tools | 8080 | TCP | Intégration selfhosted |
| **selfhosted/glance** | selfhosted/actual-budget | 5006 | TCP | Intégration selfhosted |
| **selfhosted/glance** | selfhosted/nextcloud | 80 | TCP | Intégration selfhosted |
| **selfhosted/glance** | default/tandoor | 80 | TCP | Intégration selfhosted |
| **selfhosted/immich-server** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/immich-server** | selfhosted/immich-postgres | 5432 | TCP | Base de données |
| **selfhosted/immich-server** | selfhosted/immich-valkey | 6379 | TCP | Cache |
| **selfhosted/immich-server** | selfhosted/immich-machine-learning | 3003 | TCP | Inférence ML |
| **selfhosted/immich-machine-learning** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/immich-machine-learning** | internet (world) | * | TCP | Téléchargement modèles |
| **selfhosted/immich-valkey** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/nextcloud** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/nextcloud** | selfhosted/nextcloud-postgres | 5432 | TCP | Base de données |
| **selfhosted/nextcloud** | selfhosted/nextcloud-valkey | 6379 | TCP | Cache |
| **selfhosted/nextcloud** | internet (world) | * | TCP | Federation, apps |
| **selfhosted/nextcloud-valkey** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/paperless** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/paperless** | selfhosted/paperless-redis | 6379 | TCP | Queue de tâches |
| **selfhosted/paperless** | selfhosted/paperless-tika | 9998 | TCP | Extraction texte |
| **selfhosted/paperless** | selfhosted/paperless-gotenberg | 3000 | TCP | Conversion PDF |
| **selfhosted/paperless-redis** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/paperless-tika** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **selfhosted/paperless-gotenberg** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| network/envoy-internal | selfhosted/actual-budget | 5006 | TCP | UI |
| network/envoy-internal | selfhosted/bentopdf | 8080 | TCP | UI |
| network/envoy-internal | selfhosted/glance | 8080 | TCP | UI |
| network/envoy-internal | selfhosted/it-tools | 8080 | TCP | UI |
| network/envoy-internal | selfhosted/immich-server | 2283 | TCP | UI |
| network/envoy-internal | selfhosted/nextcloud | 80 | TCP | UI |
| network/envoy-internal | selfhosted/paperless | 8000 | TCP | UI |
| observability/prometheus | selfhosted/immich-server | 8081 | TCP | Scraping métriques |
| **Mises à jour downloads** | | | | |
| selfhosted/glance | downloads/radarr | 7878 | TCP | Déjà dans glance egress |
| selfhosted/glance | downloads/sonarr | 8989 | TCP | Déjà dans glance egress |
| selfhosted/glance | downloads/bazarr | 80 | TCP | Déjà dans glance egress |
| selfhosted/glance | downloads/prowlarr | 80 | TCP | Déjà dans glance egress |
| selfhosted/glance | downloads/sabnzbd | 80 | TCP | Déjà dans glance egress |
| selfhosted/glance | downloads/qbittorrent | 8080 | TCP | Déjà dans glance egress |

---

## Rollout progressif

1. **Phase 1 (done)** : namespace `downloads`
2. **Phase 2 (ce spec)** : namespace `selfhosted` + mises à jour `downloads` pour Glance
3. **Phase 3** : namespace `media`
4. **Phase 4** : namespace `default`
5. **Phase 5** : namespaces infrastructure
