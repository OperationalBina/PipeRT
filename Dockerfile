FROM pipert_base-pipert

# Copy all necessary files for PipeRT
COPY . .

ENV PYTHONPATH='/'
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "pipert/core/main.py"]
