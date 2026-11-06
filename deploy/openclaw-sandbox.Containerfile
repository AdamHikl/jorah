# OpenClaw's default sandbox image (docs: gateway/sandboxing/images-and-setup.md), built with rootless Podman as jorah:
#   podman build -t openclaw-sandbox:bookworm-slim -f /opt/jorah/deploy/openclaw-sandbox.Containerfile /opt/jorah/deploy
# The base is pinned by digest, measured 2026-11-06. A new digest is a supply-chain change and gets its own yes.
FROM docker.io/library/debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash ca-certificates curl git jq python3 ripgrep \
  && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox
CMD ["sleep", "infinity"]
