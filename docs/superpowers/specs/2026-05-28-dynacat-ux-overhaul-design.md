# Dynacat UX Overhaul — Design

**Date** : 2026-05-28
**Scope** : intent-driven restructure of pages `home`, `media`, `games` (page `stats` untouched — already redesigned)
**Trigger** : 4 screenshots reviewed by user revealed broken widgets across pages, asymmetric column densities, redundant blocks (Infra duplicated between Home and Stats), and entire empty column on Games

## 1. Purpose

Restructure the 3 non-stats Dynacat pages around clear usage intents, fix every broken widget visible on the dashboard, and remove redundancy between pages. The result : each page answers one clear operator question.

| Page | Intent (the question the page answers) |
|------|----------------------------------------|
| `home` | "Quoi maintenant — météo, accès rapides, état général" |
| `media` | "Quoi regarder, écouter, ou demander" |
| `stats` | "Comment va le cluster" (unchanged) |
| `games` | "Quel est l'état du serveur Minecraft" |

User's framing : *"rends ça plus simple à naviguer"*. The implementation respects existing widget content where it works and only removes / replaces what duplicates other pages or is permanently broken.

## 2. Scope

**In scope**
- Configmap edits to `selfhosted/dynacat/app/configmap.yaml` for pages home/media/games
- New ExternalSecret key `CRAFTY_API_TOKEN` pulled from 1P item `crafty` (already populated by user)
- New CiliumNetworkPolicy patch to allow dynacat → crafty-app:8443
- Fix probe URLs on Emby + Audiobookshelf using `check-url` pattern (same approach validated for Gatus in PR #181)
- Replace permanently-broken Reddit widget with built-in Hacker News widget
- Fix the `#0`-placeholder Builds Paper widget (PaperMC API)
- Investigate and fix all "Chargement..." stuck widgets on Media (Bibliothèque, Prochains épisodes, Films à venir)

**Out of scope**
- Page `stats` (recently overhauled, working correctly)
- Deploying BlueMap (not in the cluster — was considered for Games col 2 but defer)
- iCal/calendar widget on Home (would need an iCal source, defer)
- LibreSpeed widget on Home (would need new deploy, defer)
- Fixing Emby/ABS pod-level issues (currently `ContainerCreating`, separate operational concern)

## 3. Page architectures

### 3.1 Home — landing daily

Current 3-col structure is kept; widgets are pruned for duplication and replaced where broken.

```
┌─ Col 1 (size: small) ─────┐  ┌─ Col 2 (size: full) ───────┐  ┌─ Col 3 (size: small) ──┐
│ INFRA (per-node metrics)  │  │ SEARCH bar                  │  │ MÉTÉO (XL, kept)        │
│  - node01/02/03/NAS       │  │                             │  │                         │
│  - UPS, NAS HDD           │  │ MEDIA monitor               │  │ LIENS RAPIDES (kept)    │
│                           │  │  - Emby   (check-url fix)   │  │  - Infrastructure       │
│                           │  │  - ABS    (check-url fix)   │  │  - Médias               │
│                           │  │                             │  │                         │
│                           │  │ HACKER NEWS top 10          │  │                         │
│                           │  │  (replaces broken Reddit)   │  │                         │
└───────────────────────────┘  └─────────────────────────────┘  └─────────────────────────┘
```

**Edits to apply** :
- **Remove** the `monitor` widget titled `Infrastructure` on home col 1 (Grafana/Prometheus/TrueNAS/Gatus) — duplicate with stats Infra subgroup, keep only the per-node metrics widgets.
- **Replace** the `reddit` widget on home col 2 with a built-in `hacker-news` widget : `type: hacker-news, limit: 10, update-interval: 30m`. No auth required.
- **Fix Emby probe** : on the existing monitor entry for Emby, add `check-url: http://emby.media.svc.cluster.local:8096` while keeping `url: https://emby.${SECRET_DOMAIN}` for the click target. Emby's internal HTTP port is **8096** (LoadBalancer type, see `kubectl -n media get svc emby`).
- **Fix Audiobookshelf probe** : add `check-url: http://audiobookshelf.media.svc.cluster.local` (port 80 by default for the ABS ClusterIP).

Note : Emby and ABS pods are currently `ContainerCreating` (probable Ceph stale-volume issue like Grafana had). Once the pods are Ready, the new check-url probes will return 200. This PR fixes the probe URLs ; it does NOT fix the underlying pod state.

### 3.2 Media — consume content

Restructured to a hero layout with the latest-Emby carousel as the focal point.

```
┌─ Col 1 (size: small) ─────┐  ┌─ Col 2 (size: full) ───────┐  ┌─ Col 3 (size: small) ──┐
│ NOW PLAYING (consolidated)│  │ DERNIÈREMENT AJOUTÉ EMBY    │  │ REQUÊTES SEERR (moved   │
│  custom-api widget that   │  │  Hero carousel of posters    │  │  here from col 1)       │
│  queries Emby Sessions    │  │  (Emby /Items?SortBy=DateCre │  │  - all current Seerr    │
│  + Navidrome NowPlaying   │  │   ated&Limit=12, big posters)│  │    entries with poster, │
│  + ABS listening-sessions │  │                              │  │    status, requester    │
│  Shows first active or    │  │ BIBLIOTHÈQUE STATS (compact) │  │                         │
│  "Aucune lecture"         │  │  10 Films · 6 Séries · 214   │  │ PROCHAINS ÉPISODES      │
│                           │  │  Épisodes · ? Morceaux       │  │  (Sonarr /api/v3/       │
│ DOWNLOADS QUEUE (kept)    │  │  (compact 1-line, no more    │  │   calendar?start=...)   │
│  glance-dlq, the existing │  │   "Chargement...")           │  │  next 7 days            │
│  Radarr+Sonarr+Readarr    │  │                              │  │                         │
│  combined dlq widget      │  │                              │  │ FILMS À VENIR           │
│                           │  │                              │  │  (Radarr /api/v3/       │
│                           │  │                              │  │   calendar?start=...)   │
│                           │  │                              │  │  next 30 days           │
└───────────────────────────┘  └─────────────────────────────┘  └─────────────────────────┘
```

**Edits to apply** :
- **Consolidate** the three current "Now playing" entries (Lecture en cours / Musique en cours / partial ABS) into one custom-api widget on col 1. Template iterates [Emby, Navidrome, ABS] internally and shows the first active session, or "Aucune lecture" if none.
- **Move** the existing "Requêtes Seerr" widget (currently col 1, big) from col 1 → col 3. The HTML+JS template is kept verbatim.
- **New** : a dedicated "Dernièrement ajouté Emby" custom-api widget on col 2 — pulls Emby `/Items?SortBy=DateCreated&SortOrder=Descending&IncludeItemTypes=Movie,Series&Limit=12` and renders poster thumbnails as a horizontal scroll. Reuses the JS code from the existing `glance-lib` widget (which already does this inline) — just extracted as a standalone widget so it gets its own widget chrome.
- **Fix "Chargement..." widgets** :
  - *Bibliothèque stats* — investigate at impl time. The widget likely queries Emby `/Items/Counts?api_key=...`. If the call returns 401 or shape changed, fix headers / template. Compact to a 1-line stats display.
  - *Prochains épisodes* — fix Sonarr `/api/v3/calendar?start=now&end=+7d&apikey=$${SONARR_API_KEY}`.
  - *Films à venir* — fix Radarr `/api/v3/calendar?start=now&end=+30d&apikey=$${RADARR_API_KEY}`.
- **Remove** : nothing removed. Just reorganized.

### 3.3 Games — gaming session

Fills the empty col 3, replaces the broken Builds Paper widget, adds live server data from Crafty API.

```
┌─ Col 1 (size: small) ─────┐  ┌─ Col 2 (size: full) ───────┐  ┌─ Col 3 (size: small) ──┐
│ PANNEAUX                  │  │ JOUEURS EN LIGNE             │  │ LIENS (kept, moved      │
│  - Crafty Controller ✓    │  │  (Crafty API                 │  │  here from col 2)       │
│                           │  │   /api/v2/servers/<uuid>/    │  │  - Administration       │
│ CONNEXION (kept)          │  │   players)                   │  │  - Plugins & mods       │
│  - Server, version, etc.  │  │  Shows live player list +    │  │  - Docs                 │
│                           │  │  count (e.g., "2/20 online") │  │                         │
│ BUILD PAPER (fixed)       │  │                              │  │ RELEASES PLUGINS (moved │
│  - Latest PaperMC build   │  │ SERVEUR INFO                 │  │  here from col 2)       │
│    from PaperMC API       │  │  (Crafty API                 │  │  - ViaVersion, BlueMap, │
│  - was "#0" placeholder   │  │   /api/v2/servers/<uuid>/    │  │    romm, etc.           │
│                           │  │   stats)                     │  │                         │
│                           │  │  Uptime, version, plugins #, │  │                         │
│                           │  │  MOTD                        │  │                         │
└───────────────────────────┘  └─────────────────────────────┘  └─────────────────────────┘
```

**Edits to apply** :
- **New col 2 main content** : 2 new custom-api widgets calling Crafty API.
  - *Joueurs en ligne* : `GET https://crafty-app.games.svc.cluster.local:8443/api/v2/servers/<server-uuid>/players` with `Authorization: Bearer $${CRAFTY_API_TOKEN}`. Template renders connected players list + count.
  - *Serveur info* : `GET .../api/v2/servers/<server-uuid>/stats`. Renders uptime, version, plugin count, MOTD.
  - The `<server-uuid>` placeholder is resolved at implementation time via `kubectl -n games exec crafty-0 -- ls /crafty/servers/` (the directory name = the server UUID). Hard-code it in the configmap.
- **Fix Builds Paper widget** : currently shows `#0` placeholder. Investigate at impl time. Likely a `custom-api` querying `https://api.papermc.io/v2/projects/paper/versions/1.21.11/builds` and a template field that returns 0 when the JSON path is wrong. Fix the template's `.JSON.Array "builds"` lookup or equivalent.
- **Move** the existing "Liens" (Administration / Plugins / Docs) and "Releases plugins" (ViaVersion, BlueMap, romm, etc.) widgets from col 2 → col 3. They're secondary to the live server state and were leaving col 3 empty before.

## 4. New secret + CNP

### 4.1 ExternalSecret addition

Append to `kubernetes/apps/selfhosted/dynacat/app/externalsecret.yaml` `spec.data` list :

```yaml
- secretKey: CRAFTY_API_TOKEN
  remoteRef:
    key: crafty
    property: api_token
```

The 1P item `crafty` in vault `kubernetes` (id `ak22rtzezdl2mczlxrxu3tld6e`) already has the `api_token` field populated with a PLAYERS-scope token created by the operator via Crafty UI.

### 4.2 CiliumNetworkPolicy patch

The widget needs egress from dynacat (selfhosted ns) to crafty-app (games ns) on TCP 8443. Two paths :

a. If `kubernetes/apps/games/crafty/app/ciliumnetworkpolicy.yaml` exists, append a `fromEndpoints` entry for `selfhosted/dynacat` to the ingress rule covering port 8443.

b. If no CNP exists for crafty, create one mirroring the structure of `kubernetes/apps/default/tandoor/app/ciliumnetworkpolicy.yaml` with selectors for crafty + ingress from `selfhosted/dynacat` on port 8443.

Implementer checks at task start which case applies via `ls kubernetes/apps/games/crafty/app/`.

## 5. Implementation order

Single PR with multiple commits :
1. Add new CNP for crafty (or patch existing) — additive, no risk
2. Add new ExternalSecret key + restart trigger
3. Configmap edits (Home + Media + Games) in one commit (mostly mechanical)
4. Local docker smoke test (same pattern used for prior PRs)
5. Push, PR, CI green, merge

## 6. Investigations required at implementation time

Listed explicitly so the implementer subagent has them in its task list :

| Investigation | Where | Output needed |
|--------------|-------|---------------|
| Crafty server UUID | `kubectl -n games exec crafty-0 -- ls /crafty/servers/` | UUID string, hard-coded in configmap URLs |
| Bibliothèque widget current state | `yq eval '.data."dynacat.yml" \| from_yaml \| .pages[1].columns[1].widgets[0]' configmap.yaml` | Whatever's there now, then craft fix |
| Prochains épisodes current state | Find on page `media` col 3 | Same |
| Films à venir current state | Find on page `media` col 3 | Same |
| Builds Paper current state | Page `games` | Same |

The Bibliothèque, Prochains épisodes, Films à venir, and Builds Paper fixes are "diagnose and fix in place" — exact YAML depends on what's currently broken. Implementer subagent inspects the current widget, identifies the bug (likely template helper / API URL / auth header), produces minimal fix.

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Crafty API token revoked / wrong scope | Spec specifies PLAYERS scope; if widget fails 401/403, rotate via Crafty UI |
| Crafty server UUID changes | Hardcoded in configmap; if user recreates the server, manual configmap edit needed (acceptable for single-server homelab) |
| Emby/ABS still down (pod issue) at merge time | Probe will continue to fail until pods recover; this PR is correct regardless; pod fix is separate |
| Hacker News widget rate limits | None expected — public read API with generous limits |
| Now-playing widget too complex (3 sources unified) | Fallback : implementer can split into 3 separate compact widgets if the unified template proves unwieldy |
| Crafty API URL HTTPS self-signed cert | Crafty exposes self-signed cert on 8443. Dynacat's custom-api may need to be configured to skip TLS verify (Dynacat's `custom-api` widget has `allow-insecure-tls: true` per docs — verify at impl time) |
| "Chargement..." widgets fixes are open-ended | If a fix proves blocked (e.g., API auth missing entirely), the widget is dropped from this PR and tracked separately |

## 8. Bootstrap order (post-merge)

1. Force-sync ExternalSecret `dynacat` so the new `CRAFTY_API_TOKEN` propagates : `kubectl -n selfhosted annotate externalsecret dynacat force-sync=$(date +%s) --overwrite`
2. Reloader detects the secret change → pod auto-rolls
3. Browser refresh `https://home.kryzql.space/`, `/media`, `/games`
4. Verify each page renders new layout, no widget errors

## 9. Hors scope / Follow-ups

- BlueMap deploy + embed widget on Games col 2 (deferred — would need new HelmRelease)
- iCal calendar widget on Home (needs source)
- Mobile-responsive layout tweaks (Dynacat handles natively; verify if needed)
- Replace single per-page colors / kitten logo with consistent branding (cosmetic, can be a separate PR)
