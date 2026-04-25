#!/bin/bash
# Deployment script for Setback game server
# Usage: ./deploy.sh <instance-ip>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <instance-ip>"
    echo "Example: $0 54.123.45.67"
    exit 1
fi

INSTANCE_IP=$1
# Try DO key first, fall back to AWS key
if [ -f "$HOME/.ssh/setback-do-key" ]; then
    SSH_KEY="$HOME/.ssh/setback-do-key"
else
    SSH_KEY="$HOME/.ssh/setback-aws-key"
fi
DEPLOY_USER="root"  # DigitalOcean droplets use root by default
APP_DIR="/opt/setback"

echo "Deploying to $INSTANCE_IP..."

# Create a temporary directory for deployment
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy application files (excluding unnecessary files)
echo "Preparing deployment package..."
rsync -av \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.ruff_cache' \
    --exclude='deploy' \
    --exclude='.project' \
    ../ "$TEMP_DIR/"

# Deploy to server
echo "Copying files to server..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$DEPLOY_USER@$INSTANCE_IP" "sudo mkdir -p $APP_DIR && sudo chown $DEPLOY_USER:$DEPLOY_USER $APP_DIR"
rsync -av -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    "$TEMP_DIR/" \
    "$DEPLOY_USER@$INSTANCE_IP:$APP_DIR/"

# Check if .env.production exists locally and copy it
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env.production" ]; then
    echo "Copying production environment variables..."
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
        "$SCRIPT_DIR/.env.production" \
        "$DEPLOY_USER@$INSTANCE_IP:$APP_DIR/.env"
else
    echo "WARNING: $SCRIPT_DIR/.env.production not found!"
    echo "Create it from $SCRIPT_DIR/.env.production.example and set BASE_URL"
fi

# Start services
echo "Starting services..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$DEPLOY_USER@$INSTANCE_IP" << 'ENDSSH'
set -e

# Wait for docker to be ready
echo "Checking if Docker is installed..."
timeout=300
elapsed=0
while ! command -v docker &> /dev/null; do
    if [ $elapsed -ge $timeout ]; then
        echo "ERROR: Docker installation timed out after ${timeout}s"
        echo "The instance may still be initializing. Check /var/log/cloud-init-output.log"
        exit 1
    fi
    echo "Waiting for Docker to be installed... (${elapsed}s/${timeout}s)"
    sleep 5
    elapsed=$((elapsed + 5))
done

# Check if docker service is running
echo "Checking if Docker service is running..."
if ! sudo systemctl is-active --quiet docker; then
    echo "Starting Docker service..."
    sudo systemctl start docker
fi

# Verify docker works (may need to use newgrp or sg to activate group membership)
if ! docker ps &> /dev/null; then
    echo "Docker group membership not active, using sudo for docker commands..."
    USE_SUDO="sudo"
else
    USE_SUDO=""
fi

cd /opt/setback
echo "Pulling latest images..."
$USE_SUDO docker compose pull

echo "Building application..."
$USE_SUDO docker compose build

echo "Stopping existing containers..."
$USE_SUDO docker compose down || true

echo "Starting containers..."
$USE_SUDO docker compose up -d

echo "Container status:"
$USE_SUDO docker compose ps
ENDSSH

echo ""
echo "Deployment complete!"
echo "Access your server at: http://$INSTANCE_IP"
echo ""
echo "To check logs: ssh -i $SSH_KEY $DEPLOY_USER@$INSTANCE_IP 'cd /opt/setback && docker compose logs -f'"
