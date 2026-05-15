FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install ONLY the build tools and libraries. 
# We do NOT install 'usbmuxd' via apt to avoid conflicts.
RUN apt update && apt install -y \
    build-essential \
    pkg-config \
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
    avahi-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. Build usbmuxd with NETWORK enabled
# This is the "brain" that handles the Wi-Fi discovery
RUN git clone https://github.com/libimobiledevice/usbmuxd.git \
    && cd usbmuxd \
    && ./autogen.sh --prefix=/usr --enable-network --with-udev \
    && make -j$(nproc) \
    && make install

# 3. Build libimobiledevice 
# This provides the actual backup tools (idevicebackup2, etc.)
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# 4. Cleanup build artifacts to keep image small
RUN rm -rf /tmp/*

# 5. Configs
ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

# We use -u 0 (root) because the 'usbmux' user won't exist 
# since we didn't install the apt package.
CMD ["usbmuxd", "-f", "-v", "-u", "0","&&","tail","-f","/dev/null"]
