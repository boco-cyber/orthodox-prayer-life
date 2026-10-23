# Production deployment

Updated 2026-10-23 after migration to AboHub.

| Setting | Value |
|---|---|
| Runtime server | AboHub — `155.248.209.35` |
| Coolify server UUID | `qit4mjbfkpigeillcdnw5k0c` |
| Docker destination UUID | `z6ty1zudb3wyoxmenu8i1psb` |
| Coolify dashboard / API | `https://hub.copticfaith.org` on `163.192.16.13` |
| Application | `orthodox-prayer-life-api` |
| Application UUID | `sk1kcdxtp8xshkylhb6vncmg` |
| Production Git branch | `main` |
| Public URL | https://prayerlife.copticfaith.org |

## Updates from GitHub

A signed GitHub `push` webhook calls `https://hub.copticfaith.org/webhooks/source/github/events/manual`. Its secret is held in GitHub and Coolify, never in this repository.

Push application changes to `main`. Coolify uses the same application UUID, settings, environment variables, and repository authentication, and builds/runs the update on AboHub. Deployment calls target the Coolify control plane, not the AboHub IP directly. Do not point `COOLIFY_BASE_URL` or `COOLIFY_RESOLVE` at AboHub.

## Data and secrets

The read-only library database is baked into the image. There are no persistent application volumes.

Cloudflare's existing proxied A records point at `155.248.209.35`. AboHub's Oracle network security group and operating-system firewall allow TCP 80 and 443. SSH administration uses `ubuntu@155.248.209.35`; Coolify uses its dedicated management key.

## Recovery

Migration snapshots are retained under `/root/abohub-migration-20261023` on the original server (`163.192.16.13`). WordPress rollback containers and volumes remain on the original server. Post-migration cleanup removed the six stopped stateless API containers and unused image/build cache; rebuild those APIs from their recorded Git revision with Coolify when rolling back. The original proxy forwards these domains to AboHub for clients using the old origin. Before rolling WordPress back, take a fresh database/file backup from AboHub so new writes are preserved.
