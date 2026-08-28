.PHONY: dev server dashboard install test simulate tac-setup tac-agent

# ── TAC Agent (Full Voice Demo) ──────────────────────────────────────────────

tac-setup:
	cd tac-sdk && make setup

tac-agent:
	cd tac-sdk && uv run python camping_world_agent.py

# ── Local Dev (Custom Server + React Dashboard) ──────────────────────────────

install:
	cd server && pip install -e ".[dev]"
	cd dashboard && COREPACK_ENABLE_STRICT=0 pnpm install

dev:
	@echo "Starting server (port 8000) and dashboard (port 5173)..."
	@trap 'kill 0' INT; \
	(cd server && .venv/bin/python -m twilio_observe.main) & \
	(cd dashboard && COREPACK_ENABLE_STRICT=0 pnpm dev) & \
	wait

server:
	cd server && .venv/bin/python -m twilio_observe.main

dashboard:
	cd dashboard && COREPACK_ENABLE_STRICT=0 pnpm dev

test:
	cd server && .venv/bin/pytest -v
	cd dashboard && pnpm test

simulate:
	cd server && uv run python ../scripts/simulate-call.py
