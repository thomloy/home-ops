# Dynacat Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 broken widgets on the Dynacat stats page, refactor the monolithic services monitor into 4 named groups, apply site-wide frosted-glass CSS to all widgets, and add 4 operator-focused widgets (Renovate PR list, recent commits, K8s pod issues, Gatus alerts).

**Architecture:** All changes live in a single ConfigMap (`kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`). Two data keys edited: `dynacat.yml` (widget layout) and `custom.css` (frosted-glass rule). No HelmRelease changes, no new secrets, no new images. Reloader detects the configmap change and rolls the pod after merge. Single PR.

**Tech Stack:** Dynacat 2.3.0 YAML config schema, Go-template inside `custom-api` widgets, GitHub REST API, Prometheus HTTP API, Gatus API, CSS `backdrop-filter`.

**Spec:** `docs/superpowers/specs/2026-05-28-dynacat-improvements-design.md`

---

## Pre-flight

### Task 0: Branch + diagnose the Releases widget failure

**Files:** none (read-only investigation)

The spec calls for diagnosing the Releases widget error inline rather than guessing. Do it before touching anything.

- [ ] **Step 1: Branch from main**

```bash
cd /home/kryzql/home-ops
git checkout main
git pull --ff-only
git checkout -b feat/dynacat-improvements
```

- [ ] **Step 2: Look at the actual Dynacat error logs for the releases widget**

```bash
kubectl -n selfhosted logs deploy/dynacat --tail=300 | grep -i -E "release|nouvelle|repository" | tail -20
```

Expected: at least one error line revealing which repo or which HTTP call fails. Record the exact error.

- [ ] **Step 3: Test each repo independently via curl from inside the pod**

```bash
TOKEN=$(kubectl -n selfhosted get secret dynacat-secret -o jsonpath='{.data.GITHUB_TOKEN}' | base64 -d)
for r in TandoorRecipes/recipes actualbudget/actual panonim/dynacat paperless-ngx/paperless-ngx immich-app/immich nextcloud/server; do
  echo "--- $r ---"
  kubectl -n selfhosted exec deploy/dynacat -- \
    wget -qO- --header="Authorization: Bearer $TOKEN" --header="Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$r/releases?per_page=1" 2>&1 | head -c 200
  echo
done
```

Expected: each repo returns a JSON array (possibly empty `[]` if no releases). Note any 404, 401, or 403. The repo(s) that fail are the ones to remove in Task 4 below.

---

## Phase 1: All configmap edits (one task, one commit)

The plan groups all edits into a single commit because they share one file and produce one logical change ("improve the dashboard"). Subagent-driven execution will dispatch one implementer, then a spec reviewer, then a code-quality reviewer.

### Task 1: Apply all configmap edits

**Files:**
- Modify: `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`

This task performs 6 distinct edits on the same file. Each subsection below shows the exact change.

#### 1.1 — Replace the monolithic services monitor with 4 grouped monitors

The current `monitor` widget on page `stats` (starting around line 628 of configmap.yaml, `size: full` column) lists 17 sites flat. Replace it with a `group` widget containing 4 child `monitor` widgets (Infra, Media, Downloads, Selfhosted).

- [ ] **Step 1: Find the current block**

