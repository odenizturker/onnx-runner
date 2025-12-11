#!/usr/bin/env bash
# Run all ONNX models in ./models/ directory once
# Full flow: build → push model → measure
# Usage: ./scripts/run_all_models.sh

set -euo pipefail


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEASUREMENT_SCRIPT="$SCRIPT_DIR/measure_model.sh"
PUSH_BINARY_SCRIPT="$SCRIPT_DIR/push_binary_to_device.sh"
MODEL_DIR="./models"
DEVICE_MODELS_DIR="/data/local/tmp/models"

# Check if measurement script exists
if [ ! -f "$MEASUREMENT_SCRIPT" ]; then
    echo "ERROR: $MEASUREMENT_SCRIPT not found"
    exit 1
fi

# Check if push binary script exists
if [ ! -f "$PUSH_BINARY_SCRIPT" ]; then
    echo "ERROR: $PUSH_BINARY_SCRIPT not found"
    exit 1
fi

# Check if models directory exists
if [ ! -d "$MODEL_DIR" ]; then
    echo "ERROR: $MODEL_DIR directory not found"
    exit 1
fi

# Find all ONNX models recursively in subdirectories
models=()
while IFS= read -r -d '' model_path; do
    models+=("$model_path")
done < <(find "$MODEL_DIR" -name "*.onnx" -type f -print0 | sort -z)

if [ ${#models[@]} -eq 0 ]; then
    echo "No .onnx models found in $MODEL_DIR (including subdirectories)"
    exit 0
fi

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "============================================================"
log "ONNX Model Power Measurement - Full Benchmark"
log "============================================================"
log "Models to measure: ${#models[@]}"
log ""

# Step 1: Build the binary
log "Step 1/3: Building onnx_runner binary..."
log "------------------------------------------------------------"
if make -C "$SCRIPT_DIR/.." > /dev/null 2>&1; then
    log "  ✓ Build successful"
else
    log "  ✗ Build failed"
    exit 1
fi
log ""

# Step 2: Push binary and libraries to device
log "Step 2/3: Deploying binary and libraries to device..."
log "------------------------------------------------------------"
if "$PUSH_BINARY_SCRIPT"; then
    log "  ✓ Binary deployed successfully"
else
    log "  ✗ Binary deployment failed"
    exit 1
fi
log ""

# Step 3: Run measurements for all models
log "Step 3/3: Running measurements..."
log "============================================================"
log ""

total_runs=0
failed_runs=0
model_count=0
total_models=${#models[@]}

# Iterate through each model
for modelpath in "${models[@]}"; do
    # Get path relative to models/ directory (e.g., "subfolder/model.onnx" or "model.onnx")
    model_relative="${modelpath#$MODEL_DIR/}"
    model_count=$((model_count + 1))

    log "Model $model_count/$total_models: $model_relative"
    log "------------------------------------------------------------"

    # Push this specific model to device
    log "  Pushing model to device..."

    # Create directory on device if needed
    model_dir=$(dirname "${model_relative}")
    if [ "${model_dir}" != "." ]; then
        adb shell "mkdir -p ${DEVICE_MODELS_DIR}/${model_dir}" 2>/dev/null || true
        adb push "${modelpath}" "${DEVICE_MODELS_DIR}/${model_dir}/" > /dev/null 2>&1
    else
        adb push "${modelpath}" "${DEVICE_MODELS_DIR}/" > /dev/null 2>&1
    fi

    log "  ✓ Model pushed to device"

    # Run measurement for this model
    log "  Running measurement..."
    total_runs=$((total_runs + 1))

    if "$MEASUREMENT_SCRIPT" "$model_relative"; then
        log "  ✓ Measurement completed successfully"
    else
        log "  ✗ Measurement failed"
        failed_runs=$((failed_runs + 1))
    fi


    log ""
done

log "============================================================"
log "All measurements complete!"
log "============================================================"
log "Total runs: $total_runs"
log "Successful: $((total_runs - failed_runs))"
log "Failed: $failed_runs"
log "Results saved in ./measurements/"
log ""
log "Next steps:"
log "  Parse results: python3 ./scripts/parse_measurements.py"
log "============================================================"

