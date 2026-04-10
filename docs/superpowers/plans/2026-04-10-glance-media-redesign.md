# Glance Media Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer l'unique onglet "media" de Glance par 5 onglets dédiés (Media, Films, Séries, Animés, Livres), chacun avec un layout 3 colonnes (small | full | small) dont le contenu est spécifique à la catégorie.

**Architecture:** Le fichier `configmap.yaml` contient le `glance.yml` complet en tant que valeur de clé ConfigMap. On remplace le bloc de l'onglet `media` (lignes ~205–408) par 5 blocs `- name: ...` distincts. L'onglet Livres nécessite une clé API Audiobookshelf ajoutée à l'ExternalSecret. Les templates JavaScript de recherche TMDB existants sont réutilisés et assignés à chaque onglet.

**Tech Stack:** Glance custom-api widget, Go templates, TMDB API, Emby API, Radarr/Sonarr/Readarr APIs, Audiobookshelf API, Kubernetes ConfigMap + ExternalSecret (External Secrets Operator, 1Password)

---

## Files

| Fichier | Action |
|---------|--------|
| `kubernetes/apps/selfhosted/glance/app/configmap.yaml` | Modifier — remplacer l'onglet media (lignes ~205–408) par 5 onglets |
| `kubernetes/apps/selfhosted/glance/app/externalsecret.yaml` | Modifier — ajouter `ABS_TOKEN` pour Audiobookshelf |

---

## Prerequisite (manuel)

