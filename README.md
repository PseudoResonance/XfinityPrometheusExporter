# XFINITY Modem Prometheus Exporter

A Prometheus exporter for XFINITY modems.

## Installation

A Dockerfile is provided to build a Docker container to run the exporter. Additionally, a Kubernetes Helm chart is included for easy deployment alongside [prometheus-operator](https://github.com/prometheus-operator/prometheus-operator/), however it can also be run as a standalone application.

### Docker Quickstart Guide

1. Clone the repository to a directory of your choice.
2. Create an environment variable file, `.env` in the directory with the application, and configure it with your modem login credentials. (ex: `MODEM_PASSWORD=password123`)
3. Build the image with `docker compose build` and run it with `docker compose up -d`.

### Prerequisites

 - Python 3.10
 - LXML
 - Requests
 - AIOHTTP

## Configuration

The exporter can be configured with command line arguments, environment variables, or through the Python file itself.

Environment variables will override options configured in the Python file, while command line arguments override all other config options.

### Environment Variables

| Variable | Description |
| --- | --- |
| `MODEM_USERNAME` | Sets the XFINITY login username |
| `MODEM_PASSWORD` | Sets the XFINITY login password |
| `MODEM_ENDPOINT` | Sets the XFINITY login page endpoint (ex: `http://192.168.100.1`) |
| `SERVER_HOST` | Sets the address to bind the webserver to, or `None` to bind to all addresses |
| `SERVER_PORT` | Sets the port to bind the webserver to |

### Command Line Arguments

| Short | Long | Description |
| --- | --- | --- |
| `-d` | `--debug` | Enables debug console output |
| `-u` | `--user` | Sets the XFINITY login username |
| `-p` | `--pass` | Sets the XFINITY login password |
| | `--endpoint` | Sets the XFINITY login page endpoint (ex: `http://192.168.100.1`) |
| | `--host` | Sets the address to bind the webserver to, or `None` to bind to all addresses |
| | `--port` | Sets the port to bind the webserver to |
