FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
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
    libusb-1.0-0-dev \
    usbmuxd \
    avahi-daemon \
    avahi-utils \
    libnss-mdns \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig

# Create supervisor config for managing services
RUN mkdir -p /etc/supervisor/conf.d

COPY supervisord.conf /etc/supervisor/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
