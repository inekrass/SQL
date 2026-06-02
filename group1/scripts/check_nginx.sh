#!/usr/bin/env sh
set -eu

QUERY="${1:-SELECT hostName() AS node}"

curl -sS --data-binary "$QUERY" "http://localhost:8123/"
