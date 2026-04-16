# CiliumNetworkPolicy — namespaces infrastructure (phase 5A)

**Date:** 2026-04-16
**Scope:** 3 pods dans 3 namespaces infrastructure

---

## Contexte

Phase 5A couvre uniquement les pods dont les besoins réseau sont clairs et vérifiables sans accès live au cluster. Les opérateurs (cert-manager controller, ESO controller, CNPG, openebs, volsync controller, tuppr, actions-runner) restent sans policy (unrestricted) car ils nécessitent un accès cluster-wide difficile à circonscrire correctement.

---

## Pods couverts

| Namespace | Pod | Labels | Port |
|-----------|-----|--------|------|
| `system-upgrade` | nut-shutdown | `app: nut-shutdown` (Deployment custom, pas bjw-s) | aucun (pas de service) |
| `volsync-system` | kopia | `app.kubernetes.io/name: kopia, instance: kopia` | 3000 |
| `external-secrets` | onepassword | `app.kubernetes.io/name: onepassword, instance: onepassword` | 8080 |

---

## Matrice de communication

| Pod | Ingress depuis | Egress vers | Internet |
|-----|---------------|-------------|---------|
| nut-shutdown | — (pas de service) | DNS, NAS:3493 (NUT), nodes Talos:50000, internet (talosctl GitHub) | ✅ |
| kopia (3000) | Gateway | DNS, world (NFS NAS) | ❌ (filesystem local via NFS) |
| onepassword (8080) | external-secrets/external-secrets | DNS, world (1Password SaaS API) | ✅ |

---

## Cas particuliers

### nut-shutdown — labels non-standard

Le Deployment `nut-shutdown` n'utilise pas bjw-s app-template. Le label selector est `app: nut-shutdown`. L'endpointSelector de la policy doit utiliser `app: nut-shutdown` (pas `app.kubernetes.io/name`).

### nut-shutdown — entités Cilium pour les nodes Talos

Les IPs des nodes (192.168.42.41-43) sont dans l'entité `cluster` de Cilium (pas `world`). Pour autoriser le trafic vers le port Talos API (50000), une règle `toCIDR` explicite est nécessaire. Le trafic vers le NAS et internet est couvert par `toEntities: world`.

### kopia — stockage NFS, pas S3

Kopia utilise un stockage filesystem monté via NFS depuis le NAS. Il n'accède pas à S3. `toEntities: world` couvre le trafic NFS (le NAS est externe au cluster). Pas d'accès internet nécessaire au-delà du NFS.

### onepassword — deux containers, même pod

Le pod onepassword contient `api` (port 8080) et `sync` (port 8081). Ils communiquent via `localhost:11220-11221` — pas de règle réseau nécessaire. Seul le port 8080 est exposé en service. L'ESO controller appelle ce port pour récupérer les secrets.

---

## Structure des fichiers

```
kubernetes/apps/system-upgrade/nut-shutdown/app/ciliumnetworkpolicy.yaml  ← nouveau
kubernetes/apps/volsync-system/kopia/app/ciliumnetworkpolicy.yaml         ← nouveau
kubernetes/apps/external-secrets/onepassword/app/ciliumnetworkpolicy.yaml ← nouveau
```

---

## Matrice de flux réseau complète

| Source | Destination | Port | Proto | Justification |
|--------|-------------|------|-------|---------------|
| **system-upgrade/nut-shutdown** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **system-upgrade/nut-shutdown** | world (NAS) | 3493 | TCP | Protocole NUT (UPS status) |
| **system-upgrade/nut-shutdown** | 192.168.42.41/32 | 50000 | TCP | Talos API node01 |
| **system-upgrade/nut-shutdown** | 192.168.42.42/32 | 50000 | TCP | Talos API node02 |
| **system-upgrade/nut-shutdown** | 192.168.42.43/32 | 50000 | TCP | Talos API node03 |
| **system-upgrade/nut-shutdown** | internet (world) | * | TCP | Download talosctl depuis GitHub |
| **volsync-system/kopia** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **volsync-system/kopia** | world (NAS) | * | TCP | NFS mount repository |
| **external-secrets/onepassword** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **external-secrets/onepassword** | internet (world) | * | TCP | 1Password SaaS API |
| network/envoy-internal | volsync-system/kopia | 3000 | TCP | UI |
| external-secrets/external-secrets | external-secrets/onepassword | 8080 | TCP | Récupération secrets |
