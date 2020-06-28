FROM ubuntu:16.04

FROM python:3.8-slim-buster

# Install necessary apt packages
RUN apt-get update -y && \
    apt-get install -yq \
    libgtk2.0-dev \
    git

# Install and initialize all python packages for Pipert
COPY requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt --no-cache-dir --default-timeout=100

# Install pycocotools
RUN pip3 install --upgrade cython
RUN pip3 install pycocotools
