#!/bin/bash
# Uruchamiany NA HOŚCIE przez FastAPI przez SSH.
# Buduje i podmienia binarkę simc w named volume.
#
# Wymagania na hoście:
#   - Docker zainstalowany, użytkownik deploy w grupie docker
#   - Image simc-builder zbudowany: docker build -f Dockerfile.builder -t simc-builder .
#   - Named volume: docker volume create simcraft-web_simc_bin
#     (lub powstaje automatycznie przy docker compose up)
#
# Użycie:
#   /opt/scripts/rebuild-simc.sh
#   Zwraca 0 na sukces, niezerowy na błąd.
#   Ostatnia linia stdout zawiera: SIMC_VERSION=<wersja>

set -euo pipefail

COMPOSE_DIR="/etc/komodo/stacks/simcraft-web"
VOLUME_NAME="simcraft-web_simc_bin"
BUILDER_IMAGE="simcraft-web-simc-builder"
LOCK_FILE="/tmp/simc-rebuild.lock"

# Mutex — tylko jeden rebuild naraz
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[rebuild-simc] ERROR: another rebuild is already running"
    exit 1
fi

echo "[rebuild-simc] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Upewnij się że volume istnieje
docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1 || \
    docker volume create "$VOLUME_NAME"

# Zbuduj/odśwież image buildera (zawsze, żeby mieć aktualne skrypty)
echo "[rebuild-simc] building simc-builder image"
docker build \
    -f "$COMPOSE_DIR/Dockerfile.builder" \
    -t "$BUILDER_IMAGE" \
    "$COMPOSE_DIR"

# Uruchom builder jako jednorazowy kontener
echo "[rebuild-simc] running simc-builder container"
docker run --rm \
    --name simc-builder-run \
    -v "${VOLUME_NAME}:/simc_out" \
    "$BUILDER_IMAGE"

echo "[rebuild-simc] DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
