FROM pipert_base-pipert

# Install splunk if needed
ARG SPLUNK
ENV SPLUNK=${SPLUNK}
RUN if [ "$SPLUNK" = "yes" ]; then pip install 'git+git://github.com/georgestarcher/Splunk-Class-httpevent.git'; fi

# Install detectron2 if needed
ARG DETECTRON
ENV DETECTRON=${DETECTRON}
RUN if [ "$DETECTRON" = "yes" ]; then pip install 'git+https://github.com/facebookresearch/detectron2.git'; fi

# Install torchvision if needed
ARG TORCHVISION
ENV TORCHVISION=${TORCHVISION}
RUN if [ "$TORCHVISION" = "yes" ]; then pip install torchvision; fi

ENV PYTHONPATH='/'
ENV PYTHONUNBUFFERED=1

# Copy all necessary files for PipeRT
COPY . .

# Create folder for log files
ENV LOGS_FOLDER_PATH pipert/utils/log_files
RUN mkdir $LOGS_FOLDER_PATH

RUN python --version
RUN python3 --version 

ENTRYPOINT ["python3", "pipert/utils/scripts/main.py"]

RUN ls
