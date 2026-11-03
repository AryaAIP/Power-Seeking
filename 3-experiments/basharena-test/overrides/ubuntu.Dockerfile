FROM ubuntu:22.04
# Infra-only: trust the cloud workspace's HTTPS proxy CA so image builds can reach PyPI.
COPY ccr-proxy-ca.crt /usr/local/share/ca-certificates/ccr-proxy-ca.crt
RUN mkdir -p /etc/ssl/certs && cat /usr/local/share/ca-certificates/ccr-proxy-ca.crt >> /etc/ssl/certs/ca-certificates.crt
