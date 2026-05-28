# Dynacat Improvements — Design

**Date** : 2026-05-28
**Scope** : `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml` (sole file modified)
**Trigger** : screenshot of stats page revealed 3 broken widgets, monolithic services block hard to scan, low contrast on the painting background, plus user wants 4 operator-focused widgets

## 1. Purpose

Improve the Dynacat dashboard along 4 axes :
1. **Fix 3 broken widgets** : Gatus 404, "Nouvelles Versions" ERROR, "PRs Renovate" placeholder
2. **Refactor the monolithic "Tous les services" monitor block** into 4 named categories (Infra / Media / Downloads / Selfhosted)
3. **Improve readability** with frosted-glass cards (backdrop-blur) over the painting background, applied site-wide
4. **Add 4 new operator-focused widgets** : Renovate PR list (replaces #1), K8s pod issues, Gatus events feed, recent commits on `home-ops`

All changes live in a single ConfigMap. No HelmRelease changes, no new Secret keys (GITHUB_TOKEN already injected). Single PR.

## 2. Scope

**In scope**
- Configmap edits to `data.dynacat.yml` (page `stats` widget reshuffling, 3 widget fixes, 4 new widgets)
- Configmap edits to `data.custom.css` (one block adding frosted-glass to `.widget`)

**Out of scope**
- Other pages (`home`, `media`, `games`) keep their layout; the CSS frosted-glass applies site-wide but no layout edits
- New container images, new ExternalSecret keys, new ClusterSecretStore entries
- Deploying additional infra (e.g., LibreSpeed for speedtest, iCal calendar source)
- Renovate config or any change outside the dynacat directory

## 3. Architecture (config-only delta)

Single file modified : `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`. Two data keys :

| Key | Edit type |
|-----|-----------|
| `dynacat.yml` | Replace one `monitor` widget with a `group` of 4 monitors; fix 1 monitor URL (Gatus); fix 1 `releases` widget; replace 1 placeholder `custom-api` (PRs Renovate); add 3 new `custom-api` widgets |
| `custom.css` | Append a single `.widget` selector rule |

## 4. Fix #1 — Gatus probe URL

**Where** : in the `monitor` widget of page `stats` (line ~630 of configmap), the entry for Gatus currently uses `url: https://gatus.${SECRET_DOMAIN}` which returns HTTP 404 because Gatus' root path isn't an HTML page in the new Gatus version.

**Fix** : change URL to `https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses`. That endpoint returns JSON with HTTP 200; the `monitor` widget only checks status code (not content), so it'll show ✅.

## 5. Fix #2 — Releases widget

**Where** : `releases` widget on page `stats` (line ~711), currently displays "ERROR / failed to retrieve any content".

**Diagnosis to perform at implementation time** : `kubectl -n selfhosted logs deploy/dynacat --tail=200 | grep -i releases` to see the actual error. Likely causes :
- Repo with no releases at all (e.g., `thomloy/home-ops` which doesn't publish GitHub Releases)
- Repo without proper token scope
- Missing `repositories:` field

**Fix recipe** : ensure config matches Dynacat schema :

```yaml
- type: releases
  title: Nouvelles versions
  token: $${GITHUB_TOKEN}
  show-source-icon: true
  limit: 5
  repositories:
    - flux-iac/flux-operator
    - external-secrets/external-secrets
    - cilium/cilium
    - rook/rook
    - prometheus-operator/prometheus-operator
```

Pick repos that *actually publish releases*. Avoid `thomloy/home-ops` (no releases). Adjust the list at implementation time based on user's actual interests visible in current widget config.

## 6. Refactor #1 — Services block into 4 groups

**Where** : the `monitor` widget on page `stats` listing all 17 services (line ~630).

**Replace** with a `group` widget containing 4 `monitor` children :

```yaml
- type: group
  widgets:
    - type: monitor
      title: Infra
      sites:
        - { title: Grafana,    url: https://grafana.${SECRET_DOMAIN},    icon: di:grafana }
        - { title: Prometheus, url: https://prometheus.${SECRET_DOMAIN}/-/healthy, icon: di:prometheus }
        - { title: Gatus,      url: https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses, icon: di:gatus }
        - { title: TrueNAS,    url: http://${NAS_IP},                    icon: di:truenas }
    - type: monitor
      title: Media
      sites:
        - { title: Emby,            url: https://emby.${SECRET_DOMAIN},            icon: di:emby }
        - { title: Audiobookshelf,  url: https://audiobookshelf.${SECRET_DOMAIN},  icon: di:audiobookshelf }
    - type: monitor
      title: Downloads
      sites:
        - { title: Radarr,      url: https://radarr.${SECRET_DOMAIN},      icon: di:radarr }
        - { title: Sonarr,      url: https://sonarr.${SECRET_DOMAIN},      icon: di:sonarr }
        - { title: Bazarr,      url: https://bazarr.${SECRET_DOMAIN},      icon: di:bazarr }
        - { title: Prowlarr,    url: https://prowlarr.${SECRET_DOMAIN},    icon: di:prowlarr }
        - { title: Sabnzbd,     url: https://sabnzbd.${SECRET_DOMAIN},     icon: di:sabnzbd }
        - { title: qBittorrent, url: https://qbittorrent.${SECRET_DOMAIN}, icon: di:qbittorrent }
    - type: monitor
      title: Selfhosted
      sites:
        - { title: Paperless,     url: https://paperless.${SECRET_DOMAIN},     icon: di:paperless }
        - { title: Tandoor,       url: https://tandoor.${SECRET_DOMAIN},       icon: di:tandoor }
        - { title: Nextcloud,     url: https://nextcloud.${SECRET_DOMAIN},     icon: di:nextcloud }
        - { title: IT-Tools,      url: https://it-tools.${SECRET_DOMAIN},      icon: di:it-tools }
        - { title: Actual Budget, url: https://budget.${SECRET_DOMAIN},        icon: di:actual-budget }
```

Note : the inline `{ k: v, k: v }` flow form above is shown for brevity in this spec only. **At implementation time, use block style** (each key on its own line, no `{ }` braces) to match the existing file convention.

## 7. CSS — Frosted-glass cards (site-wide)

**Where** : append to `data.custom.css` in the configmap.

```css
/* Frosted glass on every widget — sits over the painting background */
.widget {
  background-color: hsla(28, 20%, 15%, 0.62);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
```

**Rationale** :
- `hsla(28, 20%, 15%, 0.62)` matches the theme background-color (HSL `28 20 15` in Dynacat's `theme.background-color` syntax) at 62% opacity → consistent earthy brown that blends with the existing palette. Text contrast roughly meets WCAG AA on the painting's darker zones; OK on lighter zones with blur.
- `blur(10px) saturate(140%)` is the Apple-style frosted-glass recipe — slight desaturation prevents the background from bleeding distracting hues.
- `border-radius: 12px` softens edges; matches modern dashboard idiom.
- `border: 1px solid rgba(255,255,255,0.06)` is a barely-there hairline that hints at the card boundary even when background blends.

**Tuning fallback** : if contrast is insufficient on light zones of the painting (the top-right grass region), bump alpha 0.62 → 0.78 in a follow-up — one-line change.

## 8. New widget #1 — Renovate PRs (replaces broken placeholder)

**Where** : on page `stats`, col 3, top (replaces the existing broken `custom-api` showing `#0`).

```yaml
- type: custom-api
  title: PRs Renovate
  cache: 5m
  update-interval: 5m
  url: "https://api.github.com/search/issues?q=repo:thomloy/home-ops+type:pr+state:open+author:app/renovate&sort=updated"
  headers:
    Authorization: "Bearer $${GITHUB_TOKEN}"
    Accept: application/vnd.github+json
  template: |
    {{ $items := .JSON.Array "items" }}
    {{ if eq (len $items) 0 }}
      <div style="font-size:.85em;opacity:.5">Aucune PR Renovate ouverte</div>
    {{ else }}
      <div style="display:flex;flex-direction:column;gap:5px">
        {{ range $items }}
          <a href="{{ .HTML "html_url" }}" target="_blank" style="text-decoration:none;color:inherit;padding:5px 8px;background:rgba(0,0,0,.08);border-radius:5px;border-left:3px solid #3b82f6;display:block">
            <div style="font-size:.8em;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">#{{ .Int "number" }} {{ .String "title" }}</div>
            <div style="font-size:.68em;opacity:.55;margin-top:2px">{{ .String "updated_at" | parseTime "rfc3339" | toRelativeTime }}</div>
          </a>
        {{ end }}
      </div>
    {{ end }}
```

Notes :
- Uses Dynacat's `custom-api` JSON template helpers (`.JSON.Array`, `.String`, `.Int`, `.HTML`, `toRelativeTime`)
- The exact template function names need verification against Dynacat 2.3.0 docs — Glance and Dynacat occasionally differ on the helper namespace. If a function isn't available, fall back to simpler `{{ .Result.items.0.title }}` style.

## 9. New widget #2 — K8s pod issues

**Where** : page `stats`, col 3, below releases.

```yaml
- type: custom-api
  title: K8s pod issues
  cache: 30s
  update-interval: 30s
  url: |
    http://kube-prometheus-stack-prometheus.observability.svc.cluster.local:9090/api/v1/query?query=
    (kube_pod_container_status_restarts_total > 5) 
    or (kube_pod_status_phase{phase=~"Pending|Failed|Unknown"} == 1) 
    or (kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} == 1)
  template: |
    {{ $results := .JSON.Array "data.result" }}
    {{ if eq (len $results) 0 }}
      <div style="font-size:.85em;opacity:.5">✅ Tous les pods sains</div>
    {{ else }}
      <div style="display:flex;flex-direction:column;gap:4px">
        {{ range $results }}
          {{ $ns := .String "metric.namespace" }}{{ $pod := .String "metric.pod" }}{{ $reason := .String "metric.reason" }}
          <div style="font-size:.78em;padding:4px 8px;background:rgba(239,68,68,.12);border-left:3px solid #ef4444;border-radius:4px">
            <div style="font-weight:600">{{ $ns }} / {{ $pod }}</div>
            {{ if $reason }}<div style="font-size:.85em;opacity:.7">{{ $reason }}</div>{{ end }}
          </div>
        {{ end }}
      </div>
    {{ end }}
```

Notes :
- URL is multi-line for readability; YAML `|` block scalar preserves newlines, which the HTTP client may not handle. Single-line version is the implementation fallback if Dynacat doesn't strip whitespace.
- The PromQL query coalesces 3 unhealthy states via `or`. Empty result → green checkmark.
- Cilium NetworkPolicy : dynacat already reaches Prometheus via the Infra widget (existing `custom-api` URL points at the same service). No new CNP rule needed.

## 10. New widget #3 — Gatus events (raw alerts)

**Where** : page `stats`, col 3, below K8s issues.

```yaml
- type: custom-api
  title: Alertes récentes (Gatus)
  cache: 1m
  update-interval: 1m
  url: "https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses?page=1"
  template: |
    {{ $endpoints := .JSON.Array "" }}
    {{ $events := slice }}
    {{ range $endpoints }}
      {{ $name := .String "name" }}
      {{ $results := .JSON.Array "results" }}
      {{ range $results }}
        {{ if not (.Bool "success") }}
          {{ $events = append $events (dict "name" $name "timestamp" (.String "timestamp")) }}
        {{ end }}
      {{ end }}
    {{ end }}
    {{ if eq (len $events) 0 }}
      <div style="font-size:.85em;opacity:.5">✅ Aucune alerte récente</div>
    {{ else }}
      <div style="display:flex;flex-direction:column;gap:4px">
        {{ range $events | sortDesc "timestamp" | limit 5 }}
          <div style="font-size:.78em;padding:4px 8px;background:rgba(245,158,11,.12);border-left:3px solid #f59e0b;border-radius:4px">
            <div style="font-weight:600">{{ .name }}</div>
            <div style="font-size:.85em;opacity:.7">{{ .timestamp | parseTime "rfc3339" | toRelativeTime }}</div>
          </div>
        {{ end }}
      </div>
    {{ end }}
```

Notes :
- Gatus' `/api/v1/endpoints/statuses` returns an array of endpoints, each with a `results[]` history. We flatten + filter for failures.
- Template uses higher-level helpers (`slice`, `append`, `dict`, `sortDesc`, `limit`) which may not exist in Dynacat 2.3.0. **Fallback at implementation** : if template helpers are insufficient, simplify by querying `/api/v1/endpoints/<group>/<name>/events` for specific critical endpoints, or skip and replace with a `monitor` widget pointing at Gatus' admin UI for now.
- This widget requires `dynacat` to have egress to `gatus.${SECRET_DOMAIN}` — the route is on envoy-internal, accessible via cluster DNS or external URL. Existing config (which already calls other `${SECRET_DOMAIN}` URLs) confirms egress works.

## 11. New widget #4 — Recent commits home-ops

**Where** : page `stats`, col 3, between Renovate PRs and Releases.

```yaml
- type: custom-api
  title: Commits récents home-ops
  cache: 5m
  update-interval: 5m
  url: "https://api.github.com/repos/thomloy/home-ops/commits?per_page=5"
  headers:
    Authorization: "Bearer $${GITHUB_TOKEN}"
    Accept: application/vnd.github+json
  template: |
    {{ $commits := .JSON.Array "" }}
    {{ if eq (len $commits) 0 }}
      <div style="font-size:.85em;opacity:.5">Aucun commit récent</div>
    {{ else }}
      <div style="display:flex;flex-direction:column;gap:4px">
        {{ range $commits }}
          {{ $msg := .String "commit.message" }}
          {{ $author := .String "commit.author.name" }}
          {{ $date := .String "commit.author.date" }}
          {{ $url := .String "html_url" }}
          {{ $title := index (split "\n" $msg) 0 }}
          <a href="{{ $url }}" target="_blank" style="text-decoration:none;color:inherit;padding:4px 8px;background:rgba(0,0,0,.06);border-radius:4px;border-left:3px solid #22c55e;display:block">
            <div style="font-size:.78em;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ $title }}</div>
            <div style="font-size:.68em;opacity:.55;margin-top:2px">{{ $author }} · {{ $date | parseTime "rfc3339" | toRelativeTime }}</div>
          </a>
        {{ end }}
      </div>
    {{ end }}
```

## 12. Final col 3 layout on page `stats` (top → bottom)

```
1. PRs Renovate           (new, replaces broken #0 widget)
2. Commits récents        (new)
3. Releases (fixed)       (existing, repaired)
4. K8s pod issues         (new)
5. Alertes Gatus          (new)
6. Liens Rapides          (existing, untouched)
```

6 widgets vertically; Dynacat scrolls per column when content exceeds viewport, so density is fine for an operator page.

## 13. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Template helpers used in widgets 1-4 may not exist in Dynacat 2.3.0 | Spec lists fallback simplifications in each widget's notes. Implementer should validate the helper namespace against `docs/docs/custom-api.md` upstream before commit. |
| Backdrop-filter performance on weaker GPUs | Acceptable — modern Chromium/Firefox handle this fine even on integrated GPUs; the dashboard is opened on operator workstation, not a Raspberry Pi |
| GitHub API rate limit (5000/hour authenticated, GITHUB_TOKEN scope) | Widgets cache 5min → ~12 calls/hour each, well under quota |
| Prometheus query returns malformed JSON for our template | Implementer should curl the URL inside the dynacat pod first to verify shape; adjust template field names accordingly |
| `data.custom.css` already loaded by Dynacat | Verified by the existing `custom-css-file: /assets/custom.css` in theme block; just append the new rule |
| Releases widget can't find any repos with new releases | If still ERROR after fix, drop the widget entirely from spec — the col still has 5 useful widgets |

## 14. Bootstrap order

1. Pre-validate config locally with `docker run panonim/dynacat:2.3.0` against the updated configmap (the same smoke test used for the initial dynacat migration)
2. Single PR, single commit
3. flux-local CI validation
4. Merge
5. Force reconcile : `flux reconcile kustomization dynacat -n selfhosted`
6. Wait for HelmRelease to roll the pod (reloader detects configmap change and triggers restart)
7. Browser test : open `https://home.kryzql.space` (which lands on `home`), click `stats` tab, verify each new widget renders correctly and frosted-glass effect is visible

## 15. Out-of-scope follow-ups (not blockers)

- If template helpers force major rewrites of widgets 1-4, consider migrating to Dynacat's `extension` widget type which loads JS-rendered widgets from external URLs (cleaner separation of complex logic)
- Speedtest widget (deferred — requires deploying LibreSpeed)
- iCal calendar widget (deferred — requires picking a calendar source)
- Custom CSS tweaks for individual widgets if frosted-glass looks weird on specific ones (e.g., the inline-HTML Infra widget might need its background made transparent so the blur shows)
