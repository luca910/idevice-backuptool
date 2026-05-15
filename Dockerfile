FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install Base Tools + Every dependency + Clang
RUN apt update && apt install -y \
    build-essential pkg-config git autoconf automake libtool \
    libplist-dev libssl-dev libusb-1.0-0-dev libavahi-client-dev \
    libavahi-common-dev zlib1g-dev libcurl4-openssl-dev python3-dev \
    clang libc++-dev libc++abi-dev avahi-daemon avahi-utils libavahi-client3\
    && rm -rf /var/lib/apt/lists/*

# Global setting: Use Clang for EVERYTHING to avoid "undefined reference" errors
ENV CC=clang
ENV CXX=clang++
ENV CXXFLAGS="-std=c++20 -stdlib=libc++"

WORKDIR /tmp

# 2. Build libgeneral (With Clang)
RUN git clone https://github.com/tihmstar/libgeneral.git \
    && cd libgeneral && ./autogen.sh --prefix=/usr && make install

# 3. Build libimobiledevice-glue (With Clang)
RUN git clone https://github.com/libimobiledevice/libimobiledevice-glue.git \
    && cd libimobiledevice-glue && ./autogen.sh --prefix=/usr && make install

# 4. Build libtatsu (With Clang)
RUN git clone https://github.com/libimobiledevice/libtatsu.git \
    && cd libtatsu && ./autogen.sh --prefix=/usr && make install

# 5. Build libusbmuxd (With Clang)
RUN git clone https://github.com/libimobiledevice/libusbmuxd.git \
    && cd libusbmuxd && ./autogen.sh --prefix=/usr && make install

# 6. Build libimobiledevice (With Clang)
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice && ./autogen.sh --prefix=/usr && make install && ldconfig

# 7. Build usbmuxd2 (With Clang)
RUN git clone https://github.com/fosple/usbmuxd2.git \
    && cd usbmuxd2 \
    && ./autogen.sh \
    && ./configure CC=clang CXX=clang++ \
    && make \
    && make install


RUN rm -rf /tmp/*

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

CMD ["usbmuxd", "-v"]
