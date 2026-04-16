# CiliumNetworkPolicy — namespace `default`

**Date:** 2026-04-16
**Scope:** namespace `default` (phase 4)

---

## Contexte

Suite de la phase 3 (media). Le namespace `default` contient 2 apps : Atuin et Tandoor.

Particularités :
- Atuin utilise SQLite local → pas de base de données externe → egress DNS uniquement
- Tandoor a un postgres en sidecar container dans le **même pod** → communication via localhost, aucune règle réseau nécessaire pour postgres
- Tandoor monte du NFS depuis le NAS et permet l'import de recettes depuis des URLs → egress `toEntities: world`
- Glance (selfhosted) contacte Tandoor sur port 80 (déjà prévu dans la policy glance)

---

## Labels réels des pods

| Pod | name | instance | controller |
|-----|------|----------|------------|
| atuin | atuin | atuin | atuin |
| tandoor | tandoor | tandoor | tandoor |

---

## Ports de services

| Service | Port |
|---------|------|
| atuin | 80 |
| tandoor | 80 |

---

## Matrice de communication

| App | Ingress depuis | Egress vers | Internet |
|-----|---------------|-------------|---------|
| atuin (80) | Gateway | DNS | ❌ |
| tandoor (80) | Gateway, Glance | DNS, world (NFS NAS + imports recettes web) | ✅ |

---

## Structure des fichiers

```
kubernetes/apps/default/
├── atuin/app/ciliumnetworkpolicy.yaml    ← nouveau
└── tandoor/app/ciliumnetworkpolicy.yaml  ← nouveau
```

---

## Cas particuliers

### Tandoor — postgres sidecar

Le container `postgres` de Tandoor est dans le même pod que `app` (`POSTGRES_HOST: localhost`). La communication postgres est via localhost — pas de règle réseau nécessaire dans la CiliumNetworkPolicy.

---

## Matrice de flux réseau complète

| Source | Destination | Port | Proto | Justification |
|--------|-------------|------|-------|---------------|
| **default/atuin** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **default/tandoor** | kube-system/kube-dns | 53 | UDP+TCP | DNS |
| **default/tandoor** | internet (world) | * | TCP | NFS NAS + imports recettes |
| network/envoy-internal | default/atuin | 80 | TCP | UI / API sync |
| network/envoy-internal | default/tandoor | 80 | TCP | UI |
| selfhosted/glance | default/tandoor | 80 | TCP | Widget Glance |

---

## Rollout progressif

1. **Phase 1 (done)** : namespace `downloads`
2. **Phase 2 (done)** : namespace `selfhosted`
3. **Phase 3 (done)** : namespace `media`
4. **Phase 4 (ce spec)** : namespace `default`
5. **Phase 5** : namespaces infrastructure
