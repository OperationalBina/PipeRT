# Changelog

All notable changes to the Pipeline project will be documented in this file.

## [1.0.0] - 2020-05-07

### Added

- Monitoring the pipeline:
	- Monitor with splunk
	- Monitor with prometheus and grafana

- Pipeline manager that responsible for running the pipe:
    - cli - control the pipe manager through tcp
    - UI - React server that displays the pipe and control it

- Add support for running the pipeline with yaml file

- Add support for passing messages payload between components through shared memory

- Add more documentation about the pipeline

- Add some contrib components:
    - save predictions to DB
    - Flask display
    - Listen to stream

### Deleted

- Running the pipeline with bash script

