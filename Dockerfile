FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Base Build Tools + Every possible library + CLANG
RUN apt update && apt install -y \
    build-essential pkg-config git autoconf automake libtool \
    libplist-dev libssl-dev libusb-1.0-0-dev libavahi-client-dev \
    libavahi-common-dev zlib1g-dev \
    libcurl4-openssl-dev \
    python3-dev \
    # The fix for the "sorry, unimplemented" error
    clang libc++-dev libc++abi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2. Build libgeneral
RUN git clone https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral && ./autogen.sh --prefix=/usr && make install

# 3. Build libimobiledevice-glue
RUN git clone https://github.com/libimobiledevice/libimobiledevice-glue.git \
    && cd libimobiledevice-glue && ./autogen.sh --prefix=/usr && make install

# 4. Build libtatsu
RUN git clone https://github.com/libimobiledevice/libtatsu.git \
    && cd libtatsu && ./autogen.sh --prefix=/usr && make install

# 5. Build libusbmuxd
RUN git clone https://github.com/libimobiledevice/libusbmuxd.git \
    && cd libusbmuxd && ./autogen.sh --prefix=/usr && make install

# 6. Build libimobiledevice
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice && ./autogen.sh --prefix=/usr && make install && ldconfig

# 7. Build usbmuxd2 using Clang
# We force CC and CXX to clang/clang++ to bypass the GCC bug
RUN git clone https://github.com/tihmstar/usbmuxd2.git \
    && cd usbmuxd2 \
    && git submodule update --init --recursive \
    && ./autogen.sh --prefix=/usr \
       CC=clang CXX=clang++ \
       CXXFLAGS="-std=c++20 -stdlib=libc++" \
    && make -j$(nproc) \
    && make install

RUN rm -rf /tmp/*

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

CMD ["usbmuxd2", "-v"]
