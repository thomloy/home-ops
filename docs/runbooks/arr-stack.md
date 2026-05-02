# *arr stack runbook

## Quality / Release profile policy

The cluster runs **Recyclarr** (`kubernetes/apps/downloads/recyclarr/`) which
re-applies quality profiles + custom formats from the TRaSH guide on every
scheduled run.

Profiles that must exist (managed by Recyclarr — do not delete via UI):

| App | Profile name | Purpose |
|---|---|---|
| Radarr | `SQP-1 (2160p)` | 4K movies (Bluray + WEB) |
| Radarr | `FR-MULTi-VO-HD` | HD movies, French audio preferred |
| Sonarr | `WEB-1080p` | HD WEB, English |
| Sonarr | `WEB-2160p` | 4K WEB |
| Sonarr | `FR-MULTi-VO-WEB-1080p` | HD WEB, French audio preferred |

Anything else in the UI is residual and can be deleted.

## ⚠️ Radarr Release Profile "French" must stay disabled

Radarr UI → Settings → Profiles → Release Profiles → `French`.

It must stay **Enabled = OFF**. Otherwise Radarr rejects every release whose
title doesn't literally contain `FR`, `FRA`, or `FRENCH` — including the UHD
BluRay multi-language rips that DO contain a French audio track but only
mention English in the title. Custom Formats from Recyclarr already prefer
French audio via scoring; the hard required-terms filter on top is too strict
and causes mass rejection.

**This setting lives in Radarr's SQLite DB (in the PVC), not in Git.** If
the Radarr PVC is ever reset or recreated, re-disable this profile manually.

```bash
# Disable via API (alternative to UI)
RADARR_KEY=$(kubectl -n selfhosted get secret glance-secret -o jsonpath='{.data.RADARR_API_KEY}' | base64 -d)
kubectl -n downloads port-forward svc/radarr 17878:7878 &
PF=$!; sleep 2
curl -s -H "X-Api-Key: $RADARR_KEY" http://localhost:17878/api/v3/releaseprofile/1 \
  | python3 -c "import json,sys;d=json.load(sys.stdin);d['enabled']=False;print(json.dumps(d))" \
  | curl -s -X PUT -H "X-Api-Key: $RADARR_KEY" -H "Content-Type: application/json" \
      -d @- http://localhost:17878/api/v3/releaseprofile/1
kill $PF
```

## Sabnzbd `_UNPACK_*` stuck folders

Sabnzbd intermittently fails the rename step after a successful unpack
(recurring `OSError: Bad file descriptor`). The folder stays prefixed
`_UNPACK_*` and Sonarr/Radarr safely ignore it during import scans.

The cluster runs a CronJob that auto-fixes this every 30 minutes —
`kubernetes/apps/downloads/unpack-healer/app/cronjob.yaml`. Recovery
window is bounded at 30 minutes.

Manual run (emergency or to verify):

```bash
kubectl -n downloads create job --from=cronjob/unpack-healer healer-now
kubectl -n downloads logs job/healer-now
kubectl -n downloads delete job healer-now
```

If a download is stuck because Sonarr/Radarr already gave up retrying after
the rename fix:

```bash
# Trigger a fresh import scan (Sonarr)
SONARR_KEY=$(kubectl -n selfhosted get secret glance-secret -o jsonpath='{.data.SONARR_API_KEY}' | base64 -d)
kubectl -n downloads port-forward svc/sonarr 18989:8989 &
PF=$!; sleep 2
curl -s -X POST -H "X-Api-Key: $SONARR_KEY" -H "Content-Type: application/json" \
  -d '{"name":"DownloadedEpisodesScan"}' \
  http://localhost:18989/api/v3/command
kill $PF
```

If a queue item is in a permanent "completed - no files eligible" loop
because the original folder name no longer exists, delete it from the queue:

Sonarr UI → Activity → Queue → tick the offending entries → Remove (uncheck
"Add to blocklist" so it can re-grab if needed).

## Diagnose a "wanted/missing" movie that won't grab

1. Open the movie's page in Radarr.
2. Click the magnifier → **Interactive Search**.
3. If the list is empty → indexer issue. Check Prowlarr → Indexers status.
4. If the list has releases but none match (all rejected) → expand a
   rejected release to read the rejection reason. Common reasons:
   - `Does not contain one of the required terms: FR, FRA, FRENCH` →
     the disabled French Release Profile somehow got re-enabled. See top
     of this runbook.
   - `WEBDL-2160p is not wanted in profile` → the assigned Quality
     Profile only accepts HD. Reassign the movie to `SQP-1 (2160p)`.
   - `Custom Formats … score N below Movie's profile minimum M` → no
     release reaches the profile's minimum format score. Lower the
     minimum or move the movie to a less strict profile.

## Reassign movies to a different Quality Profile in bulk

```bash
RADARR_KEY=$(kubectl -n selfhosted get secret glance-secret -o jsonpath='{.data.RADARR_API_KEY}' | base64 -d)
kubectl -n downloads port-forward svc/radarr 17878:7878 &
PF=$!; sleep 2
# Example: move movies 22 and 35 to SQP-1 (2160p) which has id 7
curl -s -X PUT -H "X-Api-Key: $RADARR_KEY" -H "Content-Type: application/json" \
  -d '{"movieIds":[22,35],"qualityProfileId":7}' \
  http://localhost:17878/api/v3/movie/editor
kill $PF
```

Same shape for Sonarr (`/api/v3/series/editor` with `seriesIds`).

## When Recyclarr complains

Recyclarr is a CronJob (`recyclarr` in `downloads`). Logs are short-lived
(the CronJob keeps only the last successful run + 3 last failures).

```bash
# Manual run + read logs
kubectl -n downloads create job --from=cronjob/recyclarr recyclarr-now
kubectl -n downloads logs job/recyclarr-now
kubectl -n downloads delete job recyclarr-now
```

If Recyclarr crashes with `Property 'X' not found on type RootConfigYaml`,
that section of `kubernetes/apps/downloads/recyclarr/app/config/recyclarr.yml`
is unsupported by the current Recyclarr version. Comment the block out
(the secret entry can stay).