Avant de commencer, ajouter dans 1Password un item `audiobookshelf` avec la propriété `token` contenant le token API Audiobookshelf (Settings → Users → API Token dans l'interface ABS).

---

## Task 1: Ajouter ABS_TOKEN à l'ExternalSecret

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/externalsecret.yaml`

- [ ] **Step 1: Ajouter l'entrée ABS_TOKEN**

Dans `externalsecret.yaml`, ajouter après l'entrée `READARR_API_KEY` :

```yaml
    - secretKey: ABS_TOKEN
      remoteRef:
        key: audiobookshelf
        property: token
```

Le fichier complet doit ressembler à :

```yaml
---
# yaml-language-server: $schema=https://k8s-schemas.bjw-s.dev/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: glance
spec:
  refreshInterval: 12h
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: glance-secret
    creationPolicy: Owner
  data:
    - secretKey: RADARR_API_KEY
      remoteRef:
        key: radarr
        property: api_key
    - secretKey: SONARR_API_KEY
      remoteRef:
        key: sonarr
        property: api_key
    - secretKey: TMDB_API_KEY
      remoteRef:
        key: tmdb
        property: api_key
    - secretKey: EMBY_API_KEY
      remoteRef:
        key: emby
        property: glance_api_key
    - secretKey: READARR_API_KEY
      remoteRef:
        key: readarr
        property: api_key
    - secretKey: ABS_TOKEN
      remoteRef:
        key: audiobookshelf
        property: token
```

- [ ] **Step 2: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/externalsecret.yaml
git commit -m "feat(glance): add Audiobookshelf token to externalsecret"
```

---

## Task 2: Onglet Media (vue générale)

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

Remplacer le bloc :
```
      # ── Media ──────────────────────────────────────────────────────────────
      - name: media
        ...
```
jusqu'à (non inclus) :
```
      # ── Stats ──────────────────────────────────────────────────────────────
```

Par les 5 nouveaux onglets (Tasks 2–6). Cette tâche crée uniquement l'onglet `media` (vue générale).

- [ ] **Step 1: Remplacer le bloc media dans configmap.yaml**

Supprimer tout le contenu entre `# ── Media ──` et `# ── Stats ──` (non inclus), et le remplacer par :

```yaml
      # ── Media ──────────────────────────────────────────────────────────────
      - name: media
        columns:
          - size: small
            widgets:
              - type: custom-api
                title: Lecture en cours
                allow-insecure-html: true
                cache: 30s
                url: "http://emby.media.svc.cluster.local:8096/Sessions?ActiveWithinSeconds=300&api_key=$${EMBY_API_KEY}"
                template: |
                  {{$any := false}}
                  <div style="display:flex;flex-direction:column;gap:8px">
                  {{range .JSON.Array "@this"}}
                  {{if (.String "NowPlayingItem.Name")}}
                  {{$any = true}}
                  {{$paused := eq (.String "PlayState.IsPaused") "true"}}
                  {{$h := .Int "NowPlayingItem.Height"}}
                  <div style="display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(0,0,0,.06);border-radius:6px">
                    <img src="https://emby.${SECRET_DOMAIN}/Items/{{if (.String "NowPlayingItem.SeriesId")}}{{.String "NowPlayingItem.SeriesId"}}{{else}}{{.String "NowPlayingItem.Id"}}{{end}}/Images/Primary?maxHeight=100&api_key=$${EMBY_API_KEY}" style="width:45px;min-width:45px;height:67px;object-fit:cover;border-radius:4px;flex-shrink:0">
                    <div style="min-width:0;flex:1">
                      <div style="font-weight:700;font-size:.9em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{if $paused}}<span style="color:#f59e0b">●</span>{{else}}<span style="color:#22c55e">●</span>{{end}} {{if (.String "NowPlayingItem.SeriesName")}}{{.String "NowPlayingItem.SeriesName"}}{{else}}{{.String "NowPlayingItem.Name"}}{{end}}</div>
                      {{if (.String "NowPlayingItem.SeriesName")}}<div style="font-size:.75em;opacity:.7;margin-top:2px">{{printf "S%02dE%02d" (.Int "NowPlayingItem.ParentIndexNumber") (.Int "NowPlayingItem.IndexNumber")}} · {{.String "NowPlayingItem.Name"}}</div>{{end}}
                      <div style="font-size:.75em;opacity:.65;margin-top:2px">{{if (.String "NowPlayingItem.SeriesName")}}TV{{else}}Film{{end}} · {{if gt $h 2000}}4K{{else if gt $h 1000}}1080p{{else if gt $h 680}}720p{{else}}SD{{end}} · {{.String "PlayState.PlayMethod"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:1px">👤 {{.String "UserName"}} · {{.String "Client"}} ({{.String "DeviceName"}})</div>
                      <div style="font-size:.75em;font-weight:600;margin-top:3px">{{if $paused}}⏸ En pause{{else}}▶ En lecture{{end}}</div>
                    </div>
                  </div>
                  {{end}}
                  {{end}}
                  </div>

              - type: bookmarks
                title: Liens rapides
                groups:
                  - title: Media
                    links:
                      - title: Emby
                        url: https://emby.${SECRET_DOMAIN}
                        icon: di:emby
                      - title: Audiobookshelf
                        url: https://audiobookshelf.${SECRET_DOMAIN}
                        icon: di:audiobookshelf
                      - title: Radarr
                        url: https://radarr.${SECRET_DOMAIN}
                        icon: di:radarr
                      - title: Sonarr
                        url: https://sonarr.${SECRET_DOMAIN}
                        icon: di:sonarr
                      - title: Readarr
                        url: https://readarr.${SECRET_DOMAIN}
                        icon: di:readarr

          - size: full
            widgets:
              - type: group
                widgets:
                  - type: custom-api
                    title: Queue Radarr
                    allow-insecure-html: true
                    cache: 30s
                    url: "http://radarr.downloads.svc.cluster.local:7878/api/v3/queue?apikey=$${RADARR_API_KEY}&pageSize=10"
                    template: |
                      {{$records := .JSON.Array "records"}}
                      {{if eq (len $records) 0}}
                      <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                      {{else}}
                      <div style="display:flex;flex-direction:column;gap:4px">
                      {{range $records}}
                      <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                        <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                        <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                      </div>
                      {{end}}
                      </div>
                      {{end}}

                  - type: custom-api
                    title: Queue Sonarr
                    allow-insecure-html: true
                    cache: 30s
                    url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/queue?apikey=$${SONARR_API_KEY}&pageSize=10"
                    template: |
                      {{$records := .JSON.Array "records"}}
                      {{if eq (len $records) 0}}
                      <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                      {{else}}
                      <div style="display:flex;flex-direction:column;gap:4px">
                      {{range $records}}
                      <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                        <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                        <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                      </div>
                      {{end}}
                      </div>
                      {{end}}

          - size: small
            widgets:
              - type: custom-api
                title: Épisodes à venir
                allow-insecure-html: true
                cache: 30m
                url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/calendar?start=2025-01-01&end=2027-12-31&apikey=$${SONARR_API_KEY}&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/series" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://sonarr.${SECRET_DOMAIN}/MediaCover/{{.Int "seriesId"}}/poster.jpg?apikey=$${SONARR_API_KEY}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$au := .String "airDateUtc"}}<div style="font-size:.7em;opacity:.65">{{printf "S%02dE%02d" (.Int "seasonNumber") (.Int "episodeNumber")}} · {{slice $au 8 10}}-{{slice $au 5 7}}-{{slice $au 0 4}}</div>
                      {{if eq (.String "hasFile") "true"}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Dispo</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Manquant</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

              - type: custom-api
                title: Films attendus
                allow-insecure-html: true
                cache: 30m
                url: "http://radarr.downloads.svc.cluster.local:7878/api/v3/calendar?start=2025-01-01&end=2027-12-31&apikey=$${RADARR_API_KEY}&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://radarr.${SECRET_DOMAIN}/add/new?term={{.String "title"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="{{.String "images.#[coverType==poster].remoteUrl"}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$ic := .String "inCinemas"}}<div style="font-size:.7em;opacity:.65">{{slice $ic 8 10}}-{{slice $ic 5 7}}-{{slice $ic 0 4}}</div>
                      {{if eq (.String "hasFile") "true"}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Téléchargé</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Manquant</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

```

- [ ] **Step 2: Vérifier la syntaxe YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): replace media tab with overview (small|full|small)"
```

---

## Task 3: Onglet Films

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

- [ ] **Step 1: Ajouter l'onglet Films après l'onglet media**

Insérer après la fin du bloc `- name: media` (juste avant `# ── Stats ──`) :

