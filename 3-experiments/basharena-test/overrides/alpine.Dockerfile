FROM alpine:3.20
# Infra-only: http repos (containers have direct plain-HTTP egress) and router packages pre-installed.
RUN sed -i 's#https://#http://#' /etc/apk/repositories && apk add --no-cache iptables iproute2 bind-tools curl
