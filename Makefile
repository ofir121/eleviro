.PHONY: run test

run:
	uvicorn main:app --reload

test:
	pytest