```yaml
      # ── Films ──────────────────────────────────────────────────────────────
      - name: films
        columns:
          - size: small
            widgets:
              - type: custom-api
                title: Lecture en cours
                allow-insecure-html: true
                cache: 30s
                url: "http://emby.media.svc.cluster.local:8096/Sessions?ActiveWithinSeconds=300&api_key=$${EMBY_API_KEY}"
                template: |
                  {{$any := false}}
                  <div style="display:flex;flex-direction:column;gap:8px">
                  {{range .JSON.Array "@this"}}
                  {{if (.String "NowPlayingItem.Name")}}
                  {{$any = true}}
                  {{$paused := eq (.String "PlayState.IsPaused") "true"}}
                  {{$h := .Int "NowPlayingItem.Height"}}
                  <div style="display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(0,0,0,.06);border-radius:6px">
                    <img src="https://emby.${SECRET_DOMAIN}/Items/{{if (.String "NowPlayingItem.SeriesId")}}{{.String "NowPlayingItem.SeriesId"}}{{else}}{{.String "NowPlayingItem.Id"}}{{end}}/Images/Primary?maxHeight=100&api_key=$${EMBY_API_KEY}" style="width:45px;min-width:45px;height:67px;object-fit:cover;border-radius:4px;flex-shrink:0">
                    <div style="min-width:0;flex:1">
                      <div style="font-weight:700;font-size:.9em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{if $paused}}<span style="color:#f59e0b">●</span>{{else}}<span style="color:#22c55e">●</span>{{end}} {{if (.String "NowPlayingItem.SeriesName")}}{{.String "NowPlayingItem.SeriesName"}}{{else}}{{.String "NowPlayingItem.Name"}}{{end}}</div>
                      {{if (.String "NowPlayingItem.SeriesName")}}<div style="font-size:.75em;opacity:.7;margin-top:2px">{{printf "S%02dE%02d" (.Int "NowPlayingItem.ParentIndexNumber") (.Int "NowPlayingItem.IndexNumber")}} · {{.String "NowPlayingItem.Name"}}</div>{{end}}
                      <div style="font-size:.75em;opacity:.65;margin-top:2px">{{if (.String "NowPlayingItem.SeriesName")}}TV{{else}}Film{{end}} · {{if gt $h 2000}}4K{{else if gt $h 1000}}1080p{{else if gt $h 680}}720p{{else}}SD{{end}} · {{.String "PlayState.PlayMethod"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:1px">👤 {{.String "UserName"}} · {{.String "Client"}} ({{.String "DeviceName"}})</div>
                      <div style="font-size:.75em;font-weight:600;margin-top:3px">{{if $paused}}⏸ En pause{{else}}▶ En lecture{{end}}</div>
                    </div>
                  </div>
                  {{end}}
                  {{end}}
                  </div>

              - type: custom-api
                title: Téléchargements
                allow-insecure-html: true
                cache: 30s
                url: "http://radarr.downloads.svc.cluster.local:7878/api/v3/queue?apikey=$${RADARR_API_KEY}&pageSize=8"
                template: |
                  {{$records := .JSON.Array "records"}}
                  {{if eq (len $records) 0}}
                  <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $records}}
                  <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                    <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                    <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                  </div>
                  {{end}}
                  </div>
                  {{end}}

              - type: bookmarks
                title: Liens
                groups:
                  - title: Films
                    links:
                      - title: Radarr
                        url: https://radarr.${SECRET_DOMAIN}
                        icon: di:radarr
                      - title: Emby
                        url: https://emby.${SECRET_DOMAIN}
                        icon: di:emby

          - size: full
            widgets:
              - type: custom-api
                title: Films en salle
                allow-insecure-html: true
                cache: 1h
                url: "https://api.themoviedb.org/3/movie/now_playing?api_key=$${TMDB_API_KEY}&language=fr-FR&region=FR"
                template: |
                  <div id="glance-fsk" data-k="$${TMDB_API_KEY}" data-d="${SECRET_DOMAIN}" onclick="(function(e){var q=document.getElementById('glance-fsq').value.trim(),a=e.dataset.k,d=e.dataset.d;if(!q)return;fetch('https://api.themoviedb.org/3/search/movie?api_key='+a+'&query='+encodeURIComponent(q)+'&language=fr-FR').then(function(r){return r.json()}).then(function(data){var h='<div style=\'display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px\'>';data.results.forEach(function(m){var img=m.poster_path?'<img src=\'https://image.tmdb.org/t/p/w92'+m.poster_path+'\' style=\'width:100%;aspect-ratio:2/3;object-fit:cover\'>':'<div style=\'width:100%;aspect-ratio:2/3;background:rgba(0,0,0,.1)\'></div>';h+='<a href=\'https://radarr.'+d+'/add/new?term='+encodeURIComponent(m.title)+'\' target=\'_blank\' style=\'text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)\' onmouseover=\'this.style.opacity=.75\' onmouseout=\'this.style.opacity=1\'>'+img+'<div style=\'padding:8px\'><div style=\'font-weight:600;font-size:.85em;line-height:1.2\'>'+m.title+'</div><div style=\'font-size:.75em;opacity:.65;margin-top:3px\'>'+(m.release_date||'')+'</div><div style=\'font-size:.75em;margin-top:3px\'>⭐ '+(m.vote_average?m.vote_average.toFixed(1):'?')+'</div></div></a>';});h+='</div>';document.getElementById('glance-fsr').innerHTML=h;document.getElementById('glance-fsr').style.display='';document.getElementById('glance-fsd').style.display='none';});})(this)" style="display:none"></div>
                  <div style="display:flex;gap:8px;margin-bottom:12px">
                    <input id="glance-fsq" placeholder="Rechercher un film..." onkeydown="if(event.key==='Enter')document.getElementById('glance-fsk').click()" style="flex:1;padding:6px 10px;border-radius:6px;border:1px solid rgba(0,0,0,.2);background:rgba(0,0,0,.05);font-size:.9em">
                    <button onclick="document.getElementById('glance-fsk').click()" style="padding:6px 14px;border-radius:6px;background:rgba(0,0,0,.1);border:none;cursor:pointer;font-size:.9em">→</button>
                    <button onclick="document.getElementById('glance-fsq').value='';document.getElementById('glance-fsr').style.display='none';document.getElementById('glance-fsd').style.display=''" style="padding:6px 10px;border-radius:6px;background:rgba(0,0,0,.06);border:none;cursor:pointer;font-size:.9em;opacity:.6">✕</button>
                  </div>
                  <div id="glance-fsr" style="display:none"></div>
                  <div id="glance-fsd">
                  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px">
                  {{range .JSON.Array "results"}}
                  <a href="https://radarr.${SECRET_DOMAIN}/add/new?term={{.String "title"}}" target="_blank" style="text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:100%;aspect-ratio:2/3;object-fit:cover">
                    <div style="padding:8px">
                      <div style="font-weight:600;font-size:.85em;line-height:1.2">{{.String "title"}}</div>
                      {{$rd := .String "release_date"}}<div style="font-size:.75em;opacity:.65;margin-top:3px">{{slice $rd 8 10}}-{{slice $rd 5 7}}-{{slice $rd 0 4}}</div>
                      <div style="font-size:.75em;margin-top:3px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>
                  </div>

          - size: small
            widgets:
              - type: custom-api
                title: Watchlist Radarr
                allow-insecure-html: true
                cache: 30m
                url: "http://radarr.downloads.svc.cluster.local:7878/api/v3/calendar?start=2025-01-01&end=2027-12-31&apikey=$${RADARR_API_KEY}&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://radarr.${SECRET_DOMAIN}/add/new?term={{.String "title"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="{{.String "images.#[coverType==poster].remoteUrl"}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$ic := .String "inCinemas"}}<div style="font-size:.7em;opacity:.65;margin-top:2px">{{slice $ic 8 10}}-{{slice $ic 5 7}}-{{slice $ic 0 4}}</div>
                      {{if eq (.String "hasFile") "true"}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Téléchargé</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Manquant</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

              - type: custom-api
                title: Sorties films (FR)
                allow-insecure-html: true
                cache: 6h
                url: "https://api.themoviedb.org/3/discover/movie?api_key=$${TMDB_API_KEY}&language=fr-FR&region=FR&sort_by=release_date.asc&release_date.gte=2026-04-01&release_date.lte=2027-12-31&with_release_type=2%7C3&primary_release_date.gte=2023-01-01&vote_count.gte=10"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "results"}}
                  <a href="https://radarr.${SECRET_DOMAIN}/add/new?term={{.String "title"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$rd := .String "release_date"}}<div style="font-size:.7em;opacity:.65;margin-top:2px">{{slice $rd 8 10}}-{{slice $rd 5 7}}-{{slice $rd 0 4}}</div>
                      <div style="font-size:.7em;margin-top:2px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>

```

