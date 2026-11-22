# AboGator · Backend API

Backend gamificado para la enseñanza de Derecho Informático a desarrolladores.

## Stack Tecnológico
- **Python 3.12+** / **FastAPI**
- **PostgreSQL 16** con SQLAlchemy 2.0 y Alembic
- **Redis 7** (Rate limiting, bloqueos distribuidos y candados)
- **APScheduler** (Worker en segundo plano)
- **Docker & Docker Compose**

## Puesta en Marcha Local

### 1. Clonar y configurar entorno
```bash
cp .env.example .env
# Modificar valores en .env si es necesario
```

### 2. Levantar servicios con Docker
```bash
docker compose up -d
```

### 3. Migraciones y datos iniciales
```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/create_superadmin.py
docker compose exec api python scripts/seed_demo_cards.py
```

### 4. Pruebas automatizadas
```bash
docker compose exec api pytest
```

Documentación interactiva disponible en: `http://localhost:8000/docs`.