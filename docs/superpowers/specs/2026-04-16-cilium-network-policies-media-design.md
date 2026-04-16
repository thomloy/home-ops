# CiliumNetworkPolicy — namespace `media`

**Date:** 2026-04-16
**Scope:** namespace `media` (phase 3)

---

## Contexte

Suite de la phase 2 (selfhosted). Le namespace `media` contient 4 apps : Emby, Audiobookshelf, Navidrome, Seerr.

Particularités :
- Emby a déjà une policy partielle (ingress uniquement) → à compléter avec egress + ingress LAN direct
- Emby utilise un service `type: LoadBalancer` (IP directe LAN) → nécessite `fromEntities: world` sur le port 8096 pour autoriser l'accès direct depuis les appareils LAN (TV, mobiles)
- `mumc` et `arrem-sync` apparaissent dans l'ancienne policy emby mais ne sont plus déployés → exclus
- Les 3 apps avec NFS (emby, navidrome, audiobookshelf) ont besoin d'egress internet (`toEntities: world`) qui couvre aussi le trafic NFS vers le NAS (IP externe au cluster)
- Radarr et Sonarr autorisent déjà ingress depuis seerr (fait en phase 1)

---

## Labels réels des pods (kubectl get pods -n media)

| Pod | name | instance | controller |
|-----|------|----------|------------|
| emby | emby | emby | emby |
| audiobookshelf | audiobookshelf | audiobookshelf | audiobookshelf |
| navidrome | navidrome | navidrome | navidrome |
| seerr | seerr | seerr | seerr |

---

## Ports de services (kubectl get svc -n media)

| Service | Port |
|---------|------|
| emby | 8096 |
| audiobookshelf | 80 |
| navidrome | 4533 |
| seerr | 5055 |

---

## Matrice de communication

| App | Ingress depuis | Egress vers | Internet |
|-----|---------------|-------------|---------|
| emby (8096) | Gateway, Seerr, Glance, Radarr, Sonarr, LAN direct (world) | DNS, world (NFS NAS + métadonnées + plugins) | ✅ |
| audiobookshelf (80) | Gateway, Glance | DNS, world (NFS NAS + podcasts + métadonnées) | ✅ |
| navidrome (4533) | Gateway | DNS, world (NFS NAS + Last.fm + MusicBrainz) | ✅ |
| seerr (5055) | Gateway | DNS, world (TMDB/TVDB APIs), media/emby:8096, downloads/radarr:7878, downloads/sonarr:8989 | ✅ |

---

## Structure des fichiers

```
kubernetes/apps/media/
├── emby/app/ciliumnetworkpolicy.yaml        ← mise à jour (remplacer policy partielle)
├── audiobookshelf/app/ciliumnetworkpolicy.yaml  ← nouveau
├── navidrome/app/ciliumnetworkpolicy.yaml   ← nouveau
└── seerr/app/ciliumnetworkpolicy.yaml       ← nouveau
```

---

## Cas particuliers

### Emby — policy existante à remplacer

La policy existante couvre l'ingress (gateway, seerr, glance, radarr, sonarr + mumc/arrem-sync désormais exclus) mais pas l'egress. Elle sera remplacée par une version complète qui :
- Conserve les ingress existants (sans mumc et arrem-sync)
- Ajoute `fromEntities: world` sur port 8096 pour accès LAN direct via LB
- Ajoute egress : DNS + `toEntities: world`

### Emby — service LoadBalancer

Emby expose un service `type: LoadBalancer` avec `externalTrafficPolicy: Local`. Les appareils LAN (TV, mobiles) accèdent directement à l'IP LB (192.168.42.110). Ce trafic arrive avec l'IP source du client LAN et est classifié `world` par Cilium. L'ajout de `fromEntities: [world]` dans l'ingress est nécessaire pour maintenir cet accès.

### Emby — schema comment existant

La policy emby existante a un schema comment légèrement différent (`# yaml-language-server: https://...` sans `$schema=`). La version remplacée utilisera le format standard avec `$schema=`.

### NFS — couvert par toEntities: world

Les apps qui montent du NFS depuis le NAS (emby, audiobookshelf, navidrome) n'ont pas besoin de règle NFS séparée. `toEntities: world` couvre à la fois l'accès internet ET le trafic NFS vers le NAS (IP hors cluster).

---

## Matrice de flux réseau complète

| Source | Destination | Port | Proto | Justification |
|--------|-------------|------|-------|---------------|
| **media/emby** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **media/emby** | internet (world) | * | TCP | NFS NAS, métadonnées, plugins |
| **media/audiobookshelf** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **media/audiobookshelf** | internet (world) | * | TCP | NFS NAS, flux podcast, métadonnées |
| **media/navidrome** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **media/navidrome** | internet (world) | * | TCP | NFS NAS, Last.fm, MusicBrainz |
| **media/seerr** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **media/seerr** | internet (world) | * | TCP | TMDB, TVDB APIs |
| **media/seerr** | media/emby | 8096 | TCP | Intégration media server |
| **media/seerr** | downloads/radarr | 7878 | TCP | Gestion films |
| **media/seerr** | downloads/sonarr | 8989 | TCP | Gestion séries |
| network/envoy-internal | media/emby | 8096 | TCP | UI / API |
| network/envoy-internal | media/audiobookshelf | 80 | TCP | UI |
| network/envoy-internal | media/navidrome | 4533 | TCP | UI |
| network/envoy-internal | media/seerr | 5055 | TCP | UI |
| world (LAN direct) | media/emby | 8096 | TCP | Accès LAN direct via LB IP |
| selfhosted/glance | media/emby | 8096 | TCP | Widget Glance |
| selfhosted/glance | media/audiobookshelf | 80 | TCP | Widget Glance |
| downloads/radarr | media/emby | 8096 | TCP | Notification import |
| downloads/sonarr | media/emby | 8096 | TCP | Notification import |
| media/seerr | media/emby | 8096 | TCP | Requêtes media |

---

## Rollout progressif

1. **Phase 1 (done)** : namespace `downloads`
2. **Phase 2 (done)** : namespace `selfhosted` + mises à jour `downloads` pour Glance
3. **Phase 3 (ce spec)** : namespace `media`
4. **Phase 4** : namespace `default`
5. **Phase 5** : namespaces infrastructure
