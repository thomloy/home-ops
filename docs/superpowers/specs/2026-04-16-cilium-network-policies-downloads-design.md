# CiliumNetworkPolicy — namespace `downloads`

**Date:** 2026-04-16
**Scope:** namespace `downloads` uniquement (phase 1 d'un rollout progressif sur tous les namespaces)

---

## Contexte

Le cluster home-ops utilise Cilium comme CNI avec eBPF. Deux `CiliumNetworkPolicy` existaient déjà (`emby`, `paperless`) mais le namespace `downloads` n'avait aucune restriction réseau. En l'absence de policy, Cilium laisse tout le trafic passer librement entre namespaces.

## Objectif

- Appliquer un modèle **default-deny implicite** sur toutes les apps du namespace `downloads`
- Autoriser uniquement les flux légitimes (UI via gateway, inter-app, egress internet sélectif)
- Bloquer le lateral movement vers d'autres namespaces (observability, selfhosted, kube-system, etc.)

## Approche retenue

**Une `CiliumNetworkPolicy` par app** dans `kubernetes/apps/downloads/{app}/app/ciliumnetworkpolicy.yaml`.

Raisons :
- Cohérent avec le pattern existant (`emby`, `paperless`)
- Chaque policy lisible indépendamment
- Suffisant pour ~10 apps

Dès qu'une app a une policy Cilium, tout trafic non explicitement autorisé est **implicitement refusé** — pas besoin d'objet deny-all séparé.

---

## Règles communes à toutes les apps

### Ingress
- Autorisé depuis Envoy Gateway (`network` namespace, label `gateway.networking.k8s.io/gateway-name: envoy-internal`) sur le port HTTP de l'app

### Egress
- Autorisé vers `kube-system/kube-dns` port 53 UDP+TCP (résolution DNS)

---

## Matrice de communication

| App | Port | Ingress supplémentaire | Egress interne | Egress internet |
|-----|------|----------------------|----------------|-----------------|
| Radarr | 7878 | Bazarr (downloads), Seerr (media) | Prowlarr, qBittorrent, SABnzbd | ❌ |
| Sonarr | 8989 | Bazarr (downloads), Seerr (media) | Prowlarr, qBittorrent, SABnzbd | ❌ |
| Prowlarr | 80 | Radarr, Sonarr, Readarr, Lidarr (downloads) | DNS uniquement | ✅ (indexers) |
| qBittorrent | 8080 | Radarr, Sonarr, Readarr, Lidarr (downloads) | DNS uniquement | ✅ (peers BitTorrent, port 50469) |
| SABnzbd | 80 | Radarr, Sonarr, Readarr, Lidarr (downloads) | DNS uniquement | ✅ (Usenet NNTP) |
| Bazarr | 80 | — | Sonarr, Radarr | ✅ (fournisseurs sous-titres) |
| Readarr | 8787 | — | Prowlarr, qBittorrent, SABnzbd | ❌ |
| Lidarr | 8686 | — | Prowlarr, qBittorrent, SABnzbd | ❌ |
| Recyclarr | — (CronJob) | ❌ (pas d'ingress) | Sonarr, Radarr | ❌ |

---

## Structure des fichiers

```
kubernetes/apps/downloads/
├── radarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml         ← ajouter la référence
├── sonarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── prowlarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── qbittorrent/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── sabnzbd/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── bazarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── readarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
├── lidarr/app/
│   ├── ciliumnetworkpolicy.yaml   ← nouveau
│   └── kustomization.yaml
└── recyclarr/app/
    ├── ciliumnetworkpolicy.yaml   ← nouveau
    └── kustomization.yaml
```

---

## Pattern de référence — Radarr

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: radarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: radarr
      app.kubernetes.io/instance: radarr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: bazarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: media
            app.kubernetes.io/name: seerr
      toPorts:
        - ports:
            - port: "7878"
              protocol: TCP
  egress:
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:app: kube-dns
      toPorts:
        - ports:
            - port: "53"
              protocol: UDP
            - port: "53"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: prowlarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: qbittorrent
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sabnzbd
```

---

## Rollout progressif

1. **Phase 1 (ce spec)** : namespace `downloads`
2. **Phase 2** : namespace `selfhosted` (données sensibles)
3. **Phase 3** : namespace `media`
4. **Phase 4** : namespace `default`
5. **Phase 5** : namespaces infrastructure (`observability`, `network`, `kube-system`)
