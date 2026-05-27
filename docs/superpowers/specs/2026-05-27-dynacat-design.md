# Dynacat — Design (Glance replacement)

**Date** : 2026-05-27
**Namespace** : `selfhosted`
**Hostname** : `home.${SECRET_DOMAIN}` (envoy-internal, replaces `glance.${SECRET_DOMAIN}`)
**Trigger** : need automatic widget refresh without manual F5

## 1. Purpose

Replace the existing Glance dashboard with [Dynacat](https://github.com/Panonim/dynacat) (a Glance fork by Panonim) for two reasons :
1. Built-in SSE-powered auto-refresh of widgets (Glance requires manual reload)
2. Move the hostname from `glance.kryzql.space` to the more semantic `home.kryzql.space`

Dynacat is config-compatible with Glance (same widget types, same `glance.yml` schema as superset) and ships the same `app-template` deployment shape, so the migration is a controlled rename + image swap + one new per-widget field.

## 2. Scope

**In scope**
- Rename `kubernetes/apps/selfhosted/glance/` → `kubernetes/apps/selfhosted/dynacat/` (full app rename: directory, manifest names, labels, secret name, configmap names)
- Image swap `glanceapp/glance:v0.8.4` → `panonim/dynacat:2.3.0`
- Hostname switch `glance.${SECRET_DOMAIN}` → `home.${SECRET_DOMAIN}`
- Mount path `/app/config/glance.yml` → `/app/config/dynacat.yml` (Dockerfile ENTRYPOINT default)
- Add `update-interval: 30s` on the Infra Custom API widget to align client refresh with the existing 30s server cache
- Update `kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml` to authorize the new `dynacat` label (additive first, glance entry removed after rename)
- Update `kubernetes/apps/selfhosted/kustomization.yaml` index entry

**Out of scope**
- Restructuring the existing widget catalog (pages, columns, sources stay 1:1)
- Renovate group changes — `panonim/dynacat` is picked up by the default docker datasource
- Old hostname redirect / dual hosting (explicit choice: let `glance.${SECRET_DOMAIN}` disappear when ExternalDNS GCs the record)
- Dashboards Grafana / observability stack

## 3. Architecture (delta vs Glance)

Same HelmRelease shape (bjw-s `app-template` 4.6.2, single controller, single container, two ConfigMaps for config + bg, one Service, one HTTPRoute, one CiliumNetworkPolicy, one ExternalSecret). Only differences :

| Layer | Glance | Dynacat |
|-------|--------|---------|
| Image | `glanceapp/glance:v0.8.4` | `panonim/dynacat:2.3.0` |
| Config path | `/app/config/glance.yml` | `/app/config/dynacat.yml` |
| Auto-refresh | client must reload page | SSE push from server, per-widget `update-interval` |
| Default custom-api refresh | server cache only | server cache + client refresh every 1m (configurable per widget) |

### 3.1 Auto-refresh strategy

Dynacat's default per-widget intervals are reasonable (Monitor 2m, Reddit 25m, Server Stats 15s, Custom API 1m). The configmap stays untouched **except** for the Infra widget (type `custom-api`, currently `cache: 30s`), where we add `update-interval: 30s` to keep client display in lockstep with server cache.

### 3.2 Custom CSS

Glance config currently uses `theme.custom-css-file: /assets/custom.css`. Verify in `docs/docs/configuration.md` of the dynacat repo that the field name didn't change in the fork. If it did, rename at implementation time; otherwise no-op.

## 4. File layout (post-rename)

```
kubernetes/apps/selfhosted/dynacat/
├── ks.yaml                  # Kustomization (renamed from glance)
└── app/
    ├── ciliumnetworkpolicy.yaml
    ├── configmap-bg.yaml    # name: dynacat-bg
    ├── configmap.yaml       # name: dynacat-config, data key: dynacat.yml
    ├── externalsecret.yaml  # target: dynacat-secret
    ├── helmrelease.yaml
    ├── kustomization.yaml
    └── ocirepository.yaml   # name: dynacat, unchanged chart
```

And modify :
- `kubernetes/apps/selfhosted/kustomization.yaml` — `./glance/ks.yaml` → `./dynacat/ks.yaml`
- `kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml` — replace `glance` matchLabels entry by `dynacat`

## 5. String replacements inside the renamed dir

Apply each of these globally inside `kubernetes/apps/selfhosted/dynacat/` after `git mv`:

| Find | Replace |
|------|---------|
| `name: glance` (metadata, refs) | `name: dynacat` |
| `app.kubernetes.io/name: glance` | `app.kubernetes.io/name: dynacat` |
| `app.kubernetes.io/instance: glance` | `app.kubernetes.io/instance: dynacat` |
| `glance-secret` | `dynacat-secret` |
| `glance-config` | `dynacat-config` |
| `glance-bg` | `dynacat-bg` |
| `glance.yml` | `dynacat.yml` |
| `glance.${SECRET_DOMAIN}` | `home.${SECRET_DOMAIN}` |
| `glanceapp/glance` | `panonim/dynacat` |
| `tag: v0.8.4` | `tag: "2.3.0"` |

Do NOT touch :
- `github-status-token-secret` — separate secret used by the GITHUB_TOKEN secretKeyRef, unrelated to glance
- `flux` 1Password item references in externalsecret — those are external 1P items, not cluster names
- The widget catalog YAML inside the configmap (Prometheus query template, Tandoor monitor entry, Media/Arr blocks) — except the single targeted edit below

Targeted manual edit (not a rename) inside the configmap's `data.dynacat.yml` body: add `update-interval: 30s` to the Infra Custom API widget block (sibling of the existing `cache: 30s` line). Single line addition, see §3.1.

## 6. CNP cross-namespace update (tandoor)

Tandoor's existing CNP allows ingress from `selfhosted/glance` for the recipe widget. Migration is **two-step** to avoid a permission gap during pod rollover :

**Phase 1 commit** : add `dynacat` matchLabels to the same ingress rule. Keep `glance` in place.
```yaml
- matchLabels: { k8s:io.kubernetes.pod.namespace: selfhosted, app.kubernetes.io/name: glance }
- matchLabels: { k8s:io.kubernetes.pod.namespace: selfhosted, app.kubernetes.io/name: dynacat }
- matchLabels: { k8s:io.kubernetes.pod.namespace: selfhosted, app.kubernetes.io/name: sparkyfitness }
```

**Phase 2 commit** : in the same PR but landed after Phase 1 in commit order, remove the orphan `glance` entry along with the rename. Order matters within the PR — Phase 1 must be the older commit so a partial rollout (rare but possible) still works.

## 7. Risk mitigations (active, not just documented)

| Risk | Mitigation |
|------|-----------|
| Configmap field unsupported by Dynacat | Pre-merge local validation: extract the rendered `dynacat.yml` content, run `docker run --rm -v $PWD/dynacat.yml:/app/config/dynacat.yml panonim/dynacat:2.3.0` for 10s, tail logs for parse errors. If `--check-config` flag exists in dynacat 2.3.0, use it. Fail the merge if dynacat exits non-zero. |
| CNP/pod timing gap | Two-commit phasing inside the PR (Phase 1 additive, Phase 2 rename) — see §6 |
| Rename hygiene (orphan `glance` refs) | Pre-commit grep gate: `grep -r "glance" kubernetes/apps/selfhosted/dynacat/` must return 0 (the directory should have no `glance` substring anywhere). Run as part of the implementation plan's validation step before commit. |
| ESO refreshInterval 12h delays new secret | Explicit force-sync post-merge: `kubectl -n selfhosted annotate externalsecret dynacat force-sync=$(date +%s) --overwrite`. The old `glance-secret` is pruned by Flux when the old Kustomization is removed (creationPolicy: Owner), the new one is created immediately on first reconcile (not subject to refreshInterval). |
| Custom CSS path field renamed in dynacat | Verify `theme.custom-css-file` key against dynacat config docs at implementation time. Rename if changed. |
| Crash loop after merge | Rollback = `git revert <PR-merge-sha>` + push. Flux restores glance identically within ~2min. State loss: zero (configmap-driven, no PV). |
| ExternalDNS not GCing the old glance record | Watch externaldns logs after merge; if record persists beyond 5min, force-restart externaldns-unifi pod. |

## 8. Bootstrap order

1. Pre-validate configmap locally with dynacat docker image (no commit yet)
2. Commit Phase 1 (tandoor CNP additive patch)
3. Commit Phase 2 (rename + image + URL + tandoor CNP cleanup), grep gate passes
4. Open PR, wait for flux-local CI green, merge
5. Force-sync ExternalSecret post-merge
6. Verify pod 1/1 ready, HTTPRoute Accepted, DNS record swapped, browser opens at `https://home.${SECRET_DOMAIN}`
7. Verify cross-namespace : visit the page, observe Tandoor monitor widget loads (proves CNP)
8. Update bookmarks

## 9. Post-merge follow-ups

- Day-1 watch : confirm SSE connection is established (browser DevTools → Network → look for `text/event-stream` connection that stays open)
- Day-7 : if widget refresh feels too aggressive or too lazy, tune `update-interval` on individual widgets
- 30-day reminder : if a `glance.${SECRET_DOMAIN}` record persists in UDM Pro DNS, manual cleanup
