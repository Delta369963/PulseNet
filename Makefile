# PulseNet v2 — Makefile
# Two services: Next.js (port 3000) + FastAPI engine (port 8000).
# Run `make help` for usage.

SHELL := /bin/bash
ENGINE_DIR := mini-services/pulsenet-engine

.PHONY: help install dev engine test test-engine lint seed reset

help:
	@echo "PulseNet v2"
	@echo ""
	@echo "  make install      Install all dependencies (JS + Python)"
	@echo "  make seed         Re-seed the database with demo data"
	@echo "  make dev          Start the Next.js dev server (port 3000)"
	@echo "  make engine       Start the FastAPI engine (port 8000)"
	@echo "  make test         Run the Python engine tests"
	@echo "  make lint         Lint the Next.js project"
	@echo "  make reset        Wipe + re-seed the database"

install:
	@echo "→ Installing JS dependencies..."
	npm install --legacy-peer-deps
	@echo "→ Pushing Prisma schema..."
	npx prisma db push
	@echo "→ Installing Python engine dependencies..."
	cd $(ENGINE_DIR) && uv venv .venv --python 3.11 2>/dev/null || true
	cd $(ENGINE_DIR) && uv pip install -e ".[dev]" --python .venv
	@echo "✓ All dependencies installed."
	@echo ""
	@echo "  Next: copy .env.example → .env and fill in your Gemini keys."

seed:
	npx tsx prisma/seed.ts

seed-demo:
	@echo "→ Loading demo replay scenarios via API (dev server must be running)..."
	curl -s -X POST http://localhost:3000/api/demo \
	  -H "Content-Type: application/json" \
	  -d '{"action":"seed"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ Demo seeded:', d)"

reset: seed
	@echo "✓ Database initialized — trade graph ready, no demo shocks."


dev:
	npm run dev

engine:
	cd $(ENGINE_DIR) && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	cd $(ENGINE_DIR) && .venv/bin/python -m pytest -q --tb=short

lint:
	npm run lint
