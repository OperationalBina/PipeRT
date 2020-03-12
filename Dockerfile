FROM pipert_base-pipert

# Copy all necessary files for PipeRT
COPY . .

EXPOSE 5000
ENTRYPOINT ["/demo_run"]
