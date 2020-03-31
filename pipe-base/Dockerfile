FROM ubuntu:16.04

FROM python:3.6-slim-buster

# Install necessary apt packages
RUN apt-get update -y && \
    apt-get install -yq \
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
    unzip

# Get and build OpenCV 4.0
RUN cd \
    && wget https://github.com/opencv/opencv/archive/4.0.0.zip \
    && unzip 4.0.0.zip \
    && cd opencv-4.0.0 \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make -j8 \
    && make install \
    && cd \
    && rm 4.0.0.zip

# Install dlib
RUN cd ~ && \
    mkdir -p dlib && \
    git clone https://github.com/davisking/dlib.git dlib/ && \
    cd  dlib/ && \
    python setup.py install

# Install and initialize all python packages for Pipert
COPY requirements1.txt requirements2.txt /
RUN pip3 install --upgrade pip
RUN pip3 install torch
RUN pip3 install -r requirements1.txt
RUN pip3 install -r requirements2.txt

# Install Splunk HEC handler for python
RUN pip install 'git+git://github.com/georgestarcher/Splunk-Class-httpevent.git'

# Install detectron2
RUN pip install 'git+https://github.com/facebookresearch/detectron2.git'