# vci-capture
################################################################################
# Base
################################################################################
FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel AS base

WORKDIR /srv/vci-capture

RUN echo "\
  Acquire::http::proxy \"http://web-proxy.cs.uni-bonn.de:3128/\";\n\
  Acquire::https::proxy \"http://web-proxy.cs.uni-bonn.de:3128/\";\n\
  Acquire::ftp::proxy \"http://web-proxy.cs.uni-bonn.de:3128/\";\n\
  " > /etc/apt/apt.conf.d/95proxies
ENV HTTP_PROXY=http://web-proxy.cs.uni-bonn.de:3128/
ENV HTTPS_PROXY=http://web-proxy.cs.uni-bonn.de:3128/


# ----------------------------------------

# Install dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN \
  BASE_DEPENDENCIES="\
  git \
  gdb \
  libgl1 \
  libssl-dev \
  libglib2.0-0 \
  libelf-dev libusb-1.0-0-dev libraw1394-11 libtiff-dev libcurl4 lshw pciutils" \
  && apt update \
  && apt install -y --no-install-recommends $BASE_DEPENDENCIES \
  && rm -r /var/lib/apt/lists/* \
  && apt clean \
  && rm -rf \
  /tmp/* \
  /var/log/dpkg.log \
  /var/log/alternatives.log \
  /var/log/apt \
  /var/lib/apt/lists/*

RUN ln -sf /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /opt/conda/lib/libstdc++.so.6

RUN git config --global http.https://github.com.proxy http://web-proxy.cs.uni-bonn.de:3128/

# Install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


################################################################################
# Development
################################################################################
FROM base AS development
RUN \
  DEV_DEPENDENCIES="\
  openssh-client" \
  && apt update \
  && apt install -y --no-install-recommends $DEV_DEPENDENCIES \
  && rm -r /var/lib/apt/lists/* \
  && apt clean \
  && rm -rf \
  /tmp/* \
  /var/log/dpkg.log \
  /var/log/alternatives.log \
  /var/log/apt \
  /var/lib/apt/lists/*

# Install dev requirements
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt


################################################################################
# Production
################################################################################
FROM base AS production

# Copy all code
COPY . /srv/vci-capture
