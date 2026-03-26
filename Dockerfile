# runtime only — simc binary comes from named volume (simc_bin)
# First-time init: run `docker compose run --rm simc-builder` before starting the app
# or let the init-simc service handle it (see docker-compose.yml)
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    libcurl4 libssl3 \
    locales \
    openssh-client \
    && locale-gen en_US.UTF-8 en_GB.UTF-8 \
    && update-locale LANG=en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

COPY frontend/ ./frontend/

RUN mkdir -p /app/results /app/SimulationCraft && \
    echo "Generating build version..." && \
    BUILD_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo "dev") && \
    echo "Build version: $BUILD_VERSION" && \
    find /app/frontend -name "*.html" -exec sed -i "s/?v=[0-9]*/?v=$BUILD_VERSION/g" {} \; && \
    echo "Version tags updated"

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
