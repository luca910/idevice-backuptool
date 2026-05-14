FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt update && apt install -y \
    build-essential \
    pkg-config \
    checkinstall \
    git \
    autoconf \
    automake \
    libtool-bin \
    libplist-dev \
    libusbmuxd-dev \
    libimobiledevice-glue-dev \
    libtatsu-dev \
    libssl-dev \
    usbmuxd \
    && rm -rf /var/lib/apt/lists/*

# Clone and build libimobiledevice
WORKDIR /opt

RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# Keep container alive and start usbmuxd
CMD usbmuxd && tail -f /dev/null
