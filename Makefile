.PHONY: help build up down restart logs clean test install-deps migrate

GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m 

help:
	@echo "$(GREEN)Доступные команды:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-deps:
	poetry install

build:
	docker-compose build

up:
	docker-compose up -d --build

down:
	docker-compose down

restart:
	docker-compose restart

restart-bot:
	@echo "$(YELLOW)Перезапуск бота...$(NC)"
	docker-compose restart bot

restart-overlay:
	@echo "$(YELLOW)Перезапуск overlay...$(NC)"
	docker-compose restart overlay

logs:
	docker-compose logs -f

logs-bot:
	docker-compose logs -f bot

logs-overlay:
	docker-compose logs -f overlay

logs-payment:
	docker-compose logs -f payment_service

logs-db:
	docker-compose logs -f postgres

status:
	docker-compose ps

db-connect:
	docker exec -it donation_postgres psql -U postgres -d donation_bot

db-stats:
	poetry run python scripts/clear_database.py

db-clear:
	poetry run python scripts/clear_database.py

db-clear-all:
	docker-compose stop bot overlay payment_service
	docker exec donation_postgres psql -U postgres -d donation_bot -c "TRUNCATE users, streamers, donations RESTART IDENTITY CASCADE;"
	@echo "$(GREEN)База данных очищена!$(NC)"
	@echo "$(YELLOW)Перезапуск сервисов...$(NC)"
	docker-compose start bot overlay payment_service

db-reset:
	docker-compose down
	docker volume rm coursework_postgres_data || true
	docker-compose up postgres -d
	@echo "$(YELLOW)Ожидание запуска базы данных...$(NC)"
	sleep 10
	docker-compose up bot overlay payment_service -d

migrate:
	sleep 5
	docker exec donation_postgres psql -U postgres -d donation_bot -c "SELECT 1;" > /dev/null 2>&1 || (echo "$(RED)❌ PostgreSQL не доступен$(NC)" && exit 1)
	poetry run alembic upgrade head

migrate-create:
	@echo "$(GREEN)Создание новой миграции...$(NC)"
	@read -p "Введите описание миграции: " desc; \
	poetry run alembic revision --autogenerate -m "$$desc"

migrate-status:
	poetry run alembic current
	poetry run alembic history

clean:
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

install:
	sleep 15
	$(MAKE) migrate

dev-shell:
	poetry shell

dev-run-bot:
	poetry run python run_bot.py

dev-run-overlay:
	poetry run uvicorn overlay.main:app --reload --port 8000

dev-run-payment:
	poetry run python payment_service/main.py

format:
	poetry run black . --line-length 100

lint:
	poetry run mypy bot/ overlay/ payment_service/ database/

dev-logs:
	docker-compose logs -f bot overlay payment_service

rebuild:
	docker-compose down
	docker-compose up --build -d

send-donation:
	poetry run python scripts/send_test_donation.py

send-big:
	poetry run python scripts/send_test_donation.py --template big

send-small:
	poetry run python scripts/send_test_donation.py --template small

send-bulk:
	poetry run python scripts/send_test_donation.py --bulk $(or $(BULK),5)

send-custom:
	poetry run python scripts/send_test_donation.py --custom \
		--donor "$(or $(DONOR),КастомТестер)" \
		--amount $(or $(AMOUNT),1.0) \
		--currency $(or $(CURRENCY),ETH) \
		--message "$(or $(MESSAGE),Кастомный тестовый донат)"

donation-templates:
	@echo "$(GREEN)📚 Доступные шаблоны донатов...$(NC)"
	poetry run python scripts/send_test_donation.py --templates

send-to-streamer:
	poetry run python scripts/send_test_donation.py --template random --id $(or $(STREAMER_ID),1)

overlay-url:
	@echo "  http://localhost:8000/overlay/html/$(or $(STREAMER_ID),1)"
	@echo "  http://localhost:8000/overlay/donations/$(or $(STREAMER_ID),1)"

init-assets:
	poetry run python scripts/init_assets.py

show-networks:
	poetry run python scripts/init_assets.py

test-currency:
	poetry run python scripts/test_currency_service.py

test-currency-rates:
	@echo "2" | poetry run python scripts/test_currency_service.py

test-currency-fiat:
	@echo "3" | poetry run python scripts/test_currency_service.py

test-currency-health:
	@echo "5" | poetry run python scripts/test_currency_service.py

show-supported-currencies:
	@echo "7" | poetry run python scripts/test_currency_service.py

demo-currency:
	@echo "6" | poetry run python scripts/test_currency_service.py

migrate-assets:
	poetry run alembic revision --autogenerate -m "Add assets table and update donations"

.PHONY: init-networks init-oracle-types init-oracles init-all-oracles
init-networks:
	python scripts/init_networks_and_oracles.py --networks-only

init-oracle-types:
	python scripts/init_oracle_types.py

init-oracles:
	python scripts/init_oracles.py

init-all-oracles:
	python scripts/init_networks_and_oracles.py

.PHONY: test-oracle-system init-oracle-system
init-oracle-system:
	python scripts/init_networks_and_oracles.py