# Deployment Guide

## Prerequisites

1. **DigitalOcean Account**: Sign up at https://digitalocean.com
2. **DigitalOcean API Token**: Create at https://cloud.digitalocean.com/account/api/tokens
3. **SSH Key**: Generate if you don't have one

## Setup Steps

### 1. Generate SSH Key (if needed)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/setback-do-key -C "setback-deployment"
```

### 2. Install Pulumi Dependencies

```bash
cd deploy
uv sync
```

### 3. Configure Pulumi

Set your DigitalOcean API token:

```bash
cd deploy
pulumi config set digitalocean:token YOUR_DO_TOKEN --secret
```

The token will be encrypted and stored in `Pulumi.dev.yaml`.

### 4. Deploy Infrastructure

```bash
pulumi up
```

This will create:
- DigitalOcean Droplet (s-2vcpu-2gb, ~$18/month)
- Cloud Firewall (SSH, HTTP, HTTPS)
- DNS A record: setback.troyfischer.net

### 5. Configure Production Environment

```bash
cp .env.production.example .env.production
```

Edit `.env.production` and set:
```bash
BASE_URL=https://setback.troyfischer.net
CLIENT_ORIGIN=https://setback.troyfischer.net
DATABASE_URL=postgresql://app:<db-password>@postgres:5432/appdb
REDIS_URL=redis://redis:6379/0
POSTGRES_PASSWORD=<db-password>
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
AUTO_CREATE_SCHEMA=false
```

### 6. Update Google OAuth

Add authorized redirect URI in Google Cloud Console:
```
https://setback.troyfischer.net/auth/google/callback
```

### 7. Deploy Application

```bash
# Get the IP from pulumi output
pulumi stack output public_ip

# Deploy your app
./deploy.sh <droplet-ip>
```

Deployment behavior:
- the script requires a valid `deploy/.env.production`
- the production `Caddyfile` is generated from `BASE_URL` at deploy time
- the script assumes the droplet is already Docker-ready from provisioning
- the script starts `postgres` and `redis`
- runs `alembic upgrade head` in a one-off app container
- starts `web` and `caddy` only after migrations succeed

This keeps production schema changes explicit and prevents the app from starting against an outdated schema.

### GitHub Actions Release Setup

The repository now includes `.github/workflows/release.yml`. It runs verification on every release tag or manual dispatch, then deploys through the existing `deploy.sh` script.

Create a GitHub Actions environment named `production` and configure:

Environment variables:
```bash
BASE_URL=https://setback.troyfischer.net
CLIENT_ORIGIN=https://setback.troyfischer.net
DEPLOY_HOST=<droplet-ip>
REDIS_URL=redis://redis:6379/0
```

Environment secrets:
```bash
DEPLOY_SSH_KEY=<private key contents>
DATABASE_URL=postgresql://app:<db-password>@postgres:5432/appdb
POSTGRES_PASSWORD=<db-password>
SESSION_SECRET=<random session secret>
JWT_SECRET=<random jwt secret>
GOOGLE_CLIENT_ID=<google oauth client id>
GOOGLE_CLIENT_SECRET=<google oauth client secret>
```

You can configure the environment non-interactively with GitHub CLI:

```bash
cd python
cp deploy/.env.production.example deploy/.env.production
$EDITOR deploy/.env.production
./deploy/configure-github-actions.sh --deploy-host <droplet-ip>
```

What the script does:
- creates the `production` GitHub Actions environment if it does not exist
- writes environment variables: `BASE_URL`, `CLIENT_ORIGIN`, `DEPLOY_HOST`, `REDIS_URL`
- writes environment secrets: `DEPLOY_SSH_KEY`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `SESSION_SECRET`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

Requirements:
- `gh auth login` completed for the GitHub account that owns or administers the repo
- `deploy/.env.production` present with the production values
- the deployment SSH private key available at `~/.ssh/setback-do-key`, or pass `--ssh-key <path>`

Recommended environment protections:
- require at least one reviewer before deploy jobs run
- restrict deployment branches/tags to your release path
- keep production-only secrets scoped to the `production` environment instead of repository-wide secrets

The workflow is triggered by Git tags matching `v*` and by manual `workflow_dispatch`.

### 8. Verify Deployment

Visit https://setback.troyfischer.net

The first HTTPS request may take ~30 seconds as Caddy provisions the SSL certificate.

## Useful Commands

```bash
# Check deployment status
pulumi stack output

# SSH to droplet
ssh -i ~/.ssh/setback-do-key root@<ip>

# View logs on server
ssh -i ~/.ssh/setback-do-key root@<ip> 'cd /opt/setback && docker compose logs -f'

# Destroy infrastructure
pulumi destroy
```

## Costs

- **Droplet**: s-2vcpu-2gb @ $18/month
- **Bandwidth**: 2TB included
- **DNS**: Free on DigitalOcean

Total: ~$18/month
