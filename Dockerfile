FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install dependencies for usbmuxd2 and its sub-libraries
RUN apt update && apt install -y \
    build-essential \
    pkg-config \
    git \
    autoconf \
    automake \
    libtool \
    libplist-dev \
    libssl-dev \
    libusb-1.0-0-dev \
    libavahi-client-dev \
    libavahi-common-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. usbmuxd2 requires tihmstar's 'libgeneral' to build
RUN git clone https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install

# 3. Build usbmuxd2
# Note: usbmuxd2 is often better at network discovery by default
RUN git clone https://github.com/tihmstar/usbmuxd2.git \
    && cd usbmuxd2 \
    && git submodule update --init --recursive \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install

# 4. Build libimobiledevice (for tools like idevicebackup2)
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# Cleanup
RUN rm -rf /tmp/*

# Point to host DBus for Avahi communication
ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

# usbmuxd2 uses similar flags, but check 'usbmuxd2 --help' if it acts up
# -f: foreground, -v: verbose
CMD ["usbmuxd2", "-f", "-v"]
