#!/usr/bin/env bash
# Run full measurement for a single model with precise battery stats timing:
# The binary handles all three phases internally:
# - warmup (cache warm-up)
# - silence (system stabilization)
# - batterystats reset
# - measurement (with battery measurement)

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <onnx_path_relative_to_models>"
  echo "Example: $0 model.onnx"
  echo "Example: $0 zi_t/model.onnx"
  exit 1
fi

ONNX_RELATIVE_PATH="$1"
DEVICE_BIN="/data/local/tmp/onnx_runner"
DEVICE_MODEL_PATH="/data/local/tmp/models/${ONNX_RELATIVE_PATH}"
OUTPUT_DIR="./measurements"

# Duration configuration
WARMUP_DURATION=6      # 6 seconds warmup
SILENT_DURATION=6      # 6 seconds silent period
MEASUREMENT_DURATION=48 # 48 seconds measurement

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# Check if model exists locally
if [ ! -f "./models/${ONNX_RELATIVE_PATH}" ]; then
    log "ERROR: Model file not found: ./models/${ONNX_RELATIVE_PATH}"
    exit 1
fi

# Create safe filename for output (replace / with _)
SAFE_FILENAME="${ONNX_RELATIVE_PATH//\//_}"


mkdir -p "$OUTPUT_DIR"

log "Starting 3-phase measurement for: ${ONNX_RELATIVE_PATH}"
log "============================================================"

# Verify model exists on device
if ! adb shell "test -f ${DEVICE_MODEL_PATH}" 2>/dev/null; then
    log "  ✗ Model not found on device: ${DEVICE_MODEL_PATH}"
    log "    Make sure model is pushed to device first"
    exit 1
fi

# Run all three phases in a single program execution
# This keeps caches warm across phases
log "Running benchmark (warmup → silence → reset → measurement)..."
BENCHMARK_OUTPUT=$(adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=. ${DEVICE_BIN} ${ONNX_RELATIVE_PATH} ${WARMUP_DURATION} ${SILENT_DURATION} ${MEASUREMENT_DURATION}" 2>&1)
BENCHMARK_EXIT_CODE=$?

# Print the output
echo "$BENCHMARK_OUTPUT"

if [ $BENCHMARK_EXIT_CODE -ne 0 ]; then
    log "  ✗ Benchmark failed"
    exit 1
fi

# Extract timestamp from the output
BENCHMARK_TIMESTAMP=$(echo "$BENCHMARK_OUTPUT" | grep "BENCHMARK_TIMESTAMP=" | cut -d'=' -f2 | tr -d '\r\n ')

if [ -z "$BENCHMARK_TIMESTAMP" ]; then
    log "  ⚠ Warning: Could not extract timestamp from benchmark output, using default naming"
    BENCHMARK_TIMESTAMP=""
fi

# Collect battery statistics
log "Collecting battery statistics..."
if [ -n "$BENCHMARK_TIMESTAMP" ]; then
    STATS_FILE="${OUTPUT_DIR}/${SAFE_FILENAME}_${BENCHMARK_TIMESTAMP}_batterystats.txt"
else
    STATS_FILE="${OUTPUT_DIR}/${SAFE_FILENAME}_batterystats.txt"
fi
adb shell dumpsys batterystats > "$STATS_FILE"
log "  ✓ Battery statistics saved to: $STATS_FILE"

# Collect performance metrics CSV file
log "Collecting performance metrics..."
# Find the performance file using the timestamp
DEVICE_PERF_FILE=$(adb shell "ls -t /data/local/tmp/measurements/${SAFE_FILENAME}_${BENCHMARK_TIMESTAMP}_performance.csv 2>/dev/null | head -1" | tr -d '\r')

if [ -n "$DEVICE_PERF_FILE" ]; then
    # Extract just the filename
    PERF_FILENAME=$(basename "$DEVICE_PERF_FILE")
    LOCAL_PERF_FILE="${OUTPUT_DIR}/${PERF_FILENAME}"

    adb pull "$DEVICE_PERF_FILE" "$LOCAL_PERF_FILE" > /dev/null 2>&1
    if [ -f "$LOCAL_PERF_FILE" ]; then
        log "  ✓ Performance metrics saved to: $LOCAL_PERF_FILE"
    else
        log "  ⚠ Warning: Could not pull performance metrics file"
    fi
else
    log "  ⚠ Warning: No performance metrics file found on device"
fi

log "============================================================"
log "Measurement complete for: ${ONNX_RELATIVE_PATH}"

