COMPOSE := docker compose

.PHONY: up down status test config logs create-tables generate-data check-cluster check-nginx nginx-logs check-monitoring fault-status

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

test:
	$(COMPOSE) config --quiet
	$(COMPOSE) ps

create-tables:
	sh scripts/create_tables.sh

generate-data:
	sh scripts/generate_data.sh

check-cluster:
	sh scripts/check_cluster.sh

check-nginx:
	sh scripts/check_nginx.sh

nginx-logs:
	$(COMPOSE) logs --tail=100 nginx

check-monitoring:
	sh scripts/check_monitoring.sh

fault-status:
	sh scripts/fault_injection.sh status

config:
	$(COMPOSE) config

logs:
	$(COMPOSE) logs -f --tail=100
