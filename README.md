# Система донатов для стримеров

Система для приёма донатов через Telegram бота с отображением оверлеев для стримов.

## Настройка и запуск


```bash
make up

make migrate
```

### Запуск через Docker Compose

```bash
docker-compose up --build

docker-compose up -d --build

docker-compose down
```

### Миграции Alembic:

```bash
make migrate

make migrate-create

make migrate-status
```

### Форматирование и линтинг

```bash
make format

make lint
```