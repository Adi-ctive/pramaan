PY ?= .venv/bin/python
.PHONY: secrets up down seed demo test e2e eval probe cron lite full

secrets up down seed demo test e2e eval probe cron:
	$(PY) tasks.py $@

lite:
	MODE=LITE $(PY) tasks.py demo

full:
	MODE=FULL $(PY) tasks.py demo
