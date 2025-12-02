#!/usr/bin/env bash
# Run all ONNX models in ./models/ directory multiple times
# Usage: ./scripts/run_all_models.sh <runs>
# Example: ./scripts/run_all_models.sh 2    # run each model twice

set -u

RUNS="${1:-1}"

# Validate RUNS is a positive integer
if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Usage: $0 <positive-integer>"
    echo "Example: $0 2    # run each model 2 times"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEASUREMENT_SCRIPT="$SCRIPT_DIR/run_full_measurement_for_model.sh"
MODEL_DIR="./models"

# Check if measurement script exists
if [ ! -f "$MEASUREMENT_SCRIPT" ]; then
    echo "ERROR: $MEASUREMENT_SCRIPT not found"
    exit 1
fi

# Check if models directory exists
if [ ! -d "$MODEL_DIR" ]; then
    echo "ERROR: $MODEL_DIR directory not found"
    exit 1
fi

# Find all ONNX models
shopt -s nullglob
models=("$MODEL_DIR"/*.onnx)

if [ ${#models[@]} -eq 0 ]; then
    echo "No .onnx models found in $MODEL_DIR"
    exit 0
fi

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "Starting benchmark for ${#models[@]} model(s), $RUNS run(s) each"
log "============================================================"

total_runs=0
failed_runs=0

# Iterate through each model
for modelpath in "${models[@]}"; do
    modelfile=$(basename "$modelpath")
    log ""
    log "Model: $modelfile (running $RUNS time(s))"
    log "------------------------------------------------------------"

    for i in $(seq 1 "$RUNS"); do
        log "  Run #$i/$RUNS..."
        total_runs=$((total_runs + 1))

        if "$MEASUREMENT_SCRIPT" "$modelfile"; then
            log "  ✓ Run #$i completed successfully"
        else
            log "  ✗ Run #$i failed"
            failed_runs=$((failed_runs + 1))
        fi

        # Short pause between runs to allow device to stabilize
        if [ "$i" -lt "$RUNS" ]; then
            sleep 2
        fi
    done
done

log ""
log "============================================================"
log "All measurements complete!"
log "Total runs: $total_runs"
log "Successful: $((total_runs - failed_runs))"
log "Failed: $failed_runs"
log "Results saved in ./measurements/"
log "============================================================"

