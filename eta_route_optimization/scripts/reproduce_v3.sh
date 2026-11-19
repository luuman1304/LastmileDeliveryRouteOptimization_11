#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-.venv-eta/bin/python}
PROJECT=eta_route_optimization
ARTIFACTS=$PROJECT/artifacts/generated
DATASET=$ARTIFACTS/eta_dataset_v3
BASELINES=$ARTIFACTS/eta_baselines_v3
AMAZON=data/raw/amazon/almrrc2021-data-training/model_build_inputs

export PYTHONPATH=$PROJECT/src
export LOKY_MAX_CPU_COUNT=${LOKY_MAX_CPU_COUNT:-8}

"$PYTHON_BIN" -m eta_route_optimization.audit \
  --lade-glob 'data/raw/lade_d/*.parquet' \
  --amazon-root "$AMAZON" \
  --output "$ARTIFACTS/data_audit_v3.json"
"$PYTHON_BIN" -m eta_route_optimization.eta_dataset \
  --lade-glob 'data/raw/lade_d/*.parquet' --output "$DATASET"
"$PYTHON_BIN" -m eta_route_optimization.validate_protocol \
  --dataset "$DATASET" --output "$DATASET/validation.json"
"$PYTHON_BIN" -m eta_route_optimization.eta_experiment \
  --dataset "$DATASET" --output "$BASELINES"
"$PYTHON_BIN" -m eta_route_optimization.statistical_analysis \
  --predictions "$BASELINES/test_predictions.parquet" \
  --output "$ARTIFACTS/statistics_v3"
"$PYTHON_BIN" -m eta_route_optimization.integration_experiment \
  --predictions "$BASELINES/test_predictions.parquet" \
  --output "$ARTIFACTS/eta_integration_v3"
"$PYTHON_BIN" -m eta_route_optimization.slice_analysis \
  --dataset "$DATASET" --predictions "$BASELINES/test_predictions.parquet" \
  --output "$ARTIFACTS/slice_analysis_v3"
"$PYTHON_BIN" -m eta_route_optimization.graph_ablation \
  --dataset "$DATASET" \
  --base-validation-predictions "$BASELINES/validation_predictions.parquet" \
  --base-test-predictions "$BASELINES/test_predictions.parquet" \
  --output "$ARTIFACTS/graph_ablation_v3"
"$PYTHON_BIN" -m eta_route_optimization.robustness_diagnostic \
  --dataset "$DATASET" --output "$ARTIFACTS/robustness_v3"
"$PYTHON_BIN" -m eta_route_optimization.balanced_experiment \
  --dataset "$DATASET" \
  --base-validation-predictions "$BASELINES/validation_predictions.parquet" \
  --base-test-predictions "$BASELINES/test_predictions.parquet" \
  --output "$ARTIFACTS/balanced_v3"
"$PYTHON_BIN" -m eta_route_optimization.rolling_origin \
  --dataset "$DATASET" --output "$ARTIFACTS/rolling_origin_v3"
"$PYTHON_BIN" -m eta_route_optimization.soft_window_experiment \
  --source "$AMAZON" --output "$ARTIFACTS/amazon_soft_windows_v3" \
  --per-station 12 --solver-seconds 1 --repeats 3
"$PYTHON_BIN" -m eta_route_optimization.deployment_benchmark \
  --dataset "$DATASET" --output "$ARTIFACTS/deployment_v3"
"$PYTHON_BIN" -m pytest -q "$PROJECT/tests"
"$PYTHON_BIN" -m compileall -q "$PROJECT/src" "$PROJECT/scripts"
"$PYTHON_BIN" -m ruff check "$PROJECT"
"$PYTHON_BIN" "$PROJECT/scripts/generate_research_paper.py"
"$PYTHON_BIN" -m eta_route_optimization.provenance \
  --project "$PROJECT" --output "$ARTIFACTS/MANIFEST.json"
