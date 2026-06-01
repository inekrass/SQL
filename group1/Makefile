COMPOSE := docker compose

.PHONY: up down status test config logs create-tables generate-data check-cluster

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

config:
	$(COMPOSE) config

logs:
	$(COMPOSE) logs -f --tail=100
