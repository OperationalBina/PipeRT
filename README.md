# PipeRT
[![Documentation Status](https://readthedocs.org/projects/pipert/badge/?version=latest)](https://pipert.readthedocs.io/en/latest/?badge=latest)
[![Build Status](https://travis-ci.com/ItamarWilf/PipeRT.svg?branch=master)](https://travis-ci.com/ItamarWilf/PipeRT)
[![codecov](https://codecov.io/gh/ItamarWilf/PipeRT/branch/master/graph/badge.svg)](https://codecov.io/gh/ItamarWilf/PipeRT)

Real-time pipeline for video analytics.

Structure
=========
- **pipert**: The library, which contains:
    - **core**: The core parts of the library, the pipeline base 'component' and component's base 'routine'.
    - **utils**: general purpose functions for monitoring, controlling, and massage passing between components and routines.

- **pipert.contrib**: The Contrib directory contains implemented components and routines for various projects.  

The code in **pipert.contrib** is not as fully maintained as the core part of the library. It may change or be removed at any time without notice.

Documentation
=============
API documentation and an overview of the library can be found [here](https://pipert.readthedocs.io/en/latest/).

Submodule Usage
===============
- **In order to use the submodules in this project do the following:**:
    - **When cloning**: `git clone --recurse-submodules https://github.com/ItamarWilf/PipeRT.git`
    
      **OR**
    
    - **After `git pull`**: `git submodule update --init --recursive`


Installation
============
- Running the pipeline for the first time:
    - docker-compose up -d

- Build the pipeline after changes:
    - docker-compose up -d --build --force-recreate
