FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install all dependencies
RUN apt update && apt install -y \
    build-essential pkg-config git autoconf automake libtool \
    libplist-dev libssl-dev libusb-1.0-0-dev libavahi-client-dev \
    libavahi-common-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. Build libgeneral (Required for almost everything below)
RUN git clone https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install

# 3. CRITICAL: Build libimobiledevice FIRST
# usbmuxd2 needs these headers to enable its WiFi/WIFIDevice logic
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# 4. Build usbmuxd2
# We add CXXFLAGS="-fpermissive" to bypass the MUXException inheritance error
RUN git clone https://github.com/tihmstar/usbmuxd2.git \
    && cd usbmuxd2 \
    && git submodule update --init --recursive \
    && ./autogen.sh --prefix=/usr CXXFLAGS="-std=c++20 -fpermissive" \
    && make -j$(nproc) \
    && make install

RUN rm -rf /tmp/*

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

# usbmuxd2 log verbosity is controlled by -v
CMD ["usbmuxd2", "-v"]
