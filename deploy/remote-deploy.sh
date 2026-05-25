#!/bin/bash

set -euo pipefail

: "${APP_DIR:?APP_DIR must be set}"

DOCKER=""

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

die() {
    echo "ERROR: $1" >&2
    exit 1
}

pick_docker_runner() {
    if ! command -v docker >/dev/null 2>&1; then
        die "docker is not installed on the remote host"
    fi

    if ! systemctl is-active --quiet docker; then
        sudo systemctl start docker
    fi

    if docker ps >/dev/null 2>&1; then
        DOCKER="docker"
    else
        DOCKER="sudo docker"
    fi
}

compose() {
    $DOCKER compose "$@"
}

pick_docker_runner
cd "$APP_DIR"

log "Pulling base images"
compose pull

log "Building application image"
compose build

log "Stopping existing containers"
compose down || true

log "Starting database dependencies"
compose up -d --wait postgres redis

log "Running database migrations"
compose run --rm --no-deps -T web /app/.venv/bin/alembic upgrade head < /dev/null

log "Starting application services"
compose up -d web caddy

log "Container status"
compose ps
