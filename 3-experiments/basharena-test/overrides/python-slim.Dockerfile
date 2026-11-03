FROM python:3.12-slim
# Infra-only: proxy CA, plus curl and the servers' requirements pre-installed so startup needs no HTTPS.
COPY ccr-proxy-ca.crt /usr/local/share/ca-certificates/ccr-proxy-ca.crt
RUN cat /usr/local/share/ca-certificates/ccr-proxy-ca.crt >> /etc/ssl/certs/ca-certificates.crt \
 && apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt Flask==3.0.0 requests==2.31.0