```bash
grep -n "type: monitor" /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

The line ~630 entry (under page `stats`, after `- size: full`) is the one to replace. Mentally note where the next widget starts (lines after the last entry of that monitor, before the next `- size: small`).

- [ ] **Step 2: Replace the entire monitor block with this YAML**

Open `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`, locate the `- type: monitor` at line ~630 (inside page `stats`, inside the `- size: full` column), and replace it through the `- title: Actual Budget` block end with :

```yaml
              - type: group
                widgets:
                  - type: monitor
                    title: Infra
                    sites:
                      - title: Grafana
                        url: https://grafana.${SECRET_DOMAIN}
                        icon: di:grafana
                      - title: Prometheus
                        url: https://prometheus.${SECRET_DOMAIN}/-/healthy
                        icon: di:prometheus
                      - title: Gatus
                        url: https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses
                        icon: di:gatus
                      - title: TrueNAS
                        url: http://${NAS_IP}
                        icon: di:truenas
                  - type: monitor
                    title: Media
                    sites:
                      - title: Emby
                        url: https://emby.${SECRET_DOMAIN}
                        icon: di:emby
                      - title: Audiobookshelf
                        url: https://audiobookshelf.${SECRET_DOMAIN}
                        icon: di:audiobookshelf
                  - type: monitor
                    title: Downloads
                    sites:
                      - title: Radarr
                        url: https://radarr.${SECRET_DOMAIN}
                        icon: di:radarr
                      - title: Sonarr
                        url: https://sonarr.${SECRET_DOMAIN}
                        icon: di:sonarr
                      - title: Bazarr
                        url: https://bazarr.${SECRET_DOMAIN}
                        icon: di:bazarr
                      - title: Prowlarr
                        url: https://prowlarr.${SECRET_DOMAIN}
                        icon: di:prowlarr
                      - title: Sabnzbd
                        url: https://sabnzbd.${SECRET_DOMAIN}
                        icon: di:sabnzbd
                      - title: qBittorrent
                        url: https://qbittorrent.${SECRET_DOMAIN}
                        icon: di:qbittorrent
                  - type: monitor
                    title: Selfhosted
                    sites:
                      - title: Paperless
                        url: https://paperless.${SECRET_DOMAIN}
                        icon: di:paperless-ngx
                      - title: Tandoor
                        url: https://tandoor.${SECRET_DOMAIN}
                        icon: si:tandoorrecipes
                      - title: Nextcloud
                        url: https://nextcloud.${SECRET_DOMAIN}
                        icon: si:nextcloud
                      - title: IT-Tools
                        url: https://it-tools.${SECRET_DOMAIN}
                        icon: di:it-tools
                      - title: Actual Budget
                        url: https://budget.${SECRET_DOMAIN}
                        icon: si:actualbudget
```

Preserves all 17 sites, their URLs, their icons (the existing config uses both `di:` and `si:` icon prefixes — keep each site's original icon ref). Three changes vs original :
- Wrapping `type: group` with 4 sub-monitors instead of one flat list
- Gatus URL: `https://gatus.${SECRET_DOMAIN}` → `https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses` (fixes the 404)
- Same indentation as before (the widget starts at `              ` = 14 spaces)

#### 1.2 — Replace the broken `PRs Renovate` widget with a Renovate-filtered list

The current widget (around line ~687) queries all open PRs on `thomloy/home-ops` without filter. Narrow it to only Renovate PRs by changing the URL to GitHub Search API with `author:app/renovate`.

- [ ] **Step 3: Replace the entire `PRs Renovate` widget block**

Find the block starting with `- type: custom-api` titled `PRs Renovate` and replace it with :

```yaml
              - type: custom-api
                title: PRs Renovate
                allow-insecure-html: true
                cache: 5m
                update-interval: 5m
                url: "https://api.github.com/search/issues?q=repo:thomloy/home-ops+type:pr+state:open+author:app/renovate&sort=updated&per_page=10"
                headers:
                  Authorization: Bearer $${GITHUB_TOKEN}
                  Accept: application/vnd.github+json
                template: |
                  {{$prs := .JSON.Array "items"}}
                  {{if eq (len $prs) 0}}
                  <div style="font-size:.8em;opacity:.5;padding:8px 0;text-align:center">Aucune PR Renovate en attente ✓</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:5px">
                  {{range $prs}}
                  <a href="{{.String "html_url"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.12);border-radius:6px;border-left:3px solid #3b82f6" onmouseover="this.style.opacity=.7" onmouseout="this.style.opacity=1">
                    <span style="font-size:.65em;font-weight:700;color:#3b82f6;min-width:32px;margin-top:2px;flex-shrink:0">#{{.Int "number"}}</span>
                    <div style="min-width:0;flex:1">
                      <div style="font-size:.78em;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">{{.String "title"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>
                  {{end}}
```