- [ ] **Step 2: Vérifier la syntaxe YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): add Films tab (small|full|small)"
```

---

## Task 4: Onglet Séries

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

- [ ] **Step 1: Ajouter l'onglet Séries après l'onglet films**

Insérer après la fin du bloc `- name: films` (juste avant `# ── Stats ──`) :

```yaml
      # ── Séries ─────────────────────────────────────────────────────────────
      - name: séries
        columns:
          - size: small
            widgets:
              - type: custom-api
                title: Lecture en cours
                allow-insecure-html: true
                cache: 30s
                url: "http://emby.media.svc.cluster.local:8096/Sessions?ActiveWithinSeconds=300&api_key=$${EMBY_API_KEY}"
                template: |
                  {{$any := false}}
                  <div style="display:flex;flex-direction:column;gap:8px">
                  {{range .JSON.Array "@this"}}
                  {{if (.String "NowPlayingItem.Name")}}
                  {{$any = true}}
                  {{$paused := eq (.String "PlayState.IsPaused") "true"}}
                  {{$h := .Int "NowPlayingItem.Height"}}
                  <div style="display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(0,0,0,.06);border-radius:6px">
                    <img src="https://emby.${SECRET_DOMAIN}/Items/{{if (.String "NowPlayingItem.SeriesId")}}{{.String "NowPlayingItem.SeriesId"}}{{else}}{{.String "NowPlayingItem.Id"}}{{end}}/Images/Primary?maxHeight=100&api_key=$${EMBY_API_KEY}" style="width:45px;min-width:45px;height:67px;object-fit:cover;border-radius:4px;flex-shrink:0">
                    <div style="min-width:0;flex:1">
                      <div style="font-weight:700;font-size:.9em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{if $paused}}<span style="color:#f59e0b">●</span>{{else}}<span style="color:#22c55e">●</span>{{end}} {{if (.String "NowPlayingItem.SeriesName")}}{{.String "NowPlayingItem.SeriesName"}}{{else}}{{.String "NowPlayingItem.Name"}}{{end}}</div>
                      {{if (.String "NowPlayingItem.SeriesName")}}<div style="font-size:.75em;opacity:.7;margin-top:2px">{{printf "S%02dE%02d" (.Int "NowPlayingItem.ParentIndexNumber") (.Int "NowPlayingItem.IndexNumber")}} · {{.String "NowPlayingItem.Name"}}</div>{{end}}
                      <div style="font-size:.75em;opacity:.65;margin-top:2px">{{if (.String "NowPlayingItem.SeriesName")}}TV{{else}}Film{{end}} · {{if gt $h 2000}}4K{{else if gt $h 1000}}1080p{{else if gt $h 680}}720p{{else}}SD{{end}} · {{.String "PlayState.PlayMethod"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:1px">👤 {{.String "UserName"}} · {{.String "Client"}} ({{.String "DeviceName"}})</div>
                      <div style="font-size:.75em;font-weight:600;margin-top:3px">{{if $paused}}⏸ En pause{{else}}▶ En lecture{{end}}</div>
                    </div>
                  </div>
                  {{end}}
                  {{end}}
                  </div>

              - type: custom-api
                title: Téléchargements
                allow-insecure-html: true
                cache: 30s
                url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/queue?apikey=$${SONARR_API_KEY}&pageSize=8"
                template: |
                  {{$records := .JSON.Array "records"}}
                  {{if eq (len $records) 0}}
                  <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $records}}
                  <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                    <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                    <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                  </div>
                  {{end}}
                  </div>
                  {{end}}

              - type: bookmarks
                title: Liens
                groups:
                  - title: Séries
                    links:
                      - title: Sonarr
                        url: https://sonarr.${SECRET_DOMAIN}
                        icon: di:sonarr
                      - title: Emby
                        url: https://emby.${SECRET_DOMAIN}
                        icon: di:emby

          - size: full
            widgets:
              - type: custom-api
                title: Séries en cours
                allow-insecure-html: true
                cache: 1h
                url: "https://api.themoviedb.org/3/tv/on_the_air?api_key=$${TMDB_API_KEY}&language=fr-FR"
                template: |
                  <div id="glance-ssk" data-k="$${TMDB_API_KEY}" data-d="${SECRET_DOMAIN}" onclick="(function(e){var q=document.getElementById('glance-ssq').value.trim(),a=e.dataset.k,d=e.dataset.d;if(!q)return;fetch('https://api.themoviedb.org/3/search/tv?api_key='+a+'&query='+encodeURIComponent(q)+'&language=fr-FR').then(function(r){return r.json()}).then(function(data){var h='<div style=\'display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px\'>';data.results.forEach(function(m){var img=m.poster_path?'<img src=\'https://image.tmdb.org/t/p/w92'+m.poster_path+'\' style=\'width:100%;aspect-ratio:2/3;object-fit:cover\'>':'<div style=\'width:100%;aspect-ratio:2/3;background:rgba(0,0,0,.1)\'></div>';h+='<a href=\'https://sonarr.'+d+'/add/new?term='+encodeURIComponent(m.name)+'\' target=\'_blank\' style=\'text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)\' onmouseover=\'this.style.opacity=.75\' onmouseout=\'this.style.opacity=1\'>'+img+'<div style=\'padding:8px\'><div style=\'font-weight:600;font-size:.85em;line-height:1.2\'>'+m.name+'</div><div style=\'font-size:.75em;opacity:.65;margin-top:3px\'>'+(m.first_air_date||'')+'</div><div style=\'font-size:.75em;margin-top:3px\'>⭐ '+(m.vote_average?m.vote_average.toFixed(1):'?')+'</div></div></a>';});h+='</div>';document.getElementById('glance-ssr').innerHTML=h;document.getElementById('glance-ssr').style.display='';document.getElementById('glance-ssd').style.display='none';});})(this)" style="display:none"></div>
                  <div style="display:flex;gap:8px;margin-bottom:12px">
                    <input id="glance-ssq" placeholder="Rechercher une série..." onkeydown="if(event.key==='Enter')document.getElementById('glance-ssk').click()" style="flex:1;padding:6px 10px;border-radius:6px;border:1px solid rgba(0,0,0,.2);background:rgba(0,0,0,.05);font-size:.9em">
                    <button onclick="document.getElementById('glance-ssk').click()" style="padding:6px 14px;border-radius:6px;background:rgba(0,0,0,.1);border:none;cursor:pointer;font-size:.9em">→</button>
                    <button onclick="document.getElementById('glance-ssq').value='';document.getElementById('glance-ssr').style.display='none';document.getElementById('glance-ssd').style.display=''" style="padding:6px 10px;border-radius:6px;background:rgba(0,0,0,.06);border:none;cursor:pointer;font-size:.9em;opacity:.6">✕</button>
                  </div>
                  <div id="glance-ssr" style="display:none"></div>
                  <div id="glance-ssd">
                  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px">
                  {{range .JSON.Array "results"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/add/new?term={{.String "name"}}" target="_blank" style="text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:100%;aspect-ratio:2/3;object-fit:cover">
                    <div style="padding:8px">
                      <div style="font-weight:600;font-size:.85em;line-height:1.2">{{.String "name"}}</div>
                      {{$fad := .String "first_air_date"}}<div style="font-size:.75em;opacity:.65;margin-top:3px">{{slice $fad 8 10}}-{{slice $fad 5 7}}-{{slice $fad 0 4}}</div>
                      <div style="font-size:.75em;margin-top:3px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>
                  </div>

          - size: small
            widgets:
              - type: custom-api
                title: Épisodes à venir
                allow-insecure-html: true
                cache: 30m
                url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/calendar?start=2025-01-01&end=2027-12-31&apikey=$${SONARR_API_KEY}&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/series" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://sonarr.${SECRET_DOMAIN}/MediaCover/{{.Int "seriesId"}}/poster.jpg?apikey=$${SONARR_API_KEY}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$au := .String "airDateUtc"}}<div style="font-size:.7em;opacity:.65">{{printf "S%02dE%02d" (.Int "seasonNumber") (.Int "episodeNumber")}} · {{slice $au 8 10}}-{{slice $au 5 7}}-{{slice $au 0 4}}</div>
                      {{if eq (.String "hasFile") "true"}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Dispo</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Manquant</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

              - type: custom-api
                title: Sorties séries (FR)
                allow-insecure-html: true
                cache: 6h
                url: "https://api.themoviedb.org/3/discover/tv?api_key=$${TMDB_API_KEY}&language=fr-FR&watch_region=FR&sort_by=first_air_date.asc&first_air_date.gte=2026-01-01&first_air_date.lte=2027-12-31&with_type=2%7C4&with_original_language=fr%7Cen&vote_count.gte=10"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "results"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/add/new?term={{.String "name"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "name"}}</div>
                      {{$fad := .String "first_air_date"}}<div style="font-size:.7em;opacity:.65;margin-top:2px">{{slice $fad 8 10}}-{{slice $fad 5 7}}-{{slice $fad 0 4}}</div>
                      <div style="font-size:.7em;margin-top:2px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>

```

