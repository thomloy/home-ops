# Glance Media Redesign

**Date:** 2026-04-10
**Scope:** `kubernetes/apps/selfhosted/glance/app/configmap.yaml`

## Objectif

Remplacer l'unique onglet "media" (avec un group widget Films/Séries/Animés) par 5 onglets Glance dédiés, chacun avec un layout 3 colonnes cohérent (small | full | small), où le contenu de chaque colonne est spécifique à la catégorie.

## Layout commun à tous les onglets

```
[ small ]          [ full ]              [ small ]
Lecture en cours   Contenu principal     Agenda / Watchlist
Téléch. actifs     (TMDB + recherche     spécifique
Liens rapides       ou bibliothèque)
```

---

## Onglets et contenu

### 1. Media (vue générale)

| Colonne | Contenu |
|---------|---------|
| small gauche | Lecture en cours (Emby + Audiobookshelf) · Liens rapides (Emby, ABS, Radarr, Sonarr, Readarr) |
| full centre | Stats bibliothèque Emby (films, séries, épisodes) · Queue téléchargements (Radarr + Sonarr) |
| small droite | Agenda global : prochains épisodes + films attendus |

### 2. Films

| Colonne | Contenu |
|---------|---------|
| small gauche | Lecture en cours (Emby) · Queue Radarr · Liens (Radarr, Emby) |
| full centre | Films en salle TMDB (`now_playing`, fr-FR) + barre de recherche → Radarr |
| small droite | Watchlist Radarr (films monitored) · Sorties films FR (TMDB) |

### 3. Séries

| Colonne | Contenu |
|---------|---------|
| small gauche | Lecture en cours (Emby) · Queue Sonarr · Liens (Sonarr, Emby) |
| full centre | Séries en cours TMDB (`on_the_air`, fr-FR) + barre de recherche → Sonarr |
| small droite | Épisodes à venir (Sonarr calendar) · Sorties séries FR (TMDB) |

### 4. Animés

| Colonne | Contenu |
|---------|---------|
| small gauche | Lecture en cours (Emby) · Queue Sonarr · Liens (Sonarr, Emby) |
| full centre | Animés populaires TMDB (genre 16, ja, `popularity.desc`, fr-FR) + barre de recherche → Sonarr |
| small droite | Épisodes animés à venir (Sonarr calendar) · Nouvelles saisons (TMDB discover) |

### 5. Livres

| Colonne | Contenu |
|---------|---------|
| small gauche | Lecture en cours (Audiobookshelf — session active) · Queue Readarr · Liens (Readarr, ABS) |
| full centre | Bibliothèque Readarr (livres monitored, `GET /api/v1/book`) |
| small droite | Livres à venir (Readarr calendar) |

---

## APIs utilisées

| Service | Endpoint | Clé |
|---------|----------|-----|
| Emby | `http://emby.media.svc.cluster.local:8096/Sessions` | `EMBY_API_KEY` |
| Emby | `http://emby.media.svc.cluster.local:8096/Items` (stats) | `EMBY_API_KEY` |
| Audiobookshelf | `http://audiobookshelf.media.svc.cluster.local/api/me/listening-sessions` | à ajouter en secret |
| TMDB | `https://api.themoviedb.org/3/...` | `TMDB_API_KEY` |
| Radarr | `http://radarr.downloads.svc.cluster.local:7878/api/v3/queue` (queue) | `RADARR_API_KEY` |
| Radarr | `http://radarr.downloads.svc.cluster.local:7878/api/v3/calendar` (watchlist) | `RADARR_API_KEY` |
| Sonarr | `http://sonarr.downloads.svc.cluster.local:8989/api/v3/queue` (queue) | `SONARR_API_KEY` |
| Sonarr | `http://sonarr.downloads.svc.cluster.local:8989/api/v3/calendar` (agenda) | `SONARR_API_KEY` |
| Readarr | `http://readarr.downloads.svc.cluster.local:8787/api/v1/book` | `READARR_API_KEY` |
| Readarr | `http://readarr.downloads.svc.cluster.local:8787/api/v1/calendar` | `READARR_API_KEY` |

> **Note :** La clé Audiobookshelf n'est pas encore dans l'ExternalSecret Glance. Il faudra l'ajouter à `externalsecret.yaml` et dans 1Password.

---

## Modifications fichiers

| Fichier | Changement |
|---------|-----------|
| `configmap.yaml` | Remplacer l'onglet `media` par 5 onglets (media, films, séries, animés, livres) |
| `externalsecret.yaml` | Ajouter `ABS_API_KEY` (Audiobookshelf) si l'onglet Livres est implémenté |

---

## Ce qui est supprimé

- Le widget `group` avec les 3 sous-onglets Films/Séries/Animés (remplacé par des onglets natifs Glance)
- Les "Sorties films (FR)" et "Sorties séries (FR)" en tant que widgets standalone → intégrés dans les colonnes droites des onglets correspondants
- La "Watchlist (Radarr)" standalone → intégrée dans la colonne droite Films
