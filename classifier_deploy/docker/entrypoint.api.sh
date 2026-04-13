#!/bin/sh
set -eu

if [ "${METRICS_ENABLED:-true}" = "true" ] && [ "${METRICS_MULTIPROCESS_ENABLED:-false}" = "true" ]; then
  if [ -z "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    echo "PROMETHEUS_MULTIPROC_DIR must be set when multiprocess metrics are enabled." >&2
    exit 1
  fi

  mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
  rm -f "${PROMETHEUS_MULTIPROC_DIR}"/*
fi

exec "$@"
