FROM ubuntu:24.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends xorriso isolinux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
