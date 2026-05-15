FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install all build tools and development headers
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
    libavahi-client-dev \
    libudev-dev \
    libdbus-1-dev \
    libusb-1.0-0-dev \
    avahi-utils \
    udev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. Build usbmuxd 
# Discovery is automatically included because libavahi-client-dev is present.
RUN git clone https://github.com/tihmstar/usbmuxd2.git \
    && cd usbmuxd2 \
    && ./autogen.sh --prefix=/usr --with-udev \
    && make -j$(nproc) \
    && make install

# 3. Build libimobiledevice 
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# 4. Cleanup
RUN rm -rf /tmp/*

# 5. Configs
ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

# Corrected CMD: No '&&' in exec form. 
# -f keeps the container running.
CMD ["usbmuxd2", "-f", "-v", "-u", "0"]