- [ ] **Step 2: Vérifier la syntaxe YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): add Séries tab (small|full|small)"
```

---

## Task 5: Onglet Animés

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

- [ ] **Step 1: Ajouter l'onglet Animés après l'onglet séries**

Insérer après la fin du bloc `- name: séries` (juste avant `# ── Stats ──`) :

```yaml
      # ── Animés ─────────────────────────────────────────────────────────────
      - name: animés
        columns:
          - size: small
            widgets:
              - type: custom-api
                title: Lecture en cours
                allow-insecure-html: true
                cache: 30s
                url: "http://emby.media.svc.cluster.local:8096/Sessions?ActiveWithinSeconds=300&api_key=$${EMBY_API_KEY}"
                template: |
                  {{$any := false}}
                  <div style="display:flex;flex-direction:column;gap:8px">
                  {{range .JSON.Array "@this"}}
                  {{if (.String "NowPlayingItem.Name")}}
                  {{$any = true}}
                  {{$paused := eq (.String "PlayState.IsPaused") "true"}}
                  {{$h := .Int "NowPlayingItem.Height"}}
                  <div style="display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(0,0,0,.06);border-radius:6px">
                    <img src="https://emby.${SECRET_DOMAIN}/Items/{{if (.String "NowPlayingItem.SeriesId")}}{{.String "NowPlayingItem.SeriesId"}}{{else}}{{.String "NowPlayingItem.Id"}}{{end}}/Images/Primary?maxHeight=100&api_key=$${EMBY_API_KEY}" style="width:45px;min-width:45px;height:67px;object-fit:cover;border-radius:4px;flex-shrink:0">
                    <div style="min-width:0;flex:1">
                      <div style="font-weight:700;font-size:.9em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{if $paused}}<span style="color:#f59e0b">●</span>{{else}}<span style="color:#22c55e">●</span>{{end}} {{if (.String "NowPlayingItem.SeriesName")}}{{.String "NowPlayingItem.SeriesName"}}{{else}}{{.String "NowPlayingItem.Name"}}{{end}}</div>
                      {{if (.String "NowPlayingItem.SeriesName")}}<div style="font-size:.75em;opacity:.7;margin-top:2px">{{printf "S%02dE%02d" (.Int "NowPlayingItem.ParentIndexNumber") (.Int "NowPlayingItem.IndexNumber")}} · {{.String "NowPlayingItem.Name"}}</div>{{end}}
                      <div style="font-size:.75em;opacity:.65;margin-top:2px">{{if (.String "NowPlayingItem.SeriesName")}}TV{{else}}Film{{end}} · {{if gt $h 2000}}4K{{else if gt $h 1000}}1080p{{else if gt $h 680}}720p{{else}}SD{{end}} · {{.String "PlayState.PlayMethod"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:1px">👤 {{.String "UserName"}} · {{.String "Client"}} ({{.String "DeviceName"}})</div>
                      <div style="font-size:.75em;font-weight:600;margin-top:3px">{{if $paused}}⏸ En pause{{else}}▶ En lecture{{end}}</div>
                    </div>
                  </div>
                  {{end}}
                  {{end}}
                  </div>

              - type: custom-api
                title: Téléchargements
                allow-insecure-html: true
                cache: 30s
                url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/queue?apikey=$${SONARR_API_KEY}&pageSize=8"
                template: |
                  {{$records := .JSON.Array "records"}}
                  {{if eq (len $records) 0}}
                  <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $records}}
                  <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                    <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                    <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                  </div>
                  {{end}}
                  </div>
                  {{end}}

              - type: bookmarks
                title: Liens
                groups:
                  - title: Animés
                    links:
                      - title: Sonarr
                        url: https://sonarr.${SECRET_DOMAIN}
                        icon: di:sonarr
                      - title: Emby
                        url: https://emby.${SECRET_DOMAIN}
                        icon: di:emby

          - size: full
            widgets:
              - type: custom-api
                title: Animés populaires
                allow-insecure-html: true
                cache: 1h
                url: "https://api.themoviedb.org/3/discover/tv?api_key=$${TMDB_API_KEY}&with_genres=16&with_original_language=ja&sort_by=popularity.desc&language=fr-FR"
                template: |
                  <div id="glance-ask" data-k="$${TMDB_API_KEY}" data-d="${SECRET_DOMAIN}" onclick="(function(e){var q=document.getElementById('glance-asq').value.trim(),a=e.dataset.k,d=e.dataset.d;if(!q)return;fetch('https://api.themoviedb.org/3/search/tv?api_key='+a+'&query='+encodeURIComponent(q)+'&language=fr-FR').then(function(r){return r.json()}).then(function(data){var h='<div style=\'display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px\'>';data.results.forEach(function(m){var img=m.poster_path?'<img src=\'https://image.tmdb.org/t/p/w92'+m.poster_path+'\' style=\'width:100%;aspect-ratio:2/3;object-fit:cover\'>':'<div style=\'width:100%;aspect-ratio:2/3;background:rgba(0,0,0,.1)\'></div>';h+='<a href=\'https://sonarr.'+d+'/add/new?term='+encodeURIComponent(m.name)+'\' target=\'_blank\' style=\'text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)\' onmouseover=\'this.style.opacity=.75\' onmouseout=\'this.style.opacity=1\'>'+img+'<div style=\'padding:8px\'><div style=\'font-weight:600;font-size:.85em;line-height:1.2\'>'+m.name+'</div><div style=\'font-size:.75em;opacity:.65;margin-top:3px\'>'+(m.first_air_date||'')+'</div><div style=\'font-size:.75em;margin-top:3px\'>⭐ '+(m.vote_average?m.vote_average.toFixed(1):'?')+'</div></div></a>';});h+='</div>';document.getElementById('glance-asr').innerHTML=h;document.getElementById('glance-asr').style.display='';document.getElementById('glance-asd').style.display='none';});})(this)" style="display:none"></div>
                  <div style="display:flex;gap:8px;margin-bottom:12px">
                    <input id="glance-asq" placeholder="Rechercher un animé..." onkeydown="if(event.key==='Enter')document.getElementById('glance-ask').click()" style="flex:1;padding:6px 10px;border-radius:6px;border:1px solid rgba(0,0,0,.2);background:rgba(0,0,0,.05);font-size:.9em">
                    <button onclick="document.getElementById('glance-ask').click()" style="padding:6px 14px;border-radius:6px;background:rgba(0,0,0,.1);border:none;cursor:pointer;font-size:.9em">→</button>
                    <button onclick="document.getElementById('glance-asq').value='';document.getElementById('glance-asr').style.display='none';document.getElementById('glance-asd').style.display=''" style="padding:6px 10px;border-radius:6px;background:rgba(0,0,0,.06);border:none;cursor:pointer;font-size:.9em;opacity:.6">✕</button>
                  </div>
                  <div id="glance-asr" style="display:none"></div>
                  <div id="glance-asd">
                  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px">
                  {{range .JSON.Array "results"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/add/new?term={{.String "name"}}" target="_blank" style="text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:100%;aspect-ratio:2/3;object-fit:cover">
                    <div style="padding:8px">
                      <div style="font-weight:600;font-size:.85em;line-height:1.2">{{.String "name"}}</div>
                      {{$fad := .String "first_air_date"}}<div style="font-size:.75em;opacity:.65;margin-top:3px">{{slice $fad 8 10}}-{{slice $fad 5 7}}-{{slice $fad 0 4}}</div>
                      <div style="font-size:.75em;margin-top:3px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>
                  </div>

          - size: small
            widgets:
              - type: custom-api
                title: Épisodes à venir
                allow-insecure-html: true
                cache: 30m
                url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/calendar?start=2025-01-01&end=2027-12-31&apikey=$${SONARR_API_KEY}&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/series" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://sonarr.${SECRET_DOMAIN}/MediaCover/{{.Int "seriesId"}}/poster.jpg?apikey=$${SONARR_API_KEY}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      {{$au := .String "airDateUtc"}}<div style="font-size:.7em;opacity:.65">{{printf "S%02dE%02d" (.Int "seasonNumber") (.Int "episodeNumber")}} · {{slice $au 8 10}}-{{slice $au 5 7}}-{{slice $au 0 4}}</div>
                      {{if eq (.String "hasFile") "true"}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Dispo</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:2px">Manquant</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

              - type: custom-api
                title: Nouvelles saisons
                allow-insecure-html: true
                cache: 6h
                url: "https://api.themoviedb.org/3/discover/tv?api_key=$${TMDB_API_KEY}&with_genres=16&with_original_language=ja&sort_by=first_air_date.asc&first_air_date.gte=2026-04-01&first_air_date.lte=2027-12-31&language=fr-FR&vote_count.gte=5"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "results"}}
                  <a href="https://sonarr.${SECRET_DOMAIN}/add/new?term={{.String "name"}}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    <img src="https://image.tmdb.org/t/p/w92{{.String "poster_path"}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "name"}}</div>
                      {{$fad := .String "first_air_date"}}<div style="font-size:.7em;opacity:.65;margin-top:2px">{{slice $fad 8 10}}-{{slice $fad 5 7}}-{{slice $fad 0 4}}</div>
                      <div style="font-size:.7em;margin-top:2px">⭐ {{.String "vote_average"}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>

```

