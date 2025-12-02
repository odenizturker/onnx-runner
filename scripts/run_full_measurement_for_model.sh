#!/usr/bin/env bash
# Run full measurement for a single model with precise battery stats timing:
# - 6s warmup (no battery measurement)
# - 6s silent (no battery measurement)
# - Battery stats reset
# - 48s measurement (with battery measurement)
# - Export battery stats

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <onnx_filename>"
  exit 1
fi

ONNX_NAME="$1"
DEVICE_BIN="/data/local/tmp/onnx_runner"
OUTPUT_DIR="./measurements"

# Duration configuration
WARMUP_DURATION=6      # 6 seconds warmup
SILENT_DURATION=6      # 6 seconds silent period
MEASUREMENT_DURATION=48 # 48 seconds measurement

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# Check if model exists locally
if [ ! -f "./models/${ONNX_NAME}" ]; then
    log "ERROR: Model file not found: ./models/${ONNX_NAME}"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

log "Starting measurement for: ${ONNX_NAME}"
log "============================================================"

# Phase 1: Warmup - no measurement
log "Phase 1: Warmup (${WARMUP_DURATION}s)..."
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=. ${DEVICE_BIN} ${ONNX_NAME} ${WARMUP_DURATION}" > /dev/null 2>&1 || {
    log "  ✗ Warmup failed"
    exit 1
}
log "  ✓ Warmup completed"

# Phase 2: Silent - system stabilization, no measurement
log "Phase 2: Silent phase (${SILENT_DURATION}s)..."
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=. ${DEVICE_BIN} ${ONNX_NAME} ${SILENT_DURATION}" > /dev/null 2>&1 || {
    log "  ✗ Silent phase failed"
    exit 1
}
log "  ✓ Silent phase completed"

# Phase 3: Reset battery statistics (only before measurement)
log "Phase 3: Resetting battery statistics..."
adb shell dumpsys batterystats --reset > /dev/null 2>&1
sleep 1
log "  ✓ Battery statistics reset"

# Phase 4: Measurement - actual power measurement
log "Phase 4: Running measurement (${MEASUREMENT_DURATION}s)..."
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=. ${DEVICE_BIN} ${ONNX_NAME} ${MEASUREMENT_DURATION}" || {
    log "  ✗ Measurement failed"
    exit 1
}
log "  ✓ Measurement completed"

# Phase 5: Collect battery statistics
log "Phase 5: Collecting battery statistics..."
STATS_FILE="${OUTPUT_DIR}/${ONNX_NAME}_batterystats.txt"
adb shell dumpsys batterystats > "$STATS_FILE"
log "  ✓ Battery statistics saved to: $STATS_FILE"

log "============================================================"
log "Measurement complete for: ${ONNX_NAME}"

