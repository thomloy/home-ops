# CiliumNetworkPolicy — namespace `downloads` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une `CiliumNetworkPolicy` par app dans le namespace `downloads` pour appliquer un default-deny implicite et n'autoriser que les flux légitimes.

**Architecture:** Une policy par app dans `{app}/app/ciliumnetworkpolicy.yaml`, référencée dans `kustomization.yaml`. Dès qu'une policy existe sur un pod Cilium, tout trafic non listé est refusé implicitement. Pas de deny-all explicite nécessaire.

**Tech Stack:** Cilium CNI, CiliumNetworkPolicy v2, Kustomize, Flux CD

**Spec:** `docs/superpowers/specs/2026-04-16-cilium-network-policies-downloads-design.md`

---

### Task 1 : Radarr (port 7878)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/radarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/radarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/radarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/radarr/app/kustomization.yaml
git commit -m "feat(downloads/radarr): add CiliumNetworkPolicy"
```

---

### Task 2 : Sonarr (port 8989)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/sonarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/sonarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: sonarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: sonarr
      app.kubernetes.io/instance: sonarr
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
            - port: "8989"
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/sonarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/sonarr/app/kustomization.yaml
git commit -m "feat(downloads/sonarr): add CiliumNetworkPolicy"
```

---

### Task 3 : Prowlarr (port 80, egress internet)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/prowlarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/prowlarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: prowlarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: prowlarr
      app.kubernetes.io/instance: prowlarr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: readarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: lidarr
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ocirepository.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/prowlarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/prowlarr/app/kustomization.yaml
git commit -m "feat(downloads/prowlarr): add CiliumNetworkPolicy"
```

---

### Task 4 : qBittorrent (port 8080 UI, port 50469 torrent, egress internet)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/qbittorrent/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/qbittorrent/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: qbittorrent
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: qbittorrent
      app.kubernetes.io/instance: qbittorrent
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: readarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: lidarr
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
    - fromEntities:
        - world
      toPorts:
        - ports:
            - port: "50469"
              protocol: TCP
            - port: "50469"
              protocol: UDP
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/qbittorrent/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/qbittorrent/app/kustomization.yaml
git commit -m "feat(downloads/qbittorrent): add CiliumNetworkPolicy"
```

---

### Task 5 : SABnzbd (port 80, egress internet Usenet)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/sabnzbd/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/sabnzbd/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: sabnzbd
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: sabnzbd
      app.kubernetes.io/instance: sabnzbd
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: readarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: lidarr
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ocirepository.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/sabnzbd/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/sabnzbd/app/kustomization.yaml
git commit -m "feat(downloads/sabnzbd): add CiliumNetworkPolicy"
```

---

### Task 6 : Bazarr (port 80, egress internet sous-titres)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/bazarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/bazarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: bazarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: bazarr
      app.kubernetes.io/instance: bazarr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
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
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
    - toEntities:
        - world
```

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/bazarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/bazarr/app/kustomization.yaml
git commit -m "feat(downloads/bazarr): add CiliumNetworkPolicy"
```

---

### Task 7 : Readarr (port 8787)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/readarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/readarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: readarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: readarr
      app.kubernetes.io/instance: readarr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "8787"
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/readarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/readarr/app/kustomization.yaml
git commit -m "feat(downloads/readarr): add CiliumNetworkPolicy"
```

---

### Task 8 : Lidarr (port 8686)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/lidarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/lidarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: lidarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: lidarr
      app.kubernetes.io/instance: lidarr
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "8686"
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

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/lidarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/lidarr/app/kustomization.yaml
git commit -m "feat(downloads/lidarr): add CiliumNetworkPolicy"
```

---

### Task 9 : Recyclarr (CronJob, pas d'ingress)

**Fichiers :**
- Créer : `kubernetes/apps/downloads/recyclarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/recyclarr/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: recyclarr
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: recyclarr
      app.kubernetes.io/instance: recyclarr
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
            app.kubernetes.io/name: sonarr
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: radarr
```

- [ ] **Ajouter la référence dans `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./externalsecret.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
configMapGenerator:
  - name: recyclarr-configmap
    files:
      - config/recyclarr.yml
      - config/settings.yml
generatorOptions:
  disableNameSuffixHash: true
  annotations:
    kustomize.toolkit.fluxcd.io/substitute: disabled
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/recyclarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/recyclarr/app/kustomization.yaml
git commit -m "feat(downloads/recyclarr): add CiliumNetworkPolicy"
```

---

### Task 10 : Validation post-déploiement

- [ ] **Vérifier que les policies sont bien appliquées**

```bash
kubectl get ciliumnetworkpolicy -n downloads
```

Résultat attendu : 9 policies listées (radarr, sonarr, prowlarr, qbittorrent, sabnzbd, bazarr, readarr, lidarr, recyclarr)

- [ ] **Vérifier qu'aucune policy n'est en erreur**

```bash
kubectl describe ciliumnetworkpolicy -n downloads | grep -E "Name:|Events:"
```

- [ ] **Tester la connectivité UI via le gateway**

Ouvrir chaque app dans le browser via son URL interne et vérifier qu'elle charge correctement.

- [ ] **Vérifier les logs Cilium si une app ne répond plus**

```bash
# Identifier le node où tourne le pod
kubectl get pod -n downloads -o wide

# Vérifier les drops Cilium sur ce node
kubectl exec -n kube-system -it ds/cilium -- cilium monitor --type drop 2>/dev/null | head -50
```

- [ ] **Vérifier que Recyclarr se synchronise correctement**

```bash
# Forcer une exécution du CronJob
kubectl create job -n downloads --from=cronjob/recyclarr recyclarr-test-$(date +%s)

# Suivre les logs
kubectl logs -n downloads -l app.kubernetes.io/name=recyclarr --tail=50
```

Résultat attendu : logs montrant la synchro Sonarr/Radarr sans erreur de connexion.
