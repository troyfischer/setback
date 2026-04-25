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
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
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
