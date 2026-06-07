#!/bin/sh
set -e

exec celery -A config.celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-info}" \
  --pool="${CELERY_POOL:-solo}"