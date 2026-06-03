#!/usr/bin/env sh
set -eu

COMPOSE="docker compose"

usage() {
    cat <<'EOF'
Usage:
  sh scripts/fault_injection.sh replica-down
  sh scripts/fault_injection.sh replica-up
  sh scripts/fault_injection.sh shard-down
  sh scripts/fault_injection.sh shard-up
  sh scripts/fault_injection.sh keeper-one-down
  sh scripts/fault_injection.sh keeper-one-up
  sh scripts/fault_injection.sh keeper-quorum-down
  sh scripts/fault_injection.sh keeper-quorum-up
  sh scripts/fault_injection.sh status

The commands intentionally stop/start Docker Compose services.
EOF
}

case "${1:-}" in
    replica-down)
        $COMPOSE stop ch-s1-r2
        ;;
    replica-up)
        $COMPOSE start ch-s1-r2
        ;;
    shard-down)
        $COMPOSE stop ch-s2-r1 ch-s2-r2
        ;;
    shard-up)
        $COMPOSE start ch-s2-r1 ch-s2-r2
        ;;
    keeper-one-down)
        $COMPOSE stop keeper-1
        ;;
    keeper-one-up)
        $COMPOSE start keeper-1
        ;;
    keeper-quorum-down)
        $COMPOSE stop keeper-1 keeper-2
        ;;
    keeper-quorum-up)
        $COMPOSE start keeper-1 keeper-2
        ;;
    status)
        $COMPOSE ps
        ;;
    *)
        usage
        exit 1
        ;;
esac
