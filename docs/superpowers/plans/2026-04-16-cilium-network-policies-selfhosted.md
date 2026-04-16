# CiliumNetworkPolicy — namespace `selfhosted` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter des CiliumNetworkPolicies à tout le namespace `selfhosted` (default-deny implicite) et mettre à jour les policies `downloads` pour autoriser Glance.

**Architecture:** Une policy par app (ou groupe de sidecars) dans `{app}/app/ciliumnetworkpolicy.yaml`. Les CNPG pods ne sont pas couverts (trafic libre). La policy Paperless existante est remplacée par une version complète avec egress.

**Tech Stack:** Cilium CNI, CiliumNetworkPolicy v2, Kustomize, Flux CD

**Spec:** `docs/superpowers/specs/2026-04-16-cilium-network-policies-selfhosted-design.md`

---

### Task 1 : Mettre à jour les policies `downloads` pour Glance

Glance (selfhosted) contacte 6 apps dans downloads. Leurs policies actuelles n'autorisent pas cet ingress.

**Fichiers :**
- Modifier : `kubernetes/apps/downloads/radarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/sonarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/bazarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/prowlarr/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/sabnzbd/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/downloads/qbittorrent/app/ciliumnetworkpolicy.yaml`

- [ ] **Ajouter Glance dans l'ingress de radarr**

Dans `kubernetes/apps/downloads/radarr/app/ciliumnetworkpolicy.yaml`, ajouter dans le bloc `fromEndpoints` de l'ingress :

```yaml
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
```

Résultat attendu — section ingress complète :

```yaml
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
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
      toPorts:
        - ports:
            - port: "7878"
              protocol: TCP
```

- [ ] **Ajouter Glance dans l'ingress de sonarr** (port 8989)

```yaml
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
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
      toPorts:
        - ports:
            - port: "8989"
              protocol: TCP
```

- [ ] **Ajouter Glance dans l'ingress de bazarr** (port 80)

```yaml
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
```

- [ ] **Ajouter Glance dans l'ingress de prowlarr** (port 80)

```yaml
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
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
```

- [ ] **Ajouter Glance dans l'ingress de sabnzbd** (port 80)

```yaml
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
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
```

- [ ] **Ajouter Glance dans l'ingress de qbittorrent** (port 8080, ingress rule 1 uniquement)

```yaml
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
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: glance
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
```

- [ ] **Commit**

```bash
git add kubernetes/apps/downloads/radarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/sonarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/bazarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/prowlarr/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/sabnzbd/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/downloads/qbittorrent/app/ciliumnetworkpolicy.yaml
git commit -m "feat(downloads): allow ingress from glance in network policies"
```

---

### Task 2 : actual-budget (port 5006)

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/actual-budget/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/actual-budget/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: actual-budget
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: actual-budget
      app.kubernetes.io/instance: actual-budget
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
            - port: "5006"
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
```

- [ ] **Mettre à jour `kustomization.yaml`** (ajouter `./ciliumnetworkpolicy.yaml` après `./volsync.yaml`)

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./volsync.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/actual-budget/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/actual-budget/app/kustomization.yaml
git commit -m "feat(selfhosted/actual-budget): add CiliumNetworkPolicy"
```

---

### Task 3 : bentopdf (port 8080)

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/bentopdf/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/bentopdf/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: bentopdf
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: bentopdf
      app.kubernetes.io/instance: bentopdf
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "8080"
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
```

- [ ] **Mettre à jour `kustomization.yaml`**

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./helmrelease.yaml
  - ./ocirepository.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/bentopdf/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/bentopdf/app/kustomization.yaml
git commit -m "feat(selfhosted/bentopdf): add CiliumNetworkPolicy"
```

---

### Task 4 : it-tools (port 8080)

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/it-tools/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/it-tools/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: it-tools
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: it-tools
      app.kubernetes.io/instance: it-tools
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
            - port: "8080"
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
```

- [ ] **Mettre à jour `kustomization.yaml`**

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
git add kubernetes/apps/selfhosted/it-tools/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/it-tools/app/kustomization.yaml
git commit -m "feat(selfhosted/it-tools): add CiliumNetworkPolicy"
```

