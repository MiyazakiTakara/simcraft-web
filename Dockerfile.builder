FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git cmake make g++ \
    libssl-dev zlib1g-dev \
    libcurl4-openssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/build-simc.sh /build.sh
RUN chmod +x /build.sh

ENTRYPOINT ["/build.sh"]
