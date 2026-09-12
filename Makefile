.PHONY: test eval run
test:
	pytest -q
eval:
	python -m evals.evaluate
run:
	uvicorn backend.app.main:app --reload

