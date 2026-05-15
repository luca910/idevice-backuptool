FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Essential build tools and libraries
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
    # Added for usbmuxd2 specifically
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. Build libgeneral (Required by usbmuxd2)
RUN git clone https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install

# 3. Build usbmuxd2
# We pull specifically from the main branch and ensure submodules are ready
RUN git clone https://github.com/tihmstar/usbmuxd2.git \
    && cd usbmuxd2 \
    && git submodule update --init --recursive \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install

# 4. Build libimobiledevice (for the backup tools)
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && ldconfig

RUN rm -rf /tmp/*

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

# usbmuxd2 doesn't use the same flags as the original. 
# It usually runs in the foreground by default or with minimal flags.
CMD ["usbmuxd2", "-v"]
