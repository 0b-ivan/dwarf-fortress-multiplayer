# syntax=docker/dockerfile:1.7

ARG DEBIAN_VERSION=bookworm

FROM debian:${DEBIAN_VERSION}-slim AS sdlbuild
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake ca-certificates curl pkg-config \
      libx11-dev libxext-dev libxcursor-dev libxrandr-dev libxfixes-dev \
      libxi-dev libxss-dev libxkbcommon-dev libgl1-mesa-dev libpulse-dev \
    && rm -rf /var/lib/apt/lists/*
ARG SDL2_VERSION=2.30.9
RUN curl -fsSL \
      "https://github.com/libsdl-org/SDL/releases/download/release-${SDL2_VERSION}/SDL2-${SDL2_VERSION}.tar.gz" \
      -o /tmp/sdl.tgz \
    && tar -xzf /tmp/sdl.tgz -C /tmp \
    && cmake -S "/tmp/SDL2-${SDL2_VERSION}" -B /tmp/sdl-build \
         -DCMAKE_BUILD_TYPE=Release \
         -DSDL_X11_XINPUT=OFF \
         -DSDL_SHARED=ON \
         -DSDL_STATIC=OFF \
         -DSDL_TEST=OFF \
    && cmake --build /tmp/sdl-build -j"$(nproc)" \
    && cmake --install /tmp/sdl-build --prefix /sdl \
    && cp -L /sdl/lib/libSDL2-2.0.so.0 /sdl/libSDL2-2.0.so.0

FROM debian:${DEBIAN_VERSION}-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive \
    CCACHE_DIR=/ccache \
    CCACHE_COMPRESS=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc g++ cmake ninja-build ccache git ca-certificates curl \
      python3 perl zlib1g-dev libsdl2-dev libxml-libxml-perl libxml-libxslt-perl \
      libjpeg62-turbo-dev libpng-dev pkg-config bzip2 \
    && rm -rf /var/lib/apt/lists/*

ARG DFHACK_VERSION=53.16-r1.1
ARG MULTI_DWARF_COMMIT=11ea5b1df1efe599bdb4746f21773f051345a6fe
WORKDIR /build

COPY assets/private/dwarf_fortress_53_16_linux.tar.bz2 /tmp/df.tar.bz2
RUN set -eux; \
    mkdir -p /tmp/dfextract /opt/df; \
    tar -xjf /tmp/df.tar.bz2 -C /tmp/dfextract; \
    if [ -f /tmp/dfextract/dwarfort ]; then \
      cp -a /tmp/dfextract/. /opt/df/; \
    else \
      game_root="$(find /tmp/dfextract -mindepth 1 -maxdepth 1 -type d | head -1)"; \
      test -n "$game_root"; \
      cp -a "$game_root"/. /opt/df/; \
    fi; \
    test -f /opt/df/dwarfort; \
    chmod +x /opt/df/dwarfort; \
    rm -rf /tmp/df.tar.bz2 /tmp/dfextract

RUN git clone --recursive --branch "${DFHACK_VERSION}" \
      https://github.com/DFHack/dfhack.git /build/dfhack
RUN git clone https://github.com/SourceAirbender/multi-dwarf.git \
      /build/dfhack/plugins/external/dfcapture_public \
    && cd /build/dfhack/plugins/external/dfcapture_public \
    && git checkout "${MULTI_DWARF_COMMIT}"

COPY scripts/patch-multidwarf-linux.py /usr/local/bin/patch-multidwarf-linux.py
RUN python3 /usr/local/bin/patch-multidwarf-linux.py \
      /build/dfhack/plugins/external/dfcapture_public

RUN --mount=type=cache,target=/ccache \
    cmake -S /build/dfhack -B /build/dfhack/build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/df \
      -DBUILD_DOCS=OFF \
      -DBUILD_STONESENSE=OFF \
      -DBUILD_TESTS=OFF \
    && cmake --build /build/dfhack/build -j"$(nproc)" \
    && cmake --install /build/dfhack/build

RUN set -eux; \
    src=/build/dfhack/plugins/external/dfcapture_public; \
    mkdir -p \
      /opt/df/hack/dfcapture-web \
      /opt/df/hack/lua/plugins \
      /opt/df/hack/scripts/gui; \
    cp -a "$src/web"/. /opt/df/hack/dfcapture-web/; \
    cp "$src/dfcapture.lua" /opt/df/hack/lua/plugins/dfcapture.lua; \
    cp "$src/scripts/gui/dfcapture.lua" /opt/df/hack/scripts/gui/dfcapture.lua; \
    find /opt/df/hack/plugins -maxdepth 1 -type f -name 'dfcapture*' -print; \
    test -n "$(find /opt/df/hack/plugins -maxdepth 1 -type f -name 'dfcapture*.so' -print -quit)"

COPY web/dfcapture-live-audio.css /opt/df/hack/dfcapture-web/css/dfcapture-live-audio.css
COPY web/dfcapture-live-audio.js /opt/df/hack/dfcapture-web/js/dfcapture-live-audio.js
COPY scripts/patch-dfcapture-live-audio.py /usr/local/bin/patch-dfcapture-live-audio.py
RUN python3 /usr/local/bin/patch-dfcapture-live-audio.py \
      /opt/df/hack/dfcapture-web/index.html

COPY --from=sdlbuild /sdl/libSDL2-2.0.so.0 /opt/df/libSDL2-2.0.so.0

FROM debian:${DEBIAN_VERSION}-slim AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      libsdl2-2.0-0 libsdl2-image-2.0-0 \
      libjpeg62-turbo libpng16-16 \
      libgl1 libglu1-mesa libgl1-mesa-dri \
      tigervnc-standalone-server tigervnc-common \
      novnc websockify matchbox-window-manager x11-utils xdotool \
      pulseaudio pulseaudio-utils ffmpeg icecast2 nginx \
      curl ca-certificates procps bzip2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/df /opt/df
COPY config/icecast.xml /etc/icecast2/icecast.xml
COPY config/nginx.conf /etc/nginx/nginx.conf
COPY web/novnc-index.html /opt/novnc-custom/index.html
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p "/root/.local/share/Bay 12 Games/Dwarf Fortress/save" /backups /var/log/df

ENV DISPLAY=:99 \
    TERM=xterm \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    SDL_VIDEODRIVER=x11 \
    SDL_AUDIODRIVER=pulseaudio \
    SDL_RENDER_DRIVER=software \
    DFCAPTURE_PUBLIC_PORT=8765 \
    DFCAPTURE_BACKEND_PORT=8766 \
    LD_LIBRARY_PATH=/opt/df:/opt/df/hack/libs:/opt/df/hack

EXPOSE 8765 6080
WORKDIR /opt/df
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
