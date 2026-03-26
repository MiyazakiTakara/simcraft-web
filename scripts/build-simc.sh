#!/bin/bash
# Uruchamiany WEWNĄTRZ kontenera simc-builder.
# Kompiluje simc i podmienia binarkę w named volume /simc_out.
set -euo pipefail

SIMC_REPO="https://github.com/simulationcraft/simc.git"
SIMC_BRANCH="midnight"
BUILD_DIR="/tmp/simc-build"
OUT_DIR="/simc_out"

echo "[build-simc] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Klonuj lub pull
if [ -d "$BUILD_DIR/.git" ]; then
    echo "[build-simc] git pull"
    git -C "$BUILD_DIR" fetch --depth=1 origin "$SIMC_BRANCH"
    git -C "$BUILD_DIR" reset --hard "origin/$SIMC_BRANCH"
else
    echo "[build-simc] git clone"
    git clone --depth=1 --branch "$SIMC_BRANCH" "$SIMC_REPO" "$BUILD_DIR"
fi

cd "$BUILD_DIR"

# Build
echo "[build-simc] cmake configure"
cmake -DBUILD_GUI=OFF -DCMAKE_BUILD_TYPE=Release -S . -B build

echo "[build-simc] cmake build ($(nproc) cores)"
cmake --build build --parallel "$(nproc)"

BUILT_BIN="$BUILD_DIR/build/simc"
if [ ! -f "$BUILT_BIN" ]; then
    echo "[build-simc] ERROR: binary not found at $BUILT_BIN"
    exit 1
fi

# Atomowa podmiana
mkdir -p "$OUT_DIR"
cp "$BUILT_BIN" "$OUT_DIR/simc.new"
chmod 755 "$OUT_DIR/simc.new"

if [ -f "$OUT_DIR/simc" ]; then
    mv "$OUT_DIR/simc" "$OUT_DIR/simc.bak"
fi
mv "$OUT_DIR/simc.new" "$OUT_DIR/simc"

# simc nie ma flagi --version — wypisuje wersję przy uruchomieniu bez argumentów (2>&1, linia 2)
VERSION=$("$OUT_DIR/simc" 2>&1 | grep -m1 'SimulationCraft' | grep -oP 'SimulationCraft \K[^ ]+' || echo "unknown")
echo "[build-simc] SUCCESS version=$VERSION"
echo "SIMC_VERSION=$VERSION"
