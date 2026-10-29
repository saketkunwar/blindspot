# BlindSpot rebuild fabric (P1). One target chains the whole pipeline:
# install -> manifest -> gates -> seed -> api -> web -> judge.
# Needs: Python 3.11+ with project deps, Node 18+ for `web`, ports
# 8000/3000 free for the demo check. `make rebuild` is the G16 gate.

.PHONY: install manifest gates seed api web judge rebuild

install:
	pip install -e .

manifest:
	python scripts/check_manifest.py --data-dir data

gates:
	python scripts/validate_hardened.py

seed:
	python scripts/seed_store.py

api:
	python -m api.export_openapi --check

web:
	cd web && npm run build

judge:
	bash scripts/judge.sh

rebuild: install manifest gates seed api web judge
