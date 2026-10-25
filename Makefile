.PHONY: test up down dev-ml dev-api
test:
	cd services/ml && python -m pytest -q
	cd services/api && python -m pytest -q
up:
	docker compose up --build -d
down:
	docker compose down
dev-ml:
	cd services/ml && uvicorn app.main:app --port 8001 --reload
dev-api:
	cd services/api && ML_URL=http://localhost:8001 uvicorn app.main:app --port 8000 --reload
