FROM nvidia/cuda:10.1-cudnn7-runtime-ubuntu16.04

# Install necessary apt packages
RUN apt-get update && \
        apt-get install -y software-properties-common && \
        add-apt-repository ppa:deadsnakes/ppa && \
        apt-get update -y  && \
        apt-get install -y build-essential python3.6 python3.6-dev python3-pip && \
        # update pip
        python3.6 -m pip install pip --upgrade && \
        cd /usr/local/bin && \
        ln -s /usr/bin/python3.6 python

RUN apt-get install -yq \
    libgtk2.0-dev \
    wget \
    git \
    cmake \
    pkg-config \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    python-numpy \
    libtbb2 \
    libtbb-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libdc1394-22-dev \
    unzip \
    less \
    nano \
    redis-tools

# Install and initialize all python packages for Pipert
COPY requirements1.txt requirements2.txt /
RUN pip3 install --upgrade pip
RUN pip3 install opencv-contrib-python
RUN pip3 install torch
RUN pip3 install -r requirements1.txt
RUN pip3 install -r requirements2.txt

# Install detectron2
RUN python -m pip install detectron2 -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu101/index.html