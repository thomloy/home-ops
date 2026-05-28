# Dynacat UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure Dynacat pages `home`, `media`, `games` around clear usage intents — fix every broken widget, remove duplicates with `stats`, fill the empty Games column, and add live Crafty server data.

**Architecture:** Three file modifications in one PR: `selfhosted/dynacat/app/configmap.yaml` (widget layout edits for 3 pages), `selfhosted/dynacat/app/externalsecret.yaml` (add CRAFTY_API_TOKEN), `games/crafty/app/ciliumnetworkpolicy.yaml` (allow dynacat ingress). No HelmRelease change. Reloader detects configmap+secret change and rolls the dynacat pod automatically post-merge.

**Tech Stack:** Dynacat 2.3.0 widget schema, Go-templates with gjson helpers, Crafty Controller v2 REST API, PaperMC v3 fill API, External Secrets Operator + 1Password Connect, Cilium L3/L4 NetworkPolicy.

**Spec:** `docs/superpowers/specs/2026-05-28-dynacat-ux-overhaul-design.md`

**Pre-flight facts already gathered** (so the implementer doesn't redo them):
- Crafty server UUID : `51ebc4d3-9008-42ee-8de6-c3b347fc701f`
- Crafty service URL : `http://crafty-app.games.svc.cluster.local:8000` (service port `http:8000`, proxy container terminates TLS internally)
- Crafty CNP exists at `kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml` — has ingress rules for envoy-internal:8000 + tailscale:25565 + kube-dns
- 1P item `crafty` exists in vault `kubernetes` with field `api_token` populated (139 chars)
- Bibliothèque widget (Media page) : large `group` containing 3 sub-widgets that use inline JS calling Emby — "Chargement..." text is the placeholder JS replaces on success; it stays visible when Emby returns 503 (pod-level issue, not widget config). Once Emby pods recover, widgets render.
- Builds Paper widget (Games page) : currently uses `.JSON.Int "builds.|-1"` which gjson parses as 0. PaperMC v3 fill API `https://fill.papermc.io/v3/projects/paper/versions/1.21.11/builds/latest` returns `{build: <int>}` — simpler.
- Reddit r/selfhosted : confirmed 403 by user environment (old.reddit.com blocks scrapers without auth).

---

## Phase 0 : Branch

### Task 0 : Create feature branch

**Files:** none

- [ ] **Step 1 : Branch from main**

```bash
cd /home/kryzql/home-ops
git checkout main
git pull --ff-only
git checkout -b feat/dynacat-ux-overhaul
```

---

## Phase 1 : Foundation (CNP + secret)

### Task 1 : Patch Crafty CNP to allow dynacat

**Files:**
- Modify: `kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml`

- [ ] **Step 1 : Add a 3rd ingress rule allowing dynacat → port 8000**

Insert this block in the `ingress:` list BEFORE the existing kube-dns rule (after the tailscale:25565 rule), preserving 4-space indent of the existing `- fromEndpoints:` blocks :

```yaml
    # Dashboard widget probes (Crafty API for players/stats)
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: selfhosted
            app.kubernetes.io/name: dynacat
      toPorts:
        - ports:
            - port: "8000"
              protocol: TCP
```

- [ ] **Step 2 : Validate**

```bash
yq eval '.spec.ingress | length' /home/kryzql/home-ops/kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml
```

Expected: `4` (envoy-internal:8000, tailscale:25565, **dynacat:8000 (new)**, kube-dns)

```bash
kustomize build /home/kryzql/home-ops/kubernetes/apps/games/crafty/app > /dev/null && echo OK
```

- [ ] **Step 3 : Commit**

```bash
cd /home/kryzql/home-ops
git add kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml
git commit -m "$(cat <<'EOF'
feat(crafty): allow ingress from selfhosted/dynacat for API widgets

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2 : Add CRAFTY_API_TOKEN to ExternalSecret

**Files:**
- Modify: `kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml`

- [ ] **Step 1 : Append a 5th data entry at the END of `spec.data`**

Current last entry is `BETTER_AUTH_SECRET` (per the file structure). Actually verify with :

```bash
yq eval '.spec.data[].secretKey' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml
```

(Run this to see current keys.)

Then append (at the end of `data:` list, same indent as existing entries) :

```yaml
    - secretKey: CRAFTY_API_TOKEN
      remoteRef:
        key: crafty
        property: api_token
```

- [ ] **Step 2 : Validate**

```bash
yq eval '.spec.data | length' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml
```

Expected: previous count + 1.

```bash
yq eval '.spec.data[-1]' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml
```

Expected: the CRAFTY_API_TOKEN block, looking up `crafty` / `api_token`.

```bash
kustomize build /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app > /dev/null && echo OK
```

- [ ] **Step 3 : Commit**

```bash
git add kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml
git commit -m "$(cat <<'EOF'
feat(dynacat): pull CRAFTY_API_TOKEN from 1P item `crafty`

Needed by the new Crafty API widgets (players online, server stats)
added in the Games page redesign.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 : Configmap edits (one commit, all 3 pages)

This phase performs all the widget changes. Because they all live in one file and represent one logical redesign, they go in a single commit.

### Task 3 : HOME — fix probes, remove duplicate, replace Reddit

**Files:**
- Modify: `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`

The home page is `pages[0]` (yaml index). The `Infrastructure` monitor widget to remove is the one on home col 1 listing Grafana/Prometheus/TrueNAS/Gatus (lines ~36-50 in the configmap). Emby + ABS entries to fix are in a `monitor` widget on home col 2 (search by their `- title:` entries). Reddit widget to replace is on home col 2 too.

- [ ] **Step 1 : Locate current Reddit + Infrastructure + media monitor widgets**

```bash
grep -n "type: reddit\|title: Infrastructure\|title: Emby\|title: Audiobookshelf" \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml | head -10
```

Note the line numbers. There are multiple `title: Emby` matches (1 on home, 1 on stats subgroup, 1 elsewhere — focus on the **lowest line number**, which is home).

- [ ] **Step 2 : Remove the `Infrastructure` monitor widget on home col 1**

The widget block looks like :

```yaml
              - type: monitor
                title: Infrastructure
                sites:
                  - title: Grafana
                    url: https://grafana.${SECRET_DOMAIN}
                    icon: di:grafana
                  - title: Prometheus
                    url: https://prometheus.${SECRET_DOMAIN}/-/healthy
                    icon: di:prometheus
                  - title: TrueNAS
                    url: http://${NAS_IP}
                    icon: di:truenas
                  - title: Gatus
                    url: http://gatus.observability.svc.cluster.local
                    icon: di:gatus
```

Delete the entire block (from `- type: monitor` through the last entry of the `sites:` list, inclusive). Make sure not to delete the `infra` custom-api widget right above it (which renders the per-node bar chart).

- [ ] **Step 3 : Fix Emby probe in home col 2 media monitor**

Locate the home media monitor — `type: monitor`, `title: ...` (probably `Media` or unnamed) with `Emby` as one of the sites. Change the Emby entry from :

```yaml
                  - title: Emby
                    url: https://emby.${SECRET_DOMAIN}
                    icon: di:emby
```

to :

```yaml
                  - title: Emby
                    url: https://emby.${SECRET_DOMAIN}
                    check-url: http://emby.media.svc.cluster.local:8096
                    icon: di:emby
```

(Port 8096 is Emby's internal HTTP port — confirmed by `kubectl -n media get svc emby` showing `8096:30339/TCP`.)

- [ ] **Step 4 : Fix Audiobookshelf probe (same media monitor)**

Change the Audiobookshelf entry from :

```yaml
                  - title: Audiobookshelf
                    url: https://audiobookshelf.${SECRET_DOMAIN}
                    icon: di:audiobookshelf
```

to :

```yaml
                  - title: Audiobookshelf
                    url: https://audiobookshelf.${SECRET_DOMAIN}
                    check-url: http://audiobookshelf.media.svc.cluster.local
                    icon: di:audiobookshelf
```

(Default port 80 on the ABS ClusterIP service.)

- [ ] **Step 5 : Replace Reddit widget with Hacker News**

Locate the entire Reddit block (`- type: reddit` ... probably with `subreddit:` etc) on home col 2 and replace with :

```yaml
              - type: hacker-news
                title: Hacker News
                cache: 30m
                update-interval: 30m
                limit: 10
```

This is a Dynacat built-in widget, no auth needed.

- [ ] **Step 6 : Validate home page rendering**

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[0] | {name, cols: (.columns | length), widgets_total: ([.columns[].widgets[]] | length)}' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected: `name: home`, `cols: 3`, widgets count decreased by 1 (Infrastructure removed) + Reddit → Hacker News (replaced 1-for-1).

Confirm no orphan refs :

```bash
grep -c "type: reddit\|title: Infrastructure" /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected: `0` (well, the Stats Infra group still says `title: Infra` not `Infrastructure`, so this grep should be 0).

### Task 4 : MEDIA — move Seerr requests to col 3

**Files:**
- Modify: `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`

The Media page is `pages[1]`. The "Requêtes" widget on col 1 (large list of Seerr requests) moves to col 3. The "Bibliothèque" widget (which includes Dernièrement ajouté Emby JS) stays — it renders correctly once Emby pods recover (currently `ContainerCreating`, a separate operational issue not fixable from this PR).

**Deliberate spec divergence** : the spec §3.2 also proposed consolidating "Lecture en cours" + "Musique en cours" + ABS now-playing into a single custom-api widget that polls all 3 sources. The spec's own risk section noted "Fallback : implementer can split into 3 separate compact widgets if the unified template proves unwieldy". Pre-flight inspection showed the current state IS already 2 separate compact widgets (one for Emby/video, one for Navidrome/music) that both gracefully render "Aucune lecture" when idle. They work as-is once Emby/ABS pods recover. Building a unified template risks `function not defined` errors (saw this happen for `split` helper in a prior PR). **Plan choice : leave the 2 widgets as-is**, no consolidation. Lower risk, identical UX.

- [ ] **Step 1 : Locate Requêtes widget block**

```bash
grep -n "title: Requêtes\|title: Requetes" /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml | head -3
```

The widget is a large `custom-api` block on Media col 1 with the Seerr API URL and inline JS template that lists requests with posters.

- [ ] **Step 2 : Cut the Requêtes widget block**

Identify the FULL block (from `- type: custom-api` line through the end of its `template:` block — the `template: |` block scalar continues until the next widget starts at the same indent). Cut it (delete + remember).

- [ ] **Step 3 : Paste it as the FIRST widget on Media col 3**

Find the start of Media col 3 (look for the SECOND `- size: small` under page `media` — the first `- size: small` is col 1). Insert the cut Requêtes widget as the first item in its `widgets:` list.

- [ ] **Step 4 : Validate Media page widget counts**

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[1] | {col1: (.columns[0].widgets | length), col2: (.columns[1].widgets | length), col3: (.columns[2].widgets | length)}' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected: col1 count decreased by 1, col3 count increased by 1, col2 unchanged.

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[1].columns[2].widgets[0].title' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected: `Requêtes` (now first widget of col 3).

### Task 5 : GAMES — restructure col 2/3, fix Builds Paper, add Crafty widgets

**Files:**
- Modify: `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml`

The Games page is `pages[3]`. The current state : col 1 has Panneaux/Connexion/Builds Paper (Builds shows #0 due to bad gjson syntax) ; col 2 has Liens (bookmarks) + Releases plugins (releases widget) ; col 3 is EMPTY.

Edits :
1. Fix Builds Paper widget URL+template to use PaperMC v3 API (returns latest build as `{build: <int>}`)
2. Add 2 new Crafty API custom-api widgets on col 2 (Joueurs en ligne, Serveur info)
3. Move existing Liens + Releases widgets from col 2 → col 3

- [ ] **Step 1 : Fix Builds Paper widget**

Locate the Builds Paper widget on Games col 1. Replace the existing block with :

```yaml
              - type: custom-api
                title: Builds Paper
                allow-insecure-html: true
                cache: 1h
                update-interval: 1h
                url: "https://fill.papermc.io/v3/projects/paper/versions/1.21.11/builds/latest"
                template: |
                  {{$build := .JSON.Int "build"}}
                  <div style="padding:8px;background:rgba(0,0,0,.08);border-radius:6px">
                    <div style="font-size:.7em;opacity:.6">Dernier build 1.21.11</div>
                    <div style="font-weight:700;font-size:1.1em;margin-top:2px">#{{$build}}</div>
                  </div>
```

URL switched to fill.papermc.io v3 which returns a single object `{build: <int>, version: ...}` — much simpler than v2's array.

- [ ] **Step 2 : Locate Games col 2 (`size: full`) current widgets**

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[3].columns[1].widgets[].title' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected output : `Liens` and `Releases à suivre` (or similar — the bookmarks + releases widgets).

- [ ] **Step 3 : Cut Liens + Releases from col 2, paste into col 3**

Cut both widget blocks from Games col 2 `widgets:` list. Paste them as the entire content of Games col 3 (which is currently empty — col 3 might not even exist yet; create the `- size: small\n  widgets:` structure if needed).

Verify Games has 3 columns now :

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[3].columns | length' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected: `3`.

- [ ] **Step 4 : Add Joueurs en ligne widget to Games col 2 (now empty)**

In Games col 2 `widgets:` (after the cut leaves it empty), insert this widget :

```yaml
              - type: custom-api
                title: Joueurs en ligne
                allow-insecure-html: true
                cache: 30s
                update-interval: 30s
                url: "http://crafty-app.games.svc.cluster.local:8000/api/v2/servers/51ebc4d3-9008-42ee-8de6-c3b347fc701f/players"
                headers:
                  Authorization: Bearer $${CRAFTY_API_TOKEN}
                template: |
                  {{$players := .JSON.Array "data"}}
                  {{if eq (len $players) 0}}
                  <div style="font-size:.85em;opacity:.6;padding:8px 0;text-align:center">Serveur vide — aucun joueur connecté</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:6px">
                    <div style="font-size:.75em;opacity:.7;margin-bottom:4px">{{len $players}} joueur(s) en ligne</div>
                    {{range $players}}
                    <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:rgba(34,197,94,.12);border-radius:6px;border-left:3px solid #22c55e">
                      <div style="font-weight:600;font-size:.85em">{{.String "name"}}</div>
                    </div>
                    {{end}}
                  </div>
                  {{end}}
```

Notes :
- URL hardcodes the server UUID `51ebc4d3-9008-42ee-8de6-c3b347fc701f` (already determined).
- JSON path `.JSON.Array "data"` matches Crafty's API response wrapper `{status: "ok", data: [...]}`.
- If the actual API returns players under a different field, adjust at impl time (see Task 6 smoke test).

- [ ] **Step 5 : Add Serveur info widget to Games col 2**

Right after the Joueurs en ligne widget, insert :

```yaml
              - type: custom-api
                title: Serveur info
                allow-insecure-html: true
                cache: 1m
                update-interval: 1m
                url: "http://crafty-app.games.svc.cluster.local:8000/api/v2/servers/51ebc4d3-9008-42ee-8de6-c3b347fc701f/stats"
                headers:
                  Authorization: Bearer $${CRAFTY_API_TOKEN}
                template: |
                  {{$d := .JSON.Get "data"}}
                  <div style="display:flex;flex-direction:column;gap:6px;font-size:.85em">
                    <div style="display:flex;justify-content:space-between;padding:5px 10px;background:rgba(0,0,0,.06);border-radius:5px">
                      <span style="opacity:.65">Statut</span>
                      <span style="font-weight:600;color:{{if eq ($d.String "running") "true"}}#22c55e{{else}}#ef4444{{end}}">{{if eq ($d.String "running") "true"}}● En ligne{{else}}○ Hors ligne{{end}}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:5px 10px;background:rgba(0,0,0,.06);border-radius:5px">
                      <span style="opacity:.65">Version</span>
                      <span style="font-family:monospace;font-size:.85em">{{$d.String "version"}}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:5px 10px;background:rgba(0,0,0,.06);border-radius:5px">
                      <span style="opacity:.65">Joueurs max</span>
                      <span>{{$d.Int "max"}}</span>
                    </div>
                    <div style="padding:5px 10px;background:rgba(0,0,0,.06);border-radius:5px">
                      <div style="opacity:.65;font-size:.85em;margin-bottom:3px">MOTD</div>
                      <div style="font-size:.85em">{{$d.String "desc"}}</div>
                    </div>
                  </div>
```

Notes :
- The exact field names (`running`, `version`, `max`, `desc`) match Crafty v2 API stats endpoint. If field names differ in this Crafty version, the implementer adjusts after Task 6 smoke test reveals the actual response shape.
- Falls back to gracefully showing the data even if some fields are missing (gjson returns empty string for missing fields).

- [ ] **Step 6 : Validate Games page final layout**

```bash
yq eval '.data."dynacat.yml" | from_yaml | .pages[3].columns | [.[] | {size, widgets: [.widgets[].title]}]' \
  /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
```

Expected output structure :

```yaml
- size: small
  widgets: [Panneaux, Connexion, Builds Paper]
- size: full
  widgets: [Joueurs en ligne, Serveur info]
- size: small
  widgets: [Liens, Releases à suivre]
```

### Task 6 : Commit Phase 2 (single commit, all configmap edits)

**Files:** none (just commit what's been edited in Tasks 3-5)

- [ ] **Step 1 : Verify only configmap.yaml changed since Task 2's commit**

```bash
cd /home/kryzql/home-ops
git diff --stat HEAD
```

Expected: only `kubernetes/apps/selfhosted/dynacat/app/configmap.yaml` modified.

- [ ] **Step 2 : Commit**

```bash
git add kubernetes/apps/selfhosted/dynacat/app/configmap.yaml
git commit -m "$(cat <<'EOF'
feat(dynacat): intent-driven page restructure — home/media/games

home:
  - remove Infrastructure monitor (duplicate of stats Infra subgroup)
  - fix Emby + Audiobookshelf probes via check-url (cluster-internal)
  - replace broken Reddit r/selfhosted widget with Hacker News built-in

media:
  - move Requêtes Seerr widget from col 1 to col 3 (less frequent visual reference)

games:
  - fix Builds Paper widget by switching to PaperMC v3 fill API
    (was showing #0 due to v2 gjson array indexing bug)
  - add 2 new Crafty API widgets on col 2: Joueurs en ligne + Serveur info
    (real-time players + version/uptime/MOTD)
  - move Liens + Releases plugins from col 2 to col 3 (fills empty column)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline main..HEAD
```

Expected: 3 commits ahead of main (Task 1 CNP, Task 2 ESO, Task 6 configmap).

---

## Phase 3 : Local docker smoke test

### Task 7 : Validate config parses against dynacat 2.3.0

**Files:** none

- [ ] **Step 1 : Extract + substitute postBuild vars + run**

```bash
mkdir -p /tmp/dynacat-ux/assets
yq eval '.data."dynacat.yml"' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml > /tmp/dynacat-ux/dynacat.yml
yq eval '.data."custom.css"' /home/kryzql/home-ops/kubernetes/apps/selfhosted/dynacat/app/configmap.yaml > /tmp/dynacat-ux/assets/custom.css
touch /tmp/dynacat-ux/assets/bg.jpg
sed -i 's/\${NODE_IP_1}/10.0.0.1/g; s/\${NODE_IP_2}/10.0.0.2/g; s/\${NODE_IP_3}/10.0.0.3/g; s/\${NAS_IP}/10.0.0.4/g; s/\${SECRET_DOMAIN}/example.com/g' /tmp/dynacat-ux/dynacat.yml

timeout 10 docker run --rm --name dynacat-ux-check \
  -v /tmp/dynacat-ux/dynacat.yml:/app/config/dynacat.yml:ro \
  -v /tmp/dynacat-ux/assets:/app/assets:ro \
  -e TMDB_API_KEY=d -e EMBY_API_KEY=d -e RADARR_API_KEY=d -e SONARR_API_KEY=d \
  -e READARR_API_KEY=d -e LIDARR_API_KEY=d -e NAVIDROME_USER=d -e NAVIDROME_PASS=d \
  -e GITHUB_TOKEN=d -e ABS_TOKEN=d -e CRAFTY_API_TOKEN=d \
  -p 18181:8080 \
  panonim/dynacat:2.3.0 2>&1 | tail -20
echo "exit code: $?"
rm -rf /tmp/dynacat-ux
docker rm -f dynacat-ux-check 2>/dev/null
```

Expected : exit code 143 (SIGTERM from timeout = server was running) and NO `Config has errors:` lines in the output. Lines about widget API calls failing (401 etc.) due to dummy env vars are EXPECTED and fine — that's runtime, not config parse.

- [ ] **Step 2 : If parse errors appear, fix and re-test**

Common gotchas to look for in error output :
- `function "X" not defined` — a Go-template helper used that doesn't exist in 2.3.0 (saw `split` cause this on Commits widget last time). Replace with what works.
- `unexpected variable` — gjson path returns null where template expects something. Adjust the JSON path.
- Indentation issues — `yq eval` typically catches these but Dynacat's parser is stricter on some patterns.

Fix in the configmap, amend would lose information so create a NEW commit with the fix.

---

## Phase 4 : Push, PR, merge

### Task 8 : Push + open PR + watch CI

**Files:** none

- [ ] **Step 1 : Push**

```bash
git push -u origin feat/dynacat-ux-overhaul
```

- [ ] **Step 2 : Open PR**

```bash
gh pr create --base main --head feat/dynacat-ux-overhaul \
  --title "feat(dynacat): UX overhaul — home/media/games restructure + Crafty widgets" \
  --body "$(cat <<'EOF'
## Summary
Intent-driven restructure of the 3 non-stats Dynacat pages (stats was already overhauled in #181):

- **home** : removes Infrastructure monitor (duplicated stats Infra subgroup), fixes Emby+ABS probes via `check-url` to cluster-internal services, replaces broken Reddit r/selfhosted widget (403 permanently) with the built-in Hacker News widget
- **media** : moves Requêtes Seerr widget from col 1 to col 3 for better visual balance (Bibliothèque widgets render correctly once Emby pods recover — separate operational issue, not fixed here)
- **games** : fixes Builds Paper widget (was #0 due to gjson array indexing bug) by switching to PaperMC v3 fill API; adds 2 new real-time Crafty API widgets (Joueurs en ligne, Serveur info) on col 2; moves Liens + Releases plugins from col 2 to col 3 to fill previously-empty column

Plus infra : Crafty CNP allows `selfhosted/dynacat` on TCP 8000, ExternalSecret pulls a new `CRAFTY_API_TOKEN` from 1P item `crafty` (PLAYERS-scope, populated out-of-band by operator).

Spec: `docs/superpowers/specs/2026-05-28-dynacat-ux-overhaul-design.md`
Plan: `docs/superpowers/plans/2026-05-28-dynacat-ux-overhaul.md`

## Test plan
- [x] Local `docker run panonim/dynacat:2.3.0` against the configmap survives 10s with no parse errors
- [ ] flux-local CI green
- [ ] Post-merge: ExternalSecret `dynacat` Ready=True with all keys including CRAFTY_API_TOKEN
- [ ] Pod auto-rolls via reloader, reaches 1/1 Running
- [ ] Browser `/home`: Hacker News widget renders, Infrastructure monitor gone
- [ ] Browser `/games`: Joueurs en ligne shows real player data, Serveur info shows version, Builds Paper shows real build number, col 3 has Liens + Releases
- [ ] Browser `/media`: Requêtes Seerr visible on col 3 with poster thumbnails

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3 : Watch CI**

```bash
gh pr checks --watch --interval 20
```

Expected : flux-local checks green. Trivy may still fail with the known install flake from prior PRs — not blocking.

### Task 9 : Merge

**Files:** none

- [ ] **Step 1 : Squash merge**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 2 : Sync local main**

```bash
git checkout main
git fetch origin
git reset --hard origin/main
```

---

## Phase 5 : Post-merge verification

### Task 10 : Reconcile + force-sync + verify

**Files:** none

- [ ] **Step 1 : Reconcile Flux**

```bash
flux reconcile source git flux-system
flux reconcile kustomization crafty -n games
flux reconcile kustomization dynacat -n selfhosted
```

Expected : all reconciles succeed.

- [ ] **Step 2 : Force-sync ExternalSecret to pull new CRAFTY_API_TOKEN**

```bash
kubectl -n selfhosted annotate externalsecret dynacat force-sync=$(date +%s) --overwrite
sleep 5
kubectl -n selfhosted get secret dynacat-secret -o jsonpath='{.data}' | jq 'keys'
```

Expected : secret keys list includes `CRAFTY_API_TOKEN` alongside the existing 10 keys.

- [ ] **Step 3 : Wait for pod rollout**

```bash
kubectl -n selfhosted rollout status deploy/dynacat --timeout=120s
```

Expected : new pod 1/1 Running.

- [ ] **Step 4 : Test Crafty API reach from dynacat pod (proves CNP works)**

```bash
TOKEN=$(kubectl -n selfhosted get secret dynacat-secret -o jsonpath='{.data.CRAFTY_API_TOKEN}' | base64 -d)
kubectl -n selfhosted exec deploy/dynacat -- wget -qS -O /dev/null --timeout=5 \
  --header="Authorization: Bearer $TOKEN" \
  "http://crafty-app.games.svc.cluster.local:8000/api/v2/servers/51ebc4d3-9008-42ee-8de6-c3b347fc701f/stats" 2>&1 | grep HTTP | head -2
```

Expected : `HTTP/1.1 200 OK`. If 401 → token scope insufficient ; if 403 → CNP didn't apply yet ; if timeout → CNP issue or wrong port.

- [ ] **Step 5 : Browser verification**

Open in browser :
- `https://home.kryzql.space/` — no Infrastructure block on col 1 (just per-node metrics + UPS + NAS HDD), Hacker News widget on col 2, Météo + Liens on col 3
- `https://home.kryzql.space/media` — Requêtes Seerr now on col 3
- `https://home.kryzql.space/games` — Joueurs en ligne + Serveur info widgets on col 2 with real data, Liens + Releases on col 3, Builds Paper shows real build number (not #0)

---

## Rollback

If the dashboard breaks badly post-merge :

```bash
git revert <merge-sha>
git push
flux reconcile kustomization dynacat -n selfhosted
```

Reloader rolls the pod back to the previous configmap within 1 minute. The CNP patch (Task 1) is harmless on rollback — having an extra ingress rule that no pod matches anymore is a no-op. The ExternalSecret with CRAFTY_API_TOKEN would also no-op (key present but unused). For cleanest revert, run the full revert ; for a minimal revert of just configmap, manually `git revert` only Task 6's commit.

## Follow-ups (not blockers)

- Emby + Audiobookshelf pod-level fix (currently `ContainerCreating` — probable Ceph stale-volume like Grafana had). Separate ticket.
- BlueMap deployment + col 2 embed on Games page (deferred — would need new HelmRelease).
- iCal calendar widget on Home (needs source). Deferred.
- Bibliothèque "Chargement..." auto-recovers once Emby pods come back (the widget itself is correct, the inline JS just can't fetch when Emby is 503).
