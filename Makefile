.PHONY: run dev test compile seed lint typecheck clean-data

run:
	python main.py

dev:
	python main.py

test:
	pytest -q

compile:
	python -m compileall apps packages tests main.py

seed:
	python scripts/seed.py

lint:
	ruff check .

typecheck:
	mypy packages apps main.py

clean-data:
	rm -rf local_data
