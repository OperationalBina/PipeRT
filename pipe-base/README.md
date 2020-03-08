# PipeRT - base image

Base image containing all packages and repositories for the pipeline.

Structure
=========
- **Dockerfile**: The dockerfile, which contains:
    - Opencv 4.0
    - Dlib
    - Python 3.6
    - Detectron 2
    - Python packages
- **requirements1.txt**: Python packages for the pipeline.
- **requirements2.txt**: Python packages (based on the packages in requirements1.txt) for the pipeline.   