---

### Task 5 : glance (port 8080 — egress multi-namespace)

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/glance/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/glance/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: glance
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: glance
      app.kubernetes.io/instance: glance
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "8080"
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
            k8s:io.kubernetes.pod.namespace: observability
            app.kubernetes.io/name: prometheus
      toPorts:
        - ports:
            - port: "9090"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: observability
            app: grafana
      toPorts:
        - ports:
            - port: "3000"
              protocol: TCP
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
            k8s:io.kubernetes.pod.namespace: media
            app.kubernetes.io/name: audiobookshelf
      toPorts:
        - ports:
            - port: "80"
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
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: bazarr
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: prowlarr
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: sabnzbd
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: downloads
            app.kubernetes.io/name: qbittorrent
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: paperless
            app.kubernetes.io/controller: paperless
      toPorts:
        - ports:
            - port: "8000"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: it-tools
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: actual-budget
      toPorts:
        - ports:
            - port: "5006"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: nextcloud
            app.kubernetes.io/controller: nextcloud
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: default
            app.kubernetes.io/name: tandoor
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
```

- [ ] **Mettre à jour `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./configmap.yaml
  - ./configmap-bg.yaml
  - ./ocirepository.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/glance/app/kustomization.yaml
git commit -m "feat(selfhosted/glance): add CiliumNetworkPolicy"
```

---

### Task 6 : immich (server + machine-learning + valkey)

Un seul fichier couvre les 3 composants Immich.

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/immich/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/immich/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: immich-server
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: server
      app.kubernetes.io/instance: immich
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
      toPorts:
        - ports:
            - port: "2283"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: observability
            app.kubernetes.io/name: prometheus
      toPorts:
        - ports:
            - port: "8081"
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
            k8s:io.kubernetes.pod.namespace: selfhosted
            cnpg.io/cluster: immich-postgres
      toPorts:
        - ports:
            - port: "5432"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: valkey
            app.kubernetes.io/instance: immich
      toPorts:
        - ports:
            - port: "6379"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: machine-learning
            app.kubernetes.io/instance: immich
      toPorts:
        - ports:
            - port: "3003"
              protocol: TCP
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: immich-machine-learning
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: machine-learning
      app.kubernetes.io/instance: immich
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: server
            app.kubernetes.io/instance: immich
      toPorts:
        - ports:
            - port: "3003"
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
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: immich-valkey
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: valkey
      app.kubernetes.io/instance: immich
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: server
            app.kubernetes.io/instance: immich
      toPorts:
        - ports:
            - port: "6379"
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
```

- [ ] **Mettre à jour `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./cluster.yaml
  - ./cnpg-backup.yaml
  - ./pv.yaml
  - ./helmrelease.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/immich/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/immich/app/kustomization.yaml
git commit -m "feat(selfhosted/immich): add CiliumNetworkPolicy"
```

---

### Task 7 : nextcloud (app + valkey)

Un seul fichier couvre nextcloud-app et nextcloud-valkey.

**Fichiers :**
- Créer : `kubernetes/apps/selfhosted/nextcloud/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/selfhosted/nextcloud/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: nextcloud
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: nextcloud
      app.kubernetes.io/instance: nextcloud
      app.kubernetes.io/controller: nextcloud
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
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            cnpg.io/cluster: nextcloud-postgres
      toPorts:
        - ports:
            - port: "5432"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: nextcloud
            app.kubernetes.io/controller: valkey
      toPorts:
        - ports:
            - port: "6379"
              protocol: TCP
    - toEntities:
        - world
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: nextcloud-valkey
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: nextcloud
      app.kubernetes.io/instance: nextcloud
      app.kubernetes.io/controller: valkey
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: nextcloud
            app.kubernetes.io/controller: nextcloud
      toPorts:
        - ports:
            - port: "6379"
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
```

