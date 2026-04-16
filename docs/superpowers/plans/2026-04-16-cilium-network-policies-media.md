# CiliumNetworkPolicy — namespace `media` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter des CiliumNetworkPolicies à tout le namespace `media` (default-deny implicite).

**Architecture:** Une policy par app dans `{app}/app/ciliumnetworkpolicy.yaml`. La policy Emby existante (ingress uniquement) est remplacée par une version complète avec egress + accès LAN direct.

**Tech Stack:** Cilium CNI, CiliumNetworkPolicy v2, Kustomize, Flux CD

**Spec:** `docs/superpowers/specs/2026-04-16-cilium-network-policies-media-design.md`

---

### Task 1 : emby (mise à jour — remplacer policy existante)

La policy existante n'a que l'ingress. Elle est remplacée par une version complète qui ajoute egress (DNS + world) et `fromEntities: world` pour l'accès LAN direct via le service LoadBalancer.

**Fichiers :**
- Remplacer : `kubernetes/apps/media/emby/app/ciliumnetworkpolicy.yaml`
- `kustomization.yaml` référence déjà la policy — pas de modification nécessaire

- [ ] **Remplacer `ciliumnetworkpolicy.yaml`** (écraser le fichier existant avec Write)

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: emby
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: emby
      app.kubernetes.io/instance: emby
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: media
            app.kubernetes.io/name: seerr
      toPorts:
        - ports:
            - port: "8096"
              protocol: TCP
    - fromEntities:
        - world
      toPorts:
        - ports:
            - port: "8096"
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
    - toEntities:
        - world
```

- [ ] **Commit**

```bash
git add kubernetes/apps/media/emby/app/ciliumnetworkpolicy.yaml
git commit -m "feat(media/emby): complete CiliumNetworkPolicy with egress + LAN direct access"
```

---

### Task 2 : audiobookshelf (port 80)

**Fichiers :**
- Créer : `kubernetes/apps/media/audiobookshelf/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/media/audiobookshelf/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: audiobookshelf
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: audiobookshelf
      app.kubernetes.io/instance: audiobookshelf
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
      toPorts:
        - ports:
            - port: "80"
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
    - toEntities:
        - world
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/media/audiobookshelf/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/media/audiobookshelf/app/kustomization.yaml
git commit -m "feat(media/audiobookshelf): add CiliumNetworkPolicy"
```

---

### Task 3 : navidrome (port 4533)

**Fichiers :**
- Créer : `kubernetes/apps/media/navidrome/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/media/navidrome/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: navidrome
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: navidrome
      app.kubernetes.io/instance: navidrome
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "4533"
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
    - toEntities:
        - world
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/media/navidrome/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/media/navidrome/app/kustomization.yaml
git commit -m "feat(media/navidrome): add CiliumNetworkPolicy"
```

---

### Task 4 : seerr (port 5055)

**Fichiers :**
- Créer : `kubernetes/apps/media/seerr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/media/seerr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: seerr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: seerr
      app.kubernetes.io/instance: seerr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "5055"
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
    - toEntities:
        - world
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: media
            app.kubernetes.io/name: emby
      toPorts:
        - ports:
            - port: "8096"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
      toPorts:
        - ports:
            - port: "7878"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
      toPorts:
        - ports:
            - port: "8989"
              protocol: TCP
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/media/seerr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/media/seerr/app/kustomization.yaml
git commit -m "feat(media/seerr): add CiliumNetworkPolicy"
```

---

### Task 5 : Validation post-déploiement

- [ ] **Vérifier les policies media**

```bash
kubectl get ciliumnetworkpolicy -n media
```

Résultat attendu : audiobookshelf, emby, navidrome, seerr

- [ ] **Tester Emby**

Ouvrir Emby via hostname ET via IP directe LAN — vérifier que la bibliothèque s'affiche.

- [ ] **Tester Audiobookshelf**

Ouvrir Audiobookshelf, vérifier que les livres audio sont accessibles.

- [ ] **Tester Navidrome**

Ouvrir Navidrome, vérifier que la musique est accessible.

- [ ] **Tester Seerr**

Ouvrir Seerr, vérifier que Emby/Radarr/Sonarr apparaissent comme connectés dans les paramètres.

- [ ] **Surveiller les drops Cilium si une app ne répond plus**

```bash
kubectl exec -n kube-system -it ds/cilium -- cilium monitor --type drop 2>/dev/null | head -50
```
