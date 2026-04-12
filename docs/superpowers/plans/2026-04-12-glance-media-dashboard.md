# Glance Media Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le group widget (6 onglets TMDB/search) de la colonne centrale du tab média par un widget dashboard riche : stats bibliothèque (server-side) + ajouts récents + historique de lecture (browser-side via gls-trigger).

**Architecture:** Un seul `custom-api` widget fetchant Emby `/Items/Counts` côté serveur pour les stats. Un `gls-trigger` intégré dans le template fait deux fetches en parallèle (ajouts récents + historique) vers Emby public depuis le browser, et rend les deux sections en HTML.

**Tech Stack:** Glance `custom-api`, Go templates, gls-trigger browser-side JS, Emby REST API.

---

## Fichier modifié

- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`
  - Supprimer : le bloc `- size: full` du tab `media` (le `group` avec les onglets Media/Films/Séries/Animés/Livres/Musique, environ 150 lignes)
  - Ajouter : un nouveau bloc `- size: full` avec le widget dashboard

---

## Task 1 : Remplacer la colonne centrale du tab media

**Files:**
- Modify: `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

- [ ] **Step 1 : Identifier le bloc à remplacer**

Dans `configmap.yaml`, trouver le bloc `- size: full` à l'intérieur du tab `media`. Il commence par :

```yaml
          - size: full
            widgets:
              - type: group
                widgets:
                  - type: custom-api
                    title: Media
                    allow-insecure-html: true
                    cache: 30s
```

Et se termine juste avant la ligne :

```yaml
          - size: small
            widgets:
              - type: group
                widgets:
                  - type: custom-api
                    title: Media
                    allow-insecure-html: true
                    cache: 30m
                    url: "http://sonarr.downloads.svc.cluster.local:8989/api/v3/calendar
```

(La troisième colonne du tab media, celle avec le calendrier Sonarr.)

- [ ] **Step 2 : Appliquer l'Edit — remplacer le bloc entier**

Utiliser l'outil Edit pour remplacer tout le bloc `- size: full` (du group avec les 6 onglets) par le contenu suivant.

