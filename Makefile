# Makefile for building onnx_runner for Android with ONNX Runtime

CXX := g++
CXXFLAGS := -std=c++17 -O2 -pthread -Wall -Wextra
SRC := src/main.cpp
BIN := onnx_runner

# ONNX Runtime configuration
ONNXRUNTIME_VERSION := 1.17.1
ONNXRUNTIME_DIR := ./onnxruntime

# Android NDK configuration
ANDROID_NDK ?= $(HOME)/Library/Android/sdk/ndk/27.2.12479018
ANDROID_API := 24
ANDROID_ARCH := arm64-v8a

ifeq ($(ANDROID_ARCH),arm64-v8a)
    ANDROID_TOOLCHAIN := aarch64-linux-android
    ONNX_ANDROID_ARCH := arm64-v8a
else ifeq ($(ANDROID_ARCH),armeabi-v7a)
    ANDROID_TOOLCHAIN := armv7a-linux-androideabi
    ONNX_ANDROID_ARCH := armeabi-v7a
else
    $(error Unsupported ANDROID_ARCH: $(ANDROID_ARCH))
endif

ANDROID_CXX := $(ANDROID_NDK)/toolchains/llvm/prebuilt/darwin-x86_64/bin/$(ANDROID_TOOLCHAIN)$(ANDROID_API)-clang++

.PHONY: all clean download-onnxruntime

# Default target: build for Android device
all: download-onnxruntime
	@if [ ! -d "$(ANDROID_NDK)" ]; then \
		echo ""; \
		echo "============================================"; \
		echo "Android NDK not found at: $(ANDROID_NDK)"; \
		echo "============================================"; \
		echo ""; \
		echo "Please install Android NDK:"; \
		echo "1. Install Android Studio"; \
		echo "2. Open SDK Manager (Tools → SDK Manager)"; \
		echo "3. Go to SDK Tools tab"; \
		echo "4. Check 'NDK (Side by side)'"; \
		echo "5. Click Apply to install"; \
		echo ""; \
		echo "Or specify custom path:"; \
		echo "  make ANDROID_NDK=/path/to/ndk"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Building Android binary with ONNX Runtime..."
	$(ANDROID_CXX) $(CXXFLAGS) \
		-I$(ONNXRUNTIME_DIR)/headers \
		-L$(ONNXRUNTIME_DIR)/jni/$(ONNX_ANDROID_ARCH) \
		-static-libstdc++ \
		-o $(BIN) $(SRC) \
		-lonnxruntime
	@echo ""
	@echo "✓ Build complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Deploy to device:			./scripts/push_models_to_device.sh"
	@echo "2. Run measurement for a model:		./scripts/run_full_measurement_for_model.sh <model.onnx>"
	@echo "3. Run measurements for all models:	./scripts/run_all_models.sh"

# Download ONNX Runtime prebuilt Android package
download-onnxruntime:
	@mkdir -p $(ONNXRUNTIME_DIR)
	@if [ ! -f "$(ONNXRUNTIME_DIR)/onnxruntime-android-$(ONNXRUNTIME_VERSION).aar" ]; then \
		echo "Downloading ONNX Runtime Android package..."; \
		curl -L "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/$(ONNXRUNTIME_VERSION)/onnxruntime-android-$(ONNXRUNTIME_VERSION).aar" \
			-o "$(ONNXRUNTIME_DIR)/onnxruntime-android-$(ONNXRUNTIME_VERSION).aar"; \
		echo "Extracting ONNX Runtime libraries..."; \
		cd $(ONNXRUNTIME_DIR) && unzip -o -q "onnxruntime-android-$(ONNXRUNTIME_VERSION).aar" || true; \
		echo "ONNX Runtime ready"; \
	fi

clean:
	rm -f $(BIN)
	rm -rf $(ONNXRUNTIME_DIR)