Key differences vs original :
- URL : `/search/issues?q=...+author:app/renovate` instead of `/repos/.../pulls`
- JSON path : `.JSON.Array "items"` (search API wraps in `items[]`) instead of `"@this"` (flat array from /pulls)
- Cache 10m → 5m, plus `update-interval: 5m` added (SSE auto-refresh)
- Border color blue (3b82f6) to distinguish from green (which we'll use for commits)

#### 1.3 — Diagnose-then-fix Releases widget

The original block lists 6 repos. Based on Task 0's diagnosis, one or more may fail. Use the diagnosis result.

- [ ] **Step 4: Apply diagnosis-driven fix**

If Task 0 revealed a specific failing repo, edit the `Releases` widget at line ~711 and remove that repo from the `repositories:` list. If all 6 repos returned valid JSON in Task 0, the widget config is actually fine — the runtime error may be a transient Dynacat parse issue. In that case, add an explicit `limit: 5` and `since: 720h` (30 days) to constrain output and force a re-fetch:

```yaml
              - type: releases
                title: Nouvelles versions
                cache: 1h
                update-interval: 1h
                token: $${GITHUB_TOKEN}
                limit: 5
                repositories:
                  - TandoorRecipes/recipes
                  - actualbudget/actual
                  - panonim/dynacat
                  - paperless-ngx/paperless-ngx
                  - immich-app/immich
                  - nextcloud/server
```

If Task 0 showed a specific repo failing, remove just that one line from `repositories:`. If 3+ repos fail, file an upstream issue with Dynacat — for this PR, keep the surviving ones.

#### 1.4 — Add 3 new widgets

After the `Releases` widget, before `Liens rapides`, insert these three widgets in order. The final column-3 order should be: PRs Renovate, Commits récents (NEW), Nouvelles versions, K8s pod issues (NEW), Alertes Gatus (NEW), Liens rapides.

- [ ] **Step 5: Insert `Commits récents` widget (between PRs Renovate and Releases)**

```yaml
              - type: custom-api
                title: Commits récents
                allow-insecure-html: true
                cache: 5m
                update-interval: 5m
                url: "https://api.github.com/repos/thomloy/home-ops/commits?per_page=5"
                headers:
                  Authorization: Bearer $${GITHUB_TOKEN}
                  Accept: application/vnd.github+json
                template: |
                  {{$commits := .JSON.Array "@this"}}
                  {{if eq (len $commits) 0}}
                  <div style="font-size:.8em;opacity:.5;padding:8px 0;text-align:center">Aucun commit récent</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $commits}}
                  {{$msg := .String "commit.message"}}
                  {{$title := index (split $msg "\n") 0}}
                  <a href="{{.String "html_url"}}" target="_blank" style="text-decoration:none;color:inherit;padding:5px 8px;background:rgba(0,0,0,.08);border-radius:5px;border-left:3px solid #22c55e;display:block" onmouseover="this.style.opacity=.7" onmouseout="this.style.opacity=1">
                    <div style="font-size:.78em;font-weight:600;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">{{$title}}</div>
                    <div style="font-size:.68em;opacity:.55;margin-top:2px">{{.String "commit.author.name"}} · {{.String "commit.author.date"}}</div>
                  </a>
                  {{end}}
                  </div>
                  {{end}}
```

Note : `commit.author.date` is rendered as ISO-8601 raw. Dynacat's relative-time helper (`humanize_time` or `toRelativeTime`) may not exist in 2.3.0 — leaving raw ISO is the safe fallback. If you can confirm a helper exists via `docs/docs/custom-api.md`, swap it in.

- [ ] **Step 6: Insert `K8s pod issues` widget (after Nouvelles versions)**

```yaml
              - type: custom-api
                title: K8s pod issues
                allow-insecure-html: true
                cache: 30s
                update-interval: 30s
                url: "http://kube-prometheus-stack-prometheus.observability.svc.cluster.local:9090/api/v1/query?query=(kube_pod_container_status_restarts_total>5)+or+(kube_pod_status_phase%7Bphase=~%22Pending%7CFailed%7CUnknown%22%7D==1)+or+(kube_pod_container_status_waiting_reason%7Breason=%22CrashLoopBackOff%22%7D==1)"
                template: |
                  {{$results := .JSON.Array "data.result"}}
                  {{if eq (len $results) 0}}
                  <div style="font-size:.85em;opacity:.6;padding:8px 0;text-align:center">✅ Tous les pods sains</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $results}}
                  {{$ns := .String "metric.namespace"}}{{$pod := .String "metric.pod"}}{{$reason := .String "metric.reason"}}
                  <div style="font-size:.78em;padding:5px 8px;background:rgba(239,68,68,.12);border-left:3px solid #ef4444;border-radius:5px">
                    <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{$ns}} / {{$pod}}</div>
                    {{if $reason}}<div style="font-size:.85em;opacity:.7">{{$reason}}</div>{{end}}
                  </div>
                  {{end}}
                  </div>
                  {{end}}
```

PromQL is URL-encoded in the query string. The CNP allows dynacat → prometheus already (the existing Infra widget proves this).

- [ ] **Step 7: Insert `Alertes Gatus` widget (after K8s pod issues)**

This widget uses Dynacat template helpers (`slice`, `append`, `dict`, `sortDesc`) that may not exist in 2.3.0. Implementer should first test the helpers by writing a minimal version and observing the rendered output. If helpers are missing, use this **simpler fallback** that lists endpoints with a failure in their latest result :

```yaml
              - type: custom-api
                title: Alertes Gatus
                allow-insecure-html: true
                cache: 1m
                update-interval: 1m
                url: "https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses?page=1"
                template: |
                  {{$endpoints := .JSON.Array "@this"}}
                  {{$failing := slice}}
                  {{range $endpoints}}
                  {{$results := .JSON.Array "results"}}
                  {{if gt (len $results) 0}}
                  {{$last := index $results 0}}
                  {{if not (eq ($last.String "success") "true")}}
                  {{$failing = append $failing (printf "%s · %s" (.String "name") ($last.String "timestamp"))}}
                  {{end}}
                  {{end}}
                  {{end}}
                  {{if eq (len $failing) 0}}
                  <div style="font-size:.85em;opacity:.6;padding:8px 0;text-align:center">✅ Aucune alerte</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $failing}}
                  <div style="font-size:.78em;padding:5px 8px;background:rgba(245,158,11,.12);border-left:3px solid #f59e0b;border-radius:5px">{{.}}</div>
                  {{end}}
                  </div>
                  {{end}}
```

If the helpers (`slice`, `append`) don't exist in 2.3.0, the simplest fallback is a `monitor`-style widget pointing at the Gatus UI itself :

```yaml
              - type: monitor
                title: Gatus (santé globale)
                sites:
                  - title: Tous les endpoints
                    url: https://gatus.${SECRET_DOMAIN}/api/v1/endpoints/statuses
                    icon: di:gatus
```

Use the simpler fallback if implementation hits errors. Goal is operator visibility, not perfect fidelity.

#### 1.5 — Add CSS frosted-glass rule

- [ ] **Step 8: Append the CSS rule to the `custom.css` data key**

Locate the `custom.css: |` block (around line ~821 of configmap.yaml). At the END of the existing CSS content, append :

```css

/* === Frosted glass on all widget cards (added 2026-05-28) === */
.widget {
  background-color: hsla(28, 20%, 15%, 0.62);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
```

Note : leading blank line before the comment to separate from existing CSS. Do not delete or modify any other CSS rule.

### Task 2: Local docker smoke test

**Files:** none (read-only validation using docker)

Same pattern as the initial dynacat deploy : boot dynacat 2.3.0 against the edited configmap to catch parse errors before push.

- [ ] **Step 1: Extract the updated dynacat.yml**

```bash
mkdir -p /tmp/dynacat-improve/assets
yq eval '.data."dynacat.yml"' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml > /tmp/dynacat-improve/dynacat.yml
yq eval '.data."custom.css"' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml > /tmp/dynacat-improve/assets/custom.css
touch /tmp/dynacat-improve/assets/bg.jpg
# substitute Flux postBuild vars + dummy env so dynacat can parse
sed -i 's/\${NODE_IP_1}/10.0.0.1/g; s/\${NODE_IP_2}/10.0.0.2/g; s/\${NODE_IP_3}/10.0.0.3/g; s/\${NAS_IP}/10.0.0.4/g; s/\${SECRET_DOMAIN}/example.com/g' /tmp/dynacat-improve/dynacat.yml
```

- [ ] **Step 2: Boot and tail logs for 10s**

```bash
timeout 10 docker run --rm --name dynacat-improve-check \
  -v /tmp/dynacat-improve/dynacat.yml:/app/config/dynacat.yml:ro \
  -v /tmp/dynacat-improve/assets:/app/assets:ro \
  -e TMDB_API_KEY=dummy -e EMBY_API_KEY=dummy -e RADARR_API_KEY=dummy \
  -e SONARR_API_KEY=dummy -e READARR_API_KEY=dummy -e LIDARR_API_KEY=dummy \
  -e NAVIDROME_USER=dummy -e NAVIDROME_PASS=dummy -e GITHUB_TOKEN=dummy \
  -e ABS_TOKEN=dummy \
  -p 18181:8080 \
  panonim/dynacat:2.3.0 2>&1 | tail -30
echo "exit code: $?"
docker rm -f dynacat-improve-check 2>/dev/null
rm -rf /tmp/dynacat-improve
```

Expected: exit code 124 (SIGTERM from timeout = server was running and waiting for connections, no parse errors), and `Starting server on :8080` appears in logs.

If parse errors appear ("Config has errors: ..."), fix them in the configmap before proceeding to commit.

### Task 3: Commit, push, open PR

**Files:** none

- [ ] **Step 1: Verify nothing else changed**

```bash
git status --short
```

Expected: exactly one modified file, `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`.

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
git commit -m "$(cat <<'EOF'
feat(dynacat): refactor services into 4 groups, frosted-glass CSS, 3 new widgets

- Wrap monolithic services monitor on stats page in a `group` with 4
  category subsections (Infra, Media, Downloads, Selfhosted)
- Fix Gatus probe URL: append /api/v1/endpoints/statuses (was 404 on root)
- Add `update-interval: 5m` + narrow query to Renovate-author PRs only
- Add 3 new operator widgets: Commits récents, K8s pod issues, Alertes Gatus
- Add site-wide `.widget` frosted-glass CSS (backdrop-blur 10px + hsla bg)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/dynacat-improvements
gh pr create --base main --head feat/dynacat-improvements \
  --title "feat(dynacat): refactor services, frosted-glass CSS, 3 new widgets" \
  --body "$(cat <<'EOF'
## Summary
- Replaces the monolithic 17-service monitor on stats with a `group` of 4 named monitors (Infra/Media/Downloads/Selfhosted)
- Fixes Gatus probe URL (was returning 404 on root)
- Adds `update-interval: 5m` to PRs Renovate + narrows query to Renovate author only
- Adds 3 new operator widgets: Commits récents, K8s pod issues, Alertes Gatus
- Adds site-wide frosted-glass CSS via `.widget` backdrop-filter

Spec: `docs/superpowers/specs/2026-05-28-dynacat-improvements-design.md`
Plan: `docs/superpowers/plans/2026-05-28-dynacat-improvements.md`

## Test plan
- [ ] flux-local CI green
- [ ] Local `docker run panonim/dynacat:2.3.0` against the configmap exits with timeout (no parse errors)
- [ ] After merge: pod auto-rolls (reloader on configmap), reaches 1/1 Running
- [ ] Open `https://home.kryzql.space/stats` — see 4 grouped services blocks
- [ ] Each new widget renders (Commits, K8s, Gatus alerts)
- [ ] Frosted-glass visible on every widget card

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Watch CI**

```bash
gh pr checks --watch --interval 20
```

Expected: flux-local checks green. Trivy may still fail with the same install flake from prior PRs — that's a known infrastructure issue, not blocking.

### Task 4: Merge + verify

**Files:** none

- [ ] **Step 1: Merge squash**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 2: Sync local main**

```bash
git checkout main
git fetch origin
git reset --hard origin/main
```

- [ ] **Step 3: Force reconcile**

```bash
flux reconcile source git flux-system
flux reconcile kustomization dynacat -n selfhosted
```

- [ ] **Step 4: Wait for reloader to roll the pod**

```bash
kubectl -n selfhosted rollout status deploy/dynacat --timeout=120s
```

Expected: success within 1 minute (reloader detects the configmap hash change and triggers rollout).

- [ ] **Step 5: Browser verification**

Open `https://home.kryzql.space/stats`. Verify :
- The services block shows 4 named subsections (Infra, Media, Downloads, Selfhosted)
- Gatus shows ✅ (no longer 404)
- PRs Renovate shows real PRs (or "Aucune PR Renovate en attente ✓" if none)
- Commits récents shows the last 5 home-ops commits
- K8s pod issues shows ✅ Tous les pods sains (or the actual failing pods)
- Alertes Gatus renders (✅ Aucune alerte or list)
- Nouvelles versions shows new release entries (or has been fixed per Task 0 diagnosis)
- All widgets have rounded corners + frosted-glass effect over the painting

- [ ] **Step 6: SSE still works after the CSS / configmap changes**

```bash
timeout 5 curl -sk --resolve home.kryzql.space:443:192.168.42.110 \
  -H "Accept: text/event-stream" \
  -o /tmp/sse_probe \
  -w "HTTP %{http_code} content-type=%{content_type}\n" \
  --max-time 5 \
  "https://home.kryzql.space/api/sse/updates"
wc -l /tmp/sse_probe
rm -f /tmp/sse_probe
```

Expected: HTTP 200, content-type `text/event-stream`, line count > 5 (at least one widget-update event received).

---

## Rollback

If the dashboard misbehaves badly (parse errors, blank page, all widgets failing) :

```bash
git revert <merge-sha>
git push
flux reconcile kustomization dynacat -n selfhosted
```

Reloader rolls the pod back to the old configmap within ~1 minute. State loss : zero (configmap-driven, no PV).

## Follow-up tweaks (not blockers)

- If frosted-glass opacity (0.62) feels too transparent on light zones of the painting, bump to 0.78 in `.widget` rule — one-line CSS change.
- If a template helper used in widgets 5-7 misbehaves, simplify to plainer Go-template (`.String`, `.Int`, `range`) — fallback paths are noted in each widget's spec section.
- Speedtest and iCal calendar widgets remain out-of-scope (require new infra) — open as separate PR when ready.