**old_string** — commence par (utiliser ce début unique pour l'ancre) :
```
          - size: full
            widgets:
              - type: group
                widgets:
                  - type: custom-api
                    title: Media
                    allow-insecure-html: true
                    cache: 30s
                    url: "http://radarr.downloads.svc.cluster.local:7878/api/v3/queue?apikey=$${RADARR_API_KEY}&pageSize=10"
```

**new_string** — le widget dashboard complet :

```yaml
          - size: full
            widgets:
              - type: custom-api
                title: Bibliothèque
                allow-insecure-html: true
                cache: 5m
                url: "http://emby.media.svc.cluster.local:8096/Items/Counts?api_key=$${EMBY_API_KEY}"
                template: |
                  {{$movies := .Int "MovieCount"}}
                  {{$series := .Int "SeriesCount"}}
                  {{$episodes := .Int "EpisodeCount"}}
                  {{$songs := .Int "SongCount"}}
                  <div style="display:flex;flex-direction:column;gap:16px">
                  <div>
                    <div class="gls-section-hdr">BIBLIOTHÈQUE</div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                      <div style="flex:1;min-width:80px;padding:10px 14px;background:rgba(0,0,0,.1);border-radius:8px;text-align:center">
                        <div style="font-size:1.4em;font-weight:700;color:#3b82f6">{{$movies}}</div>
                        <div style="font-size:.7em;opacity:.6;margin-top:1px">🎬 Films</div>
                      </div>
                      <div style="flex:1;min-width:80px;padding:10px 14px;background:rgba(0,0,0,.1);border-radius:8px;text-align:center">
                        <div style="font-size:1.4em;font-weight:700;color:#8b5cf6">{{$series}}</div>
                        <div style="font-size:.7em;opacity:.6;margin-top:1px">📺 Séries</div>
                      </div>
                      <div style="flex:1;min-width:80px;padding:10px 14px;background:rgba(0,0,0,.1);border-radius:8px;text-align:center">
                        <div style="font-size:1.4em;font-weight:700;color:#06b6d4">{{$episodes}}</div>
                        <div style="font-size:.7em;opacity:.6;margin-top:1px">🎞 Épisodes</div>
                      </div>
                      <div style="flex:1;min-width:80px;padding:10px 14px;background:rgba(0,0,0,.1);border-radius:8px;text-align:center">
                        <div style="font-size:1.4em;font-weight:700;color:#f59e0b">{{$songs}}</div>
                        <div style="font-size:.7em;opacity:.6;margin-top:1px">🎵 Morceaux</div>
                      </div>
                    </div>
                  </div>
                  <div id="glance-lib" class="gls-trigger" data-k="$${EMBY_API_KEY}" data-d="${SECRET_DOMAIN}" onanimationstart="(function(el){var k=el.dataset.k,d=el.dataset.d,base='https://emby.'+d;Promise.all([fetch(base+'/Items?SortBy=DateCreated&SortOrder=Descending&IncludeItemTypes=Movie,Series&Recursive=true&Limit=16&Fields=PrimaryImageAspectRatio&api_key='+k).then(function(r){return r.json()}),fetch(base+'/Users?api_key='+k).then(function(r){return r.json()}).then(function(us){var uid=us&&us[0]&&us[0].Id;if(!uid)return{Items:[]};return fetch(base+'/Users/'+uid+'/Items?SortBy=DatePlayed&SortOrder=Descending&Filters=IsPlayed&Recursive=true&Limit=8&IncludeItemTypes=Movie,Episode&Fields=PrimaryImageAspectRatio,UserData&api_key='+k).then(function(r){return r.json();});})]).then(function(res){var rec=res[0].Items||[],hist=res[1].Items||[];function ago(s){var diff=Date.now()-new Date(s).getTime(),m=Math.floor(diff/60000);if(m<60)return'il y a '+m+'min';if(m<1440)return'il y a '+Math.floor(m/60)+'h';return'il y a '+Math.floor(m/1440)+'j';}function dur(t){var s=Math.floor(t/10000000),h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h>0?h+'h'+String(m).padStart(2,'0'):m+'min';}var h='<div class=\'gls-section-hdr\' style=\'margin-bottom:8px\'>AJOUTS RÉCENTS</div>';if(rec.length){h+='<div style=\'display:flex;gap:6px;overflow-x:auto;padding-bottom:6px\'>';rec.forEach(function(it){h+='<a href=\''+base+'/web/index.html#!/details?id='+it.Id+'\' target=\'_blank\' style=\'text-decoration:none;flex-shrink:0;display:block;width:92px\'><img src=\''+base+'/Items/'+it.Id+'/Images/Primary?maxHeight=138&api_key='+k+'\' style=\'width:92px;height:138px;object-fit:cover;border-radius:6px\'><span style=\'display:inline-block;margin-top:2px;font-size:.6em;padding:1px 4px;background:'+(it.Type==='Movie'?'#3b82f6':'#8b5cf6')+';color:#fff;border-radius:3px\'>'+(it.Type==='Movie'?'Film':'Série')+'</span><div style=\'font-size:.7em;font-weight:600;line-height:1.2;margin-top:1px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden\'>'+it.Name+'</div></a>';});h+='</div>';}else{h+='<div style=\'font-size:.85em;opacity:.5\'>Aucun ajout récent</div>';}h+='<div style=\'margin-top:14px\'><div class=\'gls-section-hdr\' style=\'margin-bottom:8px\'>VU RÉCEMMENT</div>';if(hist.length){h+='<div style=\'display:flex;flex-direction:column;gap:5px\'>';hist.forEach(function(it){var title=it.SeriesName||it.Name;var sub=it.SeriesName?'S'+String(it.ParentIndexNumber||0).padStart(2,'0')+'E'+String(it.IndexNumber||0).padStart(2,'0')+' · '+it.Name:(it.ProductionYear?String(it.ProductionYear):'');var ag=it.UserData&&it.UserData.LastPlayedDate?ago(it.UserData.LastPlayedDate):'';var dr=it.RunTimeTicks?dur(it.RunTimeTicks):'';h+='<a href=\''+base+'/web/index.html#!/details?id='+it.Id+'\' target=\'_blank\' style=\'text-decoration:none;color:inherit;display:flex;gap:8px;align-items:flex-start;padding:5px 8px;background:rgba(0,0,0,.06);border-radius:5px\' onmouseover=\'this.style.opacity=.75\' onmouseout=\'this.style.opacity=1\'><img src=\''+base+'/Items/'+it.Id+'/Images/Primary?maxHeight=80&api_key='+k+'\' style=\'width:35px;min-width:35px;height:52px;object-fit:cover;border-radius:3px;flex-shrink:0\'><div style=\'min-width:0;flex:1\'><div style=\'font-weight:600;font-size:.8em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis\'>'+title+'</div>'+(sub?'<div style=\'font-size:.7em;opacity:.65;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis\'>'+sub+'</div>':'')+'<div style=\'display:flex;justify-content:space-between;font-size:.68em;margin-top:2px;opacity:.5\'><span>'+dr+'</span><span>'+ag+'</span></div></div></a>';});h+='</div>';}else{h+='<div style=\'font-size:.85em;opacity:.5\'>Aucun historique</div>';}h+='</div>';el.innerHTML=h;}).catch(function(e){el.innerHTML='<div style=\'font-size:.85em;opacity:.5\'>Erreur: '+e.message+'</div>';});})(this)">Chargement...</div>
                  </div>

```

Note importante : la ligne `<div id="glance-lib"...>` doit rester sur **une seule ligne** dans le fichier YAML (pas de retour à la ligne dans le contenu de `onanimationstart`). L'outil Edit préservera ça correctement.

L'old_string doit s'étendre jusqu'à (inclus) la dernière ligne du group actuel — la ligne juste avant `          - size: small` de la 3ème colonne. Rechercher `ALBUMS RECHERCHÉS` pour trouver la fin du group, puis inclure tout jusqu'à la ligne `</div>` qui suit le gls-trigger Lidarr.

- [ ] **Step 3 : Vérifier la syntaxe YAML**

```bash
cd /home/kryzql/home-ops
python3 -c "import yaml; yaml.safe_load(open('kubernetes/apps/selfhosted/glance/app/configmap.yaml').read()); print('YAML OK')"
```

Résultat attendu : `YAML OK`

Si erreur, chercher la ligne indiquée et corriger l'indentation ou les guillemets.

- [ ] **Step 4 : Commit et push**

```bash
git add kubernetes/apps/selfhosted/glance/app/configmap.yaml
git commit -m "feat(glance): replace media center column with library dashboard

3-section widget: stats (server-side Emby /Items/Counts), recent
additions grid (browser-side, horizontal scroll), watch history list
(browser-side, Emby played items). Removes TMDB search group tabs.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

- [ ] **Step 5 : Réconcilier Flux et vérifier**

```bash
flux reconcile kustomization glance -n selfhosted --with-source
```

Attendre ~30s, puis ouvrir Glance dans le browser, aller sur l'onglet **Media**, colonne centrale.

Vérifier :
- Section **BIBLIOTHÈQUE** : 4 chips avec chiffres colorés (Films/Séries/Épisodes/Morceaux)
- Section **AJOUTS RÉCENTS** : rangée horizontale de posters, scrollable
- Section **VU RÉCEMMENT** : liste avec posters miniature, titre, durée, temps écoulé
- Colonnes gauche et droite : **inchangées**
- Aucune erreur JS dans la console du browser

---

## Références API Emby utilisées

| Endpoint | Usage | Notes |
|---|---|---|
| `GET /Items/Counts` | Stats server-side | Retourne `MovieCount`, `SeriesCount`, `EpisodeCount`, `SongCount` |
| `GET /Items?SortBy=DateCreated&IncludeItemTypes=Movie,Series` | Ajouts récents | Champ `PrimaryImageAspectRatio` demandé pour les posters |
| `GET /Users` | Récupérer l'UserId | Premier élément du tableau |
| `GET /Users/{id}/Items?Filters=IsPlayed&SortBy=DatePlayed` | Historique | Champs `UserData.LastPlayedDate`, `RunTimeTicks`, `SeriesName` |
| `GET /Items/{id}/Images/Primary?maxHeight=138` | Posters ajouts | URL construite browser-side |
| `GET /Items/{id}/Images/Primary?maxHeight=80` | Posters historique | URL construite browser-side |
