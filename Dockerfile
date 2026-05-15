FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies + Avahi client libraries
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
    # Required for Option 2
    avahi-daemon \
    libavahi-client-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build libimobiledevice (Same as before)
WORKDIR /opt
RUN git clone https://github.com/libimobiledevice/libimobiledevice.git \
    && cd libimobiledevice \
    && ./autogen.sh \
    && make -j$(nproc) \
    && make install \
    && ldconfig

# Start usbmuxd with network discovery enabled (-n)
# We run it in the foreground (-f) to keep the container alive
CMD ["usbmuxd", "-f", "-v", "-u", "0","&&","tail","-f","/dev/null"]
