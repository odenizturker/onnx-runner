#!/usr/bin/env bash
# Push all .onnx files in ./models and onnx_runner executable to device. Run manually.

set -euo pipefail

DEVICE_DIR="/data/local/tmp/models"
DEVICE_BIN_DIR="/data/local/tmp"
ONNXRUNTIME_DIR="./onnxruntime"

if [ ! -d "./models" ]; then
  echo "Error: ./models directory does not exist. Create and add .onnx files first."
  exit 1
fi

if [ ! -f "./onnx_runner" ]; then
  echo "Error: ./onnx_runner not found. Run 'make' first."
  exit 1
fi

echo "Creating device directories..."
adb shell "mkdir -p ${DEVICE_DIR}" || true
adb shell "mkdir -p ${DEVICE_BIN_DIR}" || true

echo "Pushing onnx_runner executable to ${DEVICE_BIN_DIR}/"
adb push ./onnx_runner "${DEVICE_BIN_DIR}/"
adb shell "chmod +x ${DEVICE_BIN_DIR}/onnx_runner"

# Push ONNX Runtime shared library if it exists
if [ -d "${ONNXRUNTIME_DIR}/jni" ]; then
  echo "Pushing ONNX Runtime libraries..."
  # Detect which architecture was built
  for arch_dir in ${ONNXRUNTIME_DIR}/jni/*; do
    if [ -d "${arch_dir}" ]; then
      arch=$(basename "${arch_dir}")
      if [ -f "${arch_dir}/libonnxruntime.so" ]; then
        echo "Pushing libonnxruntime.so for ${arch}"
        adb push "${arch_dir}/libonnxruntime.so" "${DEVICE_BIN_DIR}/"
        break
      fi
    fi
  done
fi

echo "Pushing all .onnx models (including subdirectories)..."

# Build array of model files
model_files=()
while IFS= read -r -d '' model_path; do
    model_files+=("$model_path")
done < <(find ./models -name "*.onnx" -type f -print0)

echo "Found ${#model_files[@]} model file(s)"

# Push each model file
for model_path in "${model_files[@]}"; do
  # Get path relative to ./models (e.g., "subfolder/model.onnx" or "model.onnx")
  relative_path="${model_path#./models/}"

  # Create subdirectory on device if needed
  model_dir=$(dirname "${relative_path}")
  if [ "${model_dir}" != "." ]; then
    echo "  Creating directory: ${DEVICE_DIR}/${model_dir}"
    adb shell "mkdir -p ${DEVICE_DIR}/${model_dir}" 2>/dev/null || true
    echo "  Pushing ${model_path} -> ${DEVICE_DIR}/${model_dir}/"
    adb push "${model_path}" "${DEVICE_DIR}/${model_dir}/" 2>&1 | grep -v "^$"
  else
    echo "  Pushing ${model_path} -> ${DEVICE_DIR}/"
    adb push "${model_path}" "${DEVICE_DIR}/" 2>&1 | grep -v "^$"
  fi
done

echo "Done. Binary and models are on device."
