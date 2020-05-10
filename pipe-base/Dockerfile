FROM python:3.8-slim-buster

# Install necessary apt packages
RUN apt-get update -y && \
    apt-get install -yq \
    libgtk2.0-dev \
    git

# Install and initialize all python packages for Pipert
COPY requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

# Install pycocotools
RUN pip3 install --upgrade cython
RUN pip3 install pycocotools

# Install Splunk HEC handler for python
RUN pip install 'git+git://github.com/georgestarcher/Splunk-Class-httpevent.git'

# Install detectron2
RUN pip install 'git+https://github.com/facebookresearch/detectron2.git'