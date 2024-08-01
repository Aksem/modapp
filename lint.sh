#!/bin/bash

SRC_DIR=modapp

poetry run black $SRC_DIR
poetry run isort $SRC_DIR
poetry run mypy --strict $SRC_DIR
poetry run flake8 $SRC_DIR
# poetry run bandit -r $SRC_DIR
# poetry run safety check

exit 0
