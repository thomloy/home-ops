# Glance Media Tab — Dashboard Colonne Centrale

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le group widget (onglets recherche TMDB) de la colonne centrale du tab média par un widget dashboard riche en 3 sections : stats bibliothèque, ajouts récents, historique de lecture.

**Scope:** Uniquement `kubernetes/apps/selfhosted/glance/app/configmap.yaml`, colonne `size: full` du tab `media`. Les deux colonnes latérales ne sont pas touchées.

**Tech Stack:** Glance `custom-api` widget, Go templates, `gls-trigger` browser-side JS, API Emby interne.

---

## Contexte

La colonne centrale (`size: full`) du tab media contient actuellement un `group` avec 6 onglets : Media (queue Radarr brute) | Films (recherche TMDB) | Séries | Animés | Livres | Musique. Le premier onglet affiche souvent un grand vide quand la queue est vide. La recherche TMDB reste accessible via Radarr/Sonarr directement.

---

## Structure du widget

Un seul `custom-api` widget remplace tout le `group`. Il est structuré en 3 sections verticales.

### Section 1 — BIBLIOTHÈQUE (stats)

- **Source :** `GET http://emby.media.svc.cluster.local:8096/Items/Counts?api_key=${EMBY_API_KEY}` — server-side, dans `url:`
- **Champs utilisés :** `MovieCount`, `SeriesCount`, `EpisodeCount`, `SongCount`
- **Rendu :** Une ligne horizontale de 4 chips colorées :
  `🎬 {n} films · 📺 {n} séries · 📖 {n} épisodes · 🎵 {n} morceaux`
- **Template :** Go template pur, pas de gls-trigger nécessaire

### Section 2 — AJOUTS RÉCENTS

- **Source :** Emby `GET /Items?SortBy=DateCreated&SortOrder=Descending&IncludeItemTypes=Movie,Series&Recursive=true&Limit=16&Fields=PrimaryImageAspectRatio&api_key=KEY`
- **Mécanisme :** `gls-trigger` — fetché browser-side depuis `https://emby.${SECRET_DOMAIN}`
- **Rendu :** Grille CSS horizontale scrollable (`overflow-x: auto`, `grid-auto-flow: column`), posters `w92` TMDB-style via `https://emby.${SECRET_DOMAIN}/Items/{Id}/Images/Primary?maxHeight=138&api_key=KEY`. Chaque poster clique → ouvre Emby sur l'item. Badge "Film" / "Série" en overlay.
- **Limite :** 16 items, affichés en rangée horizontale

### Section 3 — VU RÉCEMMENT

- **Source :** deux appels chaînés :
  1. `GET /Users` → récupère `Id` du premier élément du tableau retourné (l'admin, seul compte sur ce homelab)
  2. `GET /Users/{Id}/Items?SortBy=DatePlayed&SortOrder=Descending&Filters=IsPlayed&Recursive=true&Limit=8&IncludeItemTypes=Movie,Episode&Fields=PrimaryImageAspectRatio,UserData&api_key=KEY`
- **Mécanisme :** Même `gls-trigger` que Section 2 — `Promise.all` pour paralléliser les deux fetches (récents + users/history)
- **Rendu :** Liste verticale compacte. Par item :
  - Poster miniature (35×52px)
  - Titre (+ S01E01 si épisode)
  - Type · Durée formatée
  - "il y a Xh" / "il y a X jours" basé sur `UserData.LastPlayedDate`
- **Limite :** 8 items

---

## Architecture technique

```
custom-api widget
├── url: emby /Items/Counts  (server-side)
├── cache: 5m
├── template:
│   ├── [Go template] → Section 1 stats (MovieCount, SeriesCount...)
│   └── [gls-trigger div] data-k="${EMBY_API_KEY}" data-d="${SECRET_DOMAIN}"
│       └── onanimationstart: JS
│           ├── Promise.all([
│           │   fetch(emby /Items?SortBy=DateCreated...)   → Section 2
│           │   fetch(emby /Users)
│           │     .then(fetch /Users/{id}/Items?DatePlayed) → Section 3
│           │ ])
│           └── render innerHTML
```

### Clé API Emby

Déjà disponible comme `$${EMBY_API_KEY}` dans le template (ExternalSecret existant). Utilisée en `data-k` pour le browser-side.

### Formatage du temps écoulé

```js
function timeAgo(dateStr) {
  var diff = Date.now() - new Date(dateStr).getTime();
  var min = Math.floor(diff / 60000);
  if (min < 60) return 'il y a ' + min + 'min';
  var h = Math.floor(min / 60);
  if (h < 24) return 'il y a ' + h + 'h';
  return 'il y a ' + Math.floor(h / 24) + 'j';
}
```

### Formatage de la durée

Ticks Emby → secondes : `Math.floor(ticks / 10000000)` → `H:MM` ou `MM:SS`

---

## Ce qui est supprimé

Le `group` widget avec les onglets suivants est **entièrement supprimé** de la colonne centrale :
- Onglet "Media" (queue Radarr brute + JS sync tabs)
- Onglet "Films" (recherche TMDB + now_playing grid)
- Onglet "Séries" (recherche TMDB + on_the_air grid)
- Onglet "Animés" (discover TMDB + grid)
- Onglet "Livres" (Readarr library grid)
- Onglet "Musique" (Lidarr queue)

Ces fonctionnalités restent accessibles via les liens directs dans la colonne gauche (Radarr, Sonarr, etc.).

---

## Fichier modifié

- `kubernetes/apps/selfhosted/glance/app/configmap.yaml`
  - Supprimer : le bloc `- size: full` du tab `media` (le group avec 6 onglets Films/Séries/Animés/Livres/Musique/Media)
  - Ajouter : un nouveau bloc `- size: full` avec le widget dashboard

---

## Critères de succès

- Les 3 sections s'affichent sans erreur
- Les posters "Ajouts récents" sont cliquables et ouvrent Emby
- "Vu récemment" affiche le bon utilisateur (Thomas)
- Les deux colonnes latérales sont inchangées
- Aucun widget existant cassé