- [ ] **Mettre à jour `kustomization.yaml`**

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./ocirepository.yaml
  - ./cluster.yaml
  - ./externalsecret.yaml
  - ./pvc.yaml
  - ./helmrelease.yaml
  - ./cnpg-backup.yaml
  - ./volsync.yaml
  - ./ciliumnetworkpolicy.yaml
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/nextcloud/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/selfhosted/nextcloud/app/kustomization.yaml
git commit -m "feat(selfhosted/nextcloud): add CiliumNetworkPolicy"
```

---

### Task 8 : paperless (remplacer policy existante + sidecars)

La policy existante n'a que des règles ingress. Elle est remplacée par une version complète incluant egress + policies pour redis, tika, gotenberg.

**Fichiers :**
- Remplacer : `kubernetes/apps/selfhosted/paperless/app/ciliumnetworkpolicy.yaml`
- `kustomization.yaml` référence déjà la policy — pas de modification nécessaire

- [ ] **Remplacer `ciliumnetworkpolicy.yaml`** (écraser le fichier existant)

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: paperless
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: paperless
      app.kubernetes.io/instance: paperless
      app.kubernetes.io/controller: paperless
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
            - port: "8000"
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
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: paperless
            app.kubernetes.io/controller: redis
      toPorts:
        - ports:
            - port: "6379"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: paperless
            app.kubernetes.io/controller: tika
      toPorts:
        - ports:
            - port: "9998"
              protocol: TCP
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: paperless
            app.kubernetes.io/controller: gotenberg
      toPorts:
        - ports:
            - port: "3000"
              protocol: TCP
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: paperless-redis
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: paperless
      app.kubernetes.io/instance: paperless
      app.kubernetes.io/controller: redis
  ingress:
    - fromEndpoints:
        - matchLabels:
            app.kubernetes.io/name: paperless
            app.kubernetes.io/instance: paperless
            app.kubernetes.io/controller: paperless
      toPorts:
        - ports:
            - port: "6379"
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
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: paperless-tika
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: paperless
      app.kubernetes.io/instance: paperless
      app.kubernetes.io/controller: tika
  ingress:
    - fromEndpoints:
        - matchLabels:
            app.kubernetes.io/name: paperless
            app.kubernetes.io/instance: paperless
            app.kubernetes.io/controller: paperless
      toPorts:
        - ports:
            - port: "9998"
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
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: paperless-gotenberg
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: paperless
      app.kubernetes.io/instance: paperless
      app.kubernetes.io/controller: gotenberg
  ingress:
    - fromEndpoints:
        - matchLabels:
            app.kubernetes.io/name: paperless
            app.kubernetes.io/instance: paperless
            app.kubernetes.io/controller: paperless
      toPorts:
        - ports:
            - port: "3000"
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
```

- [ ] **Commit**

```bash
git add kubernetes/apps/selfhosted/paperless/app/ciliumnetworkpolicy.yaml
git commit -m "feat(selfhosted/paperless): complete CiliumNetworkPolicy with egress + sidecars"
```

---

### Task 9 : Validation post-déploiement

- [ ] **Vérifier les policies selfhosted**

```bash
kubectl get ciliumnetworkpolicy -n selfhosted
```

Résultat attendu : actual-budget, bentopdf, glance, immich-server, immich-machine-learning, immich-valkey, it-tools, nextcloud, nextcloud-valkey, paperless, paperless-redis, paperless-tika, paperless-gotenberg

- [ ] **Vérifier les policies downloads mises à jour**

```bash
kubectl get ciliumnetworkpolicy -n downloads
kubectl describe ciliumnetworkpolicy radarr -n downloads | grep -A5 "glance"
```

- [ ] **Tester Glance**

Ouvrir Glance dans le navigateur et vérifier que tous les widgets chargent (radarr, sonarr, emby, etc.).

- [ ] **Tester Immich**

Ouvrir Immich, vérifier que les photos s'affichent et que la reconnaissance faciale/ML fonctionne.

- [ ] **Tester Nextcloud**

Ouvrir Nextcloud, vérifier que les fichiers sont accessibles.

- [ ] **Tester Paperless**

Ouvrir Paperless, vérifier que l'OCR fonctionne (soumettre un document).

- [ ] **Surveiller les drops Cilium si une app ne répond plus**

```bash
kubectl exec -n kube-system -it ds/cilium -- cilium monitor --type drop 2>/dev/null | head -50
```