- [ ] **Step 2: Vérifier la syntaxe YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): add Animés tab (small|full|small)"
```

---

## Task 6: Onglet Livres

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

> **Prérequis :** Task 1 (ABS_TOKEN dans l'ExternalSecret) doit être déployée avant de pouvoir utiliser `$${ABS_TOKEN}`.

- [ ] **Step 1: Ajouter l'onglet Livres après l'onglet animés**

Insérer après la fin du bloc `- name: animés` (juste avant `# ── Stats ──`) :

```yaml
      # ── Livres ─────────────────────────────────────────────────────────────
      - name: livres
        columns:
          - size: small
            widgets:
              - type: custom-api
                title: Lecture en cours
                allow-insecure-html: true
                cache: 30s
                url: "http://audiobookshelf.media.svc.cluster.local/api/me/listening-sessions?itemsPerPage=3&token=$${ABS_TOKEN}"
                template: |
                  {{$sessions := .JSON.Array "sessions"}}
                  {{if eq (len $sessions) 0}}
                  <div style="font-size:.85em;opacity:.5">Aucune session en cours</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:8px">
                  {{range $sessions}}
                  <div style="display:flex;gap:10px;align-items:flex-start;padding:10px;background:rgba(0,0,0,.06);border-radius:6px">
                    <img src="https://audiobookshelf.${SECRET_DOMAIN}/api/items/{{.String "libraryItemId"}}/cover?token=$${ABS_TOKEN}" style="width:45px;min-width:45px;height:67px;object-fit:cover;border-radius:4px;flex-shrink:0">
                    <div style="min-width:0;flex:1">
                      <div style="font-weight:700;font-size:.9em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><span style="color:#22c55e">●</span> {{.String "mediaMetadata.title"}}</div>
                      <div style="font-size:.75em;opacity:.7;margin-top:2px">{{.String "mediaMetadata.authorName"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:2px">▶ En cours · {{.Int "currentTime"}}s / {{.Int "duration"}}s</div>
                    </div>
                  </div>
                  {{end}}
                  </div>
                  {{end}}

              - type: custom-api
                title: Téléchargements
                allow-insecure-html: true
                cache: 30s
                url: "http://readarr.downloads.svc.cluster.local:8787/api/v1/queue?apikey=$${READARR_API_KEY}&pageSize=8"
                template: |
                  {{$records := .JSON.Array "records"}}
                  {{if eq (len $records) 0}}
                  <div style="font-size:.85em;opacity:.5">Aucun téléchargement en cours</div>
                  {{else}}
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range $records}}
                  <div style="padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px">
                    <div style="font-size:.8em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                    <div style="display:flex;justify-content:space-between;font-size:.7em;opacity:.6;margin-top:2px"><span>{{.String "status"}}</span><span>{{.String "timeleft"}}</span></div>
                  </div>
                  {{end}}
                  </div>
                  {{end}}

              - type: bookmarks
                title: Liens
                groups:
                  - title: Livres
                    links:
                      - title: Readarr
                        url: https://readarr.${SECRET_DOMAIN}
                        icon: di:readarr
                      - title: Audiobookshelf
                        url: https://audiobookshelf.${SECRET_DOMAIN}
                        icon: di:audiobookshelf

          - size: full
            widgets:
              - type: custom-api
                title: Bibliothèque Readarr
                allow-insecure-html: true
                cache: 30m
                url: "http://readarr.downloads.svc.cluster.local:8787/api/v1/book?apikey=$${READARR_API_KEY}&pageSize=20&sortKey=releaseDate&sortDirection=desc&unmonitored=false"
                template: |
                  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://readarr.${SECRET_DOMAIN}" target="_blank" style="text-decoration:none;color:inherit;display:block;border-radius:8px;overflow:hidden;background:rgba(0,0,0,.06)" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    {{$cover := .String "images.#[coverType==cover].url"}}
                    {{if $cover}}<img src="{{$cover}}" style="width:100%;aspect-ratio:2/3;object-fit:cover">{{else}}<div style="width:100%;aspect-ratio:2/3;background:rgba(0,0,0,.1);display:flex;align-items:center;justify-content:center;font-size:2em">📚</div>{{end}}
                    <div style="padding:8px">
                      <div style="font-weight:600;font-size:.85em;line-height:1.2">{{.String "title"}}</div>
                      <div style="font-size:.75em;opacity:.65;margin-top:3px">{{.String "authorTitle"}}</div>
                      {{$rd := .String "releaseDate"}}<div style="font-size:.7em;opacity:.5;margin-top:2px">{{slice $rd 0 10}}</div>
                      {{if eq (.Int "statistics.bookFileCount") 0}}<span style="font-size:.65em;padding:1px 5px;background:#ef4444;color:#fff;border-radius:3px;display:inline-block;margin-top:3px">Manquant</span>{{else}}<span style="font-size:.65em;padding:1px 5px;background:#22c55e;color:#fff;border-radius:3px;display:inline-block;margin-top:3px">Dispo</span>{{end}}
                    </div>
                  </a>
                  {{end}}
                  </div>

          - size: small
            widgets:
              - type: custom-api
                title: Livres à venir
                allow-insecure-html: true
                cache: 6h
                url: "http://readarr.downloads.svc.cluster.local:8787/api/v1/calendar?apikey=$${READARR_API_KEY}&start=2025-01-01&end=2027-12-31&unmonitored=false"
                template: |
                  <div style="display:flex;flex-direction:column;gap:4px">
                  {{range .JSON.Array "@this"}}
                  <a href="https://readarr.${SECRET_DOMAIN}" target="_blank" style="text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:rgba(0,0,0,.06);border-radius:5px" onmouseover="this.style.opacity=.75" onmouseout="this.style.opacity=1">
                    {{$cover := .String "images.#[coverType==cover].url"}}
                    {{if $cover}}<img src="{{$cover}}" style="width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0">{{else}}<div style="width:35px;min-width:35px;height:52px;background:rgba(0,0,0,.1);border-radius:3px;flex-shrink:0;display:flex;align-items:center;justify-content:center">📚</div>{{end}}
                    <div style="min-width:0">
                      <div style="font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{.String "title"}}</div>
                      <div style="font-size:.7em;opacity:.65;margin-top:2px">{{.String "authorTitle"}}</div>
                      {{$rd := .String "releaseDate"}}<div style="font-size:.7em;opacity:.5;margin-top:1px">{{slice $rd 0 10}}</div>
                    </div>
                  </a>
                  {{end}}
                  </div>

```

- [ ] **Step 2: Vérifier la syntaxe YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): add Livres tab (small|full|small)"
```

---

## Notes de déploiement

Flux reconcilie automatiquement la ConfigMap. Après chaque commit :
- Le pod Glance redémarre pour charger le nouveau `glance.yml`
- Vérifier dans les logs : `kubectl logs -n selfhosted -l app.kubernetes.io/name=glance --tail=20`
- Si le pod crashe, `kubectl describe pod -n selfhosted -l app.kubernetes.io/name=glance` donnera la raison

### Problèmes courants

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| Template error : slice bounds | Date vide dans un champ TMDB/Sonarr | Ajouter `{{if gt (len $date) 9}}` avant `{{slice ...}}` |
| ABS sessions vide | Token invalide ou item 1Password mal nommé | Vérifier le token ABS dans l'interface web ABS → Settings |
| Readarr queue 404 | URL incorrecte | Vérifier le namespace : `kubectl get svc -n downloads` |
