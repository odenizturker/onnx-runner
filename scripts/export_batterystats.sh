#!/usr/bin/env bash
# Export batterystats to measurements/<onnx_filename>_batterystats.txt
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <onnx_filename>"
  exit 1
fi

ONNX_NAME="$1"
OUT_DIR="./measurements"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/${ONNX_NAME}_batterystats.txt"

echo "Collecting batterystats -> ${OUT_FILE}"
adb shell dumpsys batterystats > "${OUT_FILE}" || {
  echo "Warning: adb command failed; check device connectivity."
  exit 1
}

echo "Saved to ${OUT_FILE}"

