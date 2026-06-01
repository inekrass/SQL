COMPOSE := docker compose

.PHONY: up down status test config logs

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

test:
	$(COMPOSE) config --quiet
	$(COMPOSE) ps

config:
	$(COMPOSE) config

logs:
	$(COMPOSE) logs -f --tail=100
