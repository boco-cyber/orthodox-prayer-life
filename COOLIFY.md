# Deploy with Coolify

Create a new application from the public Git repository:

- Repository: `https://github.com/boco-cyber/orthodox-prayer-life`
- Branch: `main`
- Build pack: Dockerfile
- Base directory: `/`
- Dockerfile: `/Dockerfile`
- Container port: `8000`
- Health check: HTTP GET `/health`, port `8000`
- Domain: the HTTPS API domain assigned to this application

Coolify provides the reverse proxy and HTTPS. The application image already contains the read-only library database; no host filesystem mount or database service is needed. Do not deploy the standalone Caddy proxy on Coolify.

`CORS_ORIGINS` defaults to `*`, allowing websites to read this public API without cookies. Optionally set a comma-separated origin allowlist. `DATABASE_PATH` is set in the Docker image and should not need changing.

After deployment, check `/health`, `/v1/status`, `/docs`, and `/v1/bible/AVD/John/3/16`. `/v1/bible/NKJV/John/3/16` intentionally reports that a licensed NKJV source is required.

For a Docker Compose resource instead, select `/compose.coolify.yaml`. Configure Coolify's domain for service `api` at port `8000`. This file uses the database baked into the image rather than a host bind mount.

## Configured instance

- Public API: https://prayerlife.copticfaith.org
- Coolify project: `Orthodox Prayer Life` (`dvtwf7w95eo2nhdlmnl9rzsx`)
- Environment: `production` (`jgfn2mwlio4dcsq9k7q43ezw`)
- Application: `orthodox-prayer-life-api` (`sk1kcdxtp8xshkylhb6vncmg`)
- Uses AboHub (`155.248.209.35`) and its `coolify` Docker network.
- Cloudflare proxied A record for `prayerlife` points to `155.248.209.35`.

The image includes `curl` because Coolify's generated health check requires it. Pushes to `main` automatically deploy through the signed GitHub webhook; Coolify remains the deployment manager.

## Production server

Runtime: **AboHub (`155.248.209.35`)**. Control plane: `https://hub.copticfaith.org`
on `163.192.16.13`. See [DEPLOYMENT.md](DEPLOYMENT.md) for the current identifiers,
GitHub deployment trigger, data, and recovery.
