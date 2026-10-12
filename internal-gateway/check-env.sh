#!/bin/sh
set -eu

# Compose supplies topology defaults; the image itself assumes no destinations.
: "${USER_SERVICE_UPSTREAM:?USER_SERVICE_UPSTREAM must be set}"
: "${SUPPLIER_SERVICE_UPSTREAM:?SUPPLIER_SERVICE_UPSTREAM must be set}"
: "${NGINX_DNS_RESOLVER:?NGINX_DNS_RESOLVER must be set}"
