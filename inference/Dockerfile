FROM python:slim AS port-allocator

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends lsof && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install fastapi uvicorn

COPY ./inference/src/port_allocator.py /app/port_allocator.py

EXPOSE 5030

ENTRYPOINT ["python", "-m", "uvicorn", "port_allocator:app"]
CMD ["--host", "0.0.0.0", "--port", "5030"]

FROM --platform=$BUILDPLATFORM debian:bookworm-slim AS platform-tools-downloader

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl unzip ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# android world is using this version
ARG PLATFORM_TOOLS_VERSION=35.0.2
ARG TARGETOS=linux

RUN if [ "$PLATFORM_TOOLS_VERSION" = "latest" ]; then \
        PLATFORM_TOOLS_URL="https://dl.google.com/android/repository/platform-tools-latest-${TARGETOS}.zip"; \
    else \
        PLATFORM_TOOLS_URL="https://dl.google.com/android/repository/platform-tools_r${PLATFORM_TOOLS_VERSION}-${TARGETOS}.zip"; \
    fi && \
    mkdir -p /android/sdk && \
    echo "Downloading platform-tools from $PLATFORM_TOOLS_URL" && \
    curl -fL "$PLATFORM_TOOLS_URL" -o /tmp/platform-tools.zip && \
    unzip /tmp/platform-tools.zip -d /android/sdk && \
    rm /tmp/platform-tools.zip

FROM debian:bookworm-slim AS adb-server

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openssl ca-certificates netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY --from=platform-tools-downloader /android/sdk/platform-tools/adb /usr/local/bin/adb
COPY --chmod=0755 ./inference/extra/adb-server-entrypoint.sh /entrypoint.sh

EXPOSE 5037

CMD ["/entrypoint.sh"]

FROM python:3.11 AS worker-base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git openssl ca-certificates curl ffmpeg netcat-openbsd && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=platform-tools-downloader /android/sdk/platform-tools/adb /usr/local/bin/adb

COPY ./requirements.txt ./setup.py /usr/src/android_lab/
COPY ./android_lab /usr/src/android_lab/android_lab

ADD https://github.com/google-deepmind/android_env.git#1c4e8a92da09ac1886e24f09fa8baa6dddabc4c6 /usr/src/android_env
COPY ./inference/extra/android_env.patch /usr/src/android_env.patch
RUN cd /usr/src/android_env && \
    git apply --check /usr/src/android_env.patch && \
    git apply /usr/src/android_env.patch && \
    rm /usr/src/android_env.patch

ADD https://github.com/google-research/android_world.git#cac18549cd8cbb3094f827939765cebf5877fd1e /usr/src/android_world
COPY ./inference/extra/android_world.patch /usr/src/android_world.patch
RUN cd /usr/src/android_world && \
    git apply --check /usr/src/android_world.patch && \
    git apply /usr/src/android_world.patch && \
    rm /usr/src/android_world.patch

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install \
      --editable /usr/src/android_env \
      --requirement /usr/src/android_world/requirements.txt \
      --editable /usr/src/android_world \
      --requirement /usr/src/android_lab/requirements.txt \
      --editable /usr/src/android_lab

COPY ./inference/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --requirement /app/requirements.txt

COPY ./inference/src /app/src
COPY ./inference/configs /app/configs

COPY --chmod=0755 ./inference/extra/agentrl-worker-entrypoint.sh /entrypoint.sh

ENV TMPDIR=/tmp

FROM worker-base AS android-lab

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/android_lab.yaml"]

FROM worker-base AS android-world

ADD https://storage.googleapis.com/android_env-tasks/2024.05.13-accessibility_forwarder.apk /tmp/2024.05.13-accessibility_forwarder.apk

ENTRYPOINT ["/entrypoint.sh", "-c", "configs/android_world.yaml"]
