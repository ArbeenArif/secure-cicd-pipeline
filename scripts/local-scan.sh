#!/usr/bin/env bash
# Run the same security gates as the CI pipeline on your own machine.
# Usage: ./scripts/local-scan.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements-dev.txt

echo "== [1/4] Bandit (SAST) =="
bandit -r app --severity-level medium --confidence-level medium

echo "== [2/4] pip-audit (dependency CVEs) =="
pip-audit -r app/requirements.txt --strict

echo "== [3/4] pytest + coverage =="
pytest --cov=app --cov-report=term-missing --cov-fail-under=85

echo "== [4/4] Docker build + Trivy (optional, needs docker & trivy) =="
if command -v docker >/dev/null && command -v trivy >/dev/null; then
  docker build -t secure-cicd-demo:local .
  trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 secure-cicd-demo:local
else
  echo "docker/trivy not installed - skipping image scan"
fi

echo "All local gates passed."
