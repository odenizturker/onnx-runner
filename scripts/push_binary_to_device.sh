#!/usr/bin/env bash
# Push only onnx_runner executable and ONNX Runtime libraries to device
# Models are pushed separately by run_all_models.sh to avoid large transfers

set -euo pipefail

DEVICE_BIN_DIR="/data/local/tmp"
DEVICE_MODELS_DIR="/data/local/tmp/models"
ONNXRUNTIME_DIR="./onnxruntime"

if [ ! -f "./onnx_runner" ]; then
  echo "Error: ./onnx_runner not found. Run 'make' first."
  exit 1
fi

echo "Creating device directories..."
adb shell "mkdir -p ${DEVICE_BIN_DIR}" || true
adb shell "mkdir -p ${DEVICE_MODELS_DIR}" || true

echo "Pushing onnx_runner executable to ${DEVICE_BIN_DIR}/"
adb push ./onnx_runner "${DEVICE_BIN_DIR}/" > /dev/null 2>&1
adb shell "chmod +x ${DEVICE_BIN_DIR}/onnx_runner"

# Push ONNX Runtime shared library if it exists
if [ -d "${ONNXRUNTIME_DIR}/jni" ]; then
  echo "Pushing ONNX Runtime libraries..."
  # Detect which architecture was built
  for arch_dir in ${ONNXRUNTIME_DIR}/jni/*; do
    if [ -d "${arch_dir}" ]; then
      arch=$(basename "${arch_dir}")
      if [ -f "${arch_dir}/libonnxruntime.so" ]; then
        echo "  Pushing libonnxruntime.so for ${arch}"
        adb push "${arch_dir}/libonnxruntime.so" "${DEVICE_BIN_DIR}/" > /dev/null 2>&1
        break
      fi
    fi
  done
fi

echo "Done. Binary and libraries are on device."

