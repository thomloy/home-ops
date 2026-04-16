# CiliumNetworkPolicy — infrastructure (phase 5A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter des CiliumNetworkPolicies aux pods infrastructure à besoins réseau clairs : nut-shutdown, kopia, onepassword.

**Architecture:** Une policy par pod. Les opérateurs (ESO, cert-manager, CNPG, etc.) restent sans policy (unrestricted). nut-shutdown utilise `app: nut-shutdown` comme selector (Deployment custom, pas bjw-s).

**Tech Stack:** Cilium CNI, CiliumNetworkPolicy v2, Kustomize, Flux CD

**Spec:** `docs/superpowers/specs/2026-04-16-cilium-network-policies-infra-design.md`

---

### Task 1 : nut-shutdown (system-upgrade)

**Fichiers :**
- Créer : `kubernetes/apps/system-upgrade/nut-shutdown/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/system-upgrade/nut-shutdown/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

Note : `nut-shutdown` utilise `app: nut-shutdown` comme label (Deployment custom, pas bjw-s app-template). Les IPs des nodes Talos (192.168.42.41-43) sont dans l'entité `cluster` de Cilium → règle `toCIDR` nécessaire pour le port 50000. Le NAS et internet sont couverts par `toEntities: world`.

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: nut-shutdown
spec:
  endpointSelector:
    matchLabels:
      app: nut-shutdown
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
    - toCIDR:
        - 192.168.42.41/32
        - 192.168.42.42/32
        - 192.168.42.43/32
      toPorts:
        - ports:
            - port: "50000"
              protocol: TCP
    - toEntities:
        - world
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/system-upgrade/nut-shutdown/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/system-upgrade/nut-shutdown/app/kustomization.yaml
git commit -m "feat(system-upgrade/nut-shutdown): add CiliumNetworkPolicy"
```

---

### Task 2 : kopia (volsync-system, port 3000)

**Fichiers :**
- Créer : `kubernetes/apps/volsync-system/kopia/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/volsync-system/kopia/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: kopia
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: kopia
      app.kubernetes.io/instance: kopia
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: network
            gateway.networking.k8s.io/gateway-name: envoy-internal
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
    - toEntities:
        - world
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/volsync-system/kopia/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/volsync-system/kopia/app/kustomization.yaml
git commit -m "feat(volsync-system/kopia): add CiliumNetworkPolicy"
```

---

### Task 3 : onepassword (external-secrets, port 8080)

**Fichiers :**
- Créer : `kubernetes/apps/external-secrets/onepassword/app/ciliumnetworkpolicy.yaml`
- Modifier : `kubernetes/apps/external-secrets/onepassword/app/kustomization.yaml`

- [ ] **Créer `ciliumnetworkpolicy.yaml`**

Note : Le pod a deux containers (`api` + `sync`) qui communiquent via localhost — pas de règle réseau pour ça. Seul le port 8080 (`api`) est exposé. L'ESO controller (mêmes namespace, `app.kubernetes.io/name: external-secrets`) appelle ce port.

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/cilium.io/ciliumnetworkpolicy_v2.json
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: onepassword
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: onepassword
      app.kubernetes.io/instance: onepassword
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: external-secrets
            app.kubernetes.io/name: external-secrets
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
```

- [ ] **Mettre à jour `kustomization.yaml`** (lire d'abord, puis ajouter `./ciliumnetworkpolicy.yaml`)

- [ ] **Commit**

```bash
git add kubernetes/apps/external-secrets/onepassword/app/ciliumnetworkpolicy.yaml \
        kubernetes/apps/external-secrets/onepassword/app/kustomization.yaml
git commit -m "feat(external-secrets/onepassword): add CiliumNetworkPolicy"
```
