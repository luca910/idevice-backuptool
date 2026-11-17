# syntax=docker/dockerfile:1

#
# Stage 1: build libgeneral, libimobiledevice, usbmuxd2 and friends.
# Everything is pinned via ARGs so builds are reproducible; override with
# e.g. `docker build --build-arg LIBIMOBILEDEVICE_VERSION=master .`
#
FROM ubuntu:latest AS builder

ARG LIBGENERAL_VERSION=93
ARG LIBIMOBILEDEVICE_GLUE_VERSION=1.3.3
ARG LIBTATSU_VERSION=1.1.1
ARG LIBUSBMUXD_VERSION=2.1.1
ARG LIBIMOBILEDEVICE_VERSION=1.4.0
ARG USBMUXD2_REF=17a8f5b19c21e36a80770fdb44a1648046b8dc7d

ENV DEBIAN_FRONTEND=noninteractive

# Install base tools + every build dependency + clang
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config git ca-certificates autoconf automake libtool \
    libplist-dev libssl-dev libusb-1.0-0-dev libavahi-client-dev \
    libavahi-common-dev zlib1g-dev libcurl4-openssl-dev python3-dev \
    clang libc++-dev libc++abi-dev \
    && rm -rf /var/lib/apt/lists/*

# Use clang for everything to avoid "undefined reference" errors
ENV CC=clang
ENV CXX=clang++
ENV CXXFLAGS="-std=c++20 -stdlib=libc++"

WORKDIR /tmp

# Build everything in dependency order. Shallow clones of pinned refs,
# except libgeneral: its version is derived from commit count, which a
# shallow clone would break (usbmuxd2 requires libgeneral >= 72).
# usbmuxd2 (fosple fork) has no release tags, so its ARG pins a commit.
# One RUN per project for granular layer caching.
RUN git clone --branch "${LIBGENERAL_VERSION}" https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral && ./autogen.sh --prefix=/usr && make -j"$(nproc)" install && ldconfig

RUN cd /tmp && git clone --depth 1 --branch "${LIBIMOBILEDEVICE_GLUE_VERSION}" https://github.com/libimobiledevice/libimobiledevice-glue.git \
    && cd libimobiledevice-glue && ./autogen.sh --prefix=/usr && make -j"$(nproc)" install && ldconfig

RUN cd /tmp && git clone --depth 1 --branch "${LIBTATSU_VERSION}" https://github.com/libimobiledevice/libtatsu.git \
    && cd libtatsu && ./autogen.sh --prefix=/usr && make -j"$(nproc)" install && ldconfig

RUN cd /tmp && git clone --depth 1 --branch "${LIBUSBMUXD_VERSION}" https://github.com/libimobiledevice/libusbmuxd.git \
    && cd libusbmuxd && ./autogen.sh --prefix=/usr && make -j"$(nproc)" install && ldconfig

RUN cd /tmp && git clone --depth 1 --branch "${LIBIMOBILEDEVICE_VERSION}" https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice && ./autogen.sh --prefix=/usr && make -j"$(nproc)" install && ldconfig

RUN cd /tmp && git clone https://github.com/fosple/usbmuxd2.git \
    && cd usbmuxd2 && git checkout "${USBMUXD2_REF}" \
    && ./autogen.sh --prefix=/usr CC=clang CXX=clang++ \
    && make -j"$(nproc)" && make install && ldconfig

# Copy only the build products (binaries + shared libs) to a known location
# so the runtime stage stays small.
RUN set -eux; \
    mkdir -p /artifacts/bin /artifacts/lib; \
    find /usr/bin /usr/sbin /usr/local/bin /usr/local/sbin -maxdepth 1 -type f \
        \( -name 'idevice*' -o -name 'usbmuxd' \) -exec cp -a {} /artifacts/bin/ \; ; \
    for d in /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib /usr/local/lib/x86_64-linux-gnu; do \
        [ -d "$d" ] || continue; \
        find "$d" -maxdepth 1 -type f \
            \( -name 'libgeneral*' -o -name 'libplist*' -o -name 'libimobiledevice*' \
               -o -name 'libusbmuxd*' -o -name 'libtatsu*' \) -exec cp -a {} /artifacts/lib/ \; ; \
    done; \
    ls -la /artifacts/bin /artifacts/lib

#
# Stage 2: runtime image - no compilers, no build toolchain.
#
FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# Runtime packages only. The -dev packages are pinned the same way as in the
# builder so the shared libraries match across Ubuntu base image versions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 dbus avahi-daemon avahi-utils \
    libplist-dev libssl-dev libusb-1.0-0-dev libavahi-client-dev \
    libavahi-common-dev zlib1g-dev libcurl4-openssl-dev \
    libc++-dev libc++abi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /artifacts/bin/ /usr/bin/
COPY --from=builder /artifacts/lib/ /usr/lib/
RUN ldconfig

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket
ENV BACKUP_DIR=/mnt/backups

WORKDIR /app

COPY ./src ./

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/status', timeout=5)"

CMD ["python3", "script.py"]
