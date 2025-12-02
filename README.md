# ONNX Inference Power Measurement on Android

A simple tool to measure **power consumption** of ONNX models running on Android devices.

## What Does This Do?

This project helps you:
1. Run ONNX models on Android devices
2. Measure how much power (Watts) each model consumes

## Setup

### Prerequisites

Before you start, you'll need:
- **macOS** or **Linux** computer
- **Android device** (ARM64 recommended)
- **USB cable** to connect device to computer
- **Android NDK** (for building)

### 1. Install ADB (Android Debug Bridge)

ADB is used to communicate with your Android device.

**macOS:**
```bash
brew install android-platform-tools
```

**Linux:**
```bash
sudo apt-get install android-tools-adb
```

**Verify installation:**
```bash
adb version
# Should show: Android Debug Bridge version X.X.X
```

### 2. Install Android NDK

The NDK is needed to compile C++ code for Android.

**Option A: Via Android Studio (Recommended)**
1. Download [Android Studio](https://developer.android.com/studio)
2. Open Android Studio → **Tools** → **SDK Manager**
3. Click **SDK Tools** tab
4. Check ☑ **NDK (Side by side)**
5. Click **Apply** to install
6. NDK will be at: `~/Library/Android/sdk/ndk/<version>/`

**Option B: Direct Download**
1. Download from [developer.android.com/ndk](https://developer.android.com/ndk/downloads)
2. Extract and note the path
3. Update `NDK_ROOT` in `Makefile` if needed

### 3. Enable Developer Mode on Android Device

**Steps:**
1. Open **Settings** on your Android device
2. Go to **About Phone** (or **About Device**)
3. Find **Build Number**
4. **Tap "Build Number" 7 times** rapidly
5. You'll see a message: "You are now a developer!"

### 4. Enable USB Debugging

**Steps:**
1. Open **Settings** → **System** → **Developer Options**
   - (On some devices: **Settings** → **Developer Options**)
2. Enable **USB Debugging** (toggle ON)

### 5. Connect Device to Computer

#### Option A: USB Connection (Recommended for Initial Setup)

**Steps:**
1. Connect your Android device via USB cable
2. On your device, you'll see a popup: **"Allow USB debugging?"**
3. Check **"Always allow from this computer"**
4. Tap **OK**

**Verify connection:**
```bash
adb devices
```

**Expected output:**
```
List of devices attached
ABC123XYZ    device
```

If you see `unauthorized` instead of `device`:
- Check your device screen for the authorization popup
- Tap "OK" on the device

If you see no devices:
```bash
# Restart ADB server
adb kill-server
adb start-server
adb devices
```

#### Option B: WiFi Connection (Wireless ADB)

WiFi connection allows you to run measurements without USB cable, which is important for accurate power measurements.

> **⚠️ IMPORTANT: Use System Terminal, Not IDE Terminal**
> 
> If you get `"no route to host"` or connection errors when running `adb connect`, this may be due to IDE terminal networking restrictions.
> 
> **Solution:** Use your system's native terminal app:
> - **macOS**: Use Terminal.app or iTerm2 (not VSCode/JetBrains terminal)
> - **Linux**: Use GNOME Terminal, Konsole, or similar (not IDE terminal)
> 
> IDEs may sandbox terminal networking capabilities, preventing ADB WiFi connections from working properly.

**Steps:**

1. **First, connect via USB** (required for initial setup)
   ```bash
   adb devices
   # Make sure device is connected
   ```

2. **Find your device's IP address**
   
   On your Android device:
   - Open **Settings** → **About Phone** → **Status** → **IP address**
   - Or: **Settings** → **WiFi** → Tap your connected network → IP address
   - Note down the IP (e.g., `192.168.1.100`)

3. **Enable TCP/IP mode on device**
   ```bash
   adb tcpip 5555
   ```
   
   You should see: `restarting in TCP mode port: 5555`

4. **Disconnect USB cable** (optional but recommended for measurements)

5. **Connect via WiFi**
   ```bash
   adb connect <device_ip>:5555
   ```
   
   Example:
   ```bash
   adb connect 192.168.1.100:5555
   ```
   
   You should see: `connected to 192.168.1.100:5555`

6. **Verify WiFi connection**
   ```bash
   adb devices
   ```
   
   **Expected output:**
   ```
   List of devices attached
   192.168.1.100:5555    device
   ```

**Disconnect WiFi ADB:**
```bash
adb disconnect <device_ip>:5555
# Or disconnect all:
adb disconnect
```

**Switch back to USB mode:**
```bash
adb usb
```

**Important Notes:**
- Both computer and device must be on the **same WiFi network**
- WiFi connection may be slower than USB
- Use WiFi mode for power measurements to avoid USB charging interference
- If connection drops, reconnect via USB and repeat steps

### 6. Test ADB Connection

Run a simple command to verify everything works:

```bash
# Check Android version
adb shell getprop ro.build.version.release

# Check device architecture
adb shell getprop ro.product.cpu.abi
# Should show: arm64-v8a (64-bit) or armeabi-v7a (32-bit)
```

### 7. Prepare Models

Place your ONNX model files in the `models/` directory:

```bash
mkdir -p models
cp /path/to/your/model.onnx models/
ls models/
```

## Quick Start

### 1. Build the Binary

```bash
make
```

This downloads ONNX Runtime and builds an Android executable.

### 2. Deploy to Device

Connect your Android device via USB and run:

```bash
./scripts/push_models_to_device.sh
```

### 3. Run Measurements

**Test all models (recommended):**
```bash
./scripts/run_all_models.sh 3    # Run each model 3 times
```

**Or test a single model:**
```bash
./scripts/run_full_measurement_for_model.sh model.onnx
```

### 4. View Results

```bash
./scripts/parse_measurements.sh
cat reports/model_report.txt
```

## How It Works

### The Measurement Process

Each measurement runs in 3 phases:

1. **Warmup (6s)**: Loads the model and runs initial inferences to warm up the CPU
2. **Silent (6s)**: Continues running to stabilize system temperature and power draw
3. **Measurement (48s)**: Actual power measurement happens here
   - Battery stats are reset before this phase
   - Android records voltage and current every ~13 seconds
   - Raw data saved to `./measurements/`

### What Gets Measured?

Android's `batterystats` records:
- **Voltage** (mV): Battery voltage during inference
- **Current** (mA): How much current is drawn (positive = discharging)
- **Power** (W): Calculated as `Voltage × Current`

### Understanding the Report

Example report:
```
Model: conv_w128_h128_cin1_cout3_zi_t.onnx
Measurement Samples: 6

VOLTAGE STATISTICS (mV)
  Average: 4051 mV (4.05V)

CURRENT STATISTICS (mA - discharge)
  Average: 490 mA
  Maximum: 563 mA
  Minimum: 410 mA

POWER CONSUMPTION
  Average Power: 1.986 W
```

**What this means:**
- The model consumed an average of **1.986 Watts** during the 48-second measurement
- Current varied between 410-563 mA depending on workload
- 6 samples were collected (one every ~13 seconds)

## Project Structure

```
├── src/main.cpp                    # Inference binary (runs model for N seconds)
├── models/                         # Put your .onnx models here
├── measurements/                   # Raw battery statistics (auto-generated)
├── reports/                        # Human-readable reports (auto-generated)
├── scripts/
│   ├── run_all_models.sh          # Run all models N times
│   ├── run_full_measurement_for_model.sh  # Run single model measurement
│   ├── parse_measurements.sh      # Convert raw data to readable reports
│   └── push_models_to_device.sh   # Deploy binary and models to device
└── Makefile                        # Build system
```

## Scripts Explained

### `run_all_models.sh <runs>`
Loops through all `.onnx` files in `./models/` and runs each one multiple times.
```bash
./scripts/run_all_models.sh 3    # Run each model 3 times
```

### `run_full_measurement_for_model.sh <model.onnx>`
Runs a complete measurement for one model:
1. Warmup phase (6s)
2. Silent phase (6s)
3. Reset battery stats
4. Measurement phase (48s)
5. Save results

### `parse_measurements.sh`
Reads raw battery data from `./measurements/` and generates readable reports in `./reports/`.

### `push_models_to_device.sh`
Deploys the binary, libraries, and models to the Android device at `/data/local/tmp/`.

## Customizing Measurement Duration

Edit the script: `./scripts/run_full_measurement_for_model.sh`

```bash
# Duration configuration (in seconds)
WARMUP_DURATION=6      # Warmup phase
SILENT_DURATION=6      # Silent phase
MEASUREMENT_DURATION=48 # Actual measurement
```

**Why these durations?**
- **Warmup**: Loads model into memory, CPU reaches steady state
- **Silent**: Temperature stabilizes, power draw becomes consistent
- **Measurement**: Longer = more samples = more accurate average

## The Binary

The C++ binary (`onnx_runner`) runs on the Android device:

```bash
# Usage on device
./onnx_runner <model_filename> <duration_seconds>
```

**What it does:**
1. Loads the ONNX model from `/data/local/tmp/models/`
2. Generates random input data (matches model's expected input shape)
3. Runs inference repeatedly for the specified duration
4. Prints throughput statistics

**Example:**
```bash
./onnx_runner model.onnx 10    # Run for 10 seconds
```

## Important Notes

- **Use WiFi ADB for measurements** - USB connection provides charging current which interferes with power readings
  - Deploy models via USB first: `./scripts/push_models_to_device.sh`
  - Then switch to WiFi: `adb tcpip 5555` → `adb connect <ip>:5555`
  - Disconnect USB cable before running measurements
- **Close background apps** for consistent results
- **Run multiple times** (3+) and average the results
- **Let device cool down** between measurements (wait 1-2 minutes)
- Input data is random (doesn't affect power, only throughput)
- Models must be in `./models/` directory before deployment

## Troubleshooting

### Device Connection Issues

**"No devices/emulators found" or `adb devices` shows empty list**
```bash
# Restart ADB server
adb kill-server
adb start-server
adb devices

# Check USB cable and port
# Try a different USB port or cable
```

**Device shows as `unauthorized`**
- Check your device screen for USB debugging authorization popup
- Tap "Allow" and check "Always allow from this computer"
- If popup doesn't appear:
  ```bash
  adb kill-server
  # Unplug and replug USB cable
  adb start-server
  ```

**Device shows as `offline`**
```bash
adb kill-server && adb start-server
# Or reboot the device
```

**WiFi ADB connection issues**

*"no route to host" or cannot connect via WiFi:*
```bash
# First, try using system terminal instead of IDE terminal
# IDEs (VSCode, JetBrains) may block networking in their terminals
# Use Terminal.app (macOS) or native terminal (Linux)

# Make sure you enabled TCP mode first via USB
adb tcpip 5555

# Verify device IP is correct
# Settings → WiFi → Tap network → IP address

# Try reconnecting
adb connect <device_ip>:5555
```

*WiFi connection keeps dropping:*
- Check if device and computer are on the same WiFi network
- Check if device has stable WiFi connection
- Device may have gone to sleep - adjust screen timeout
- Router may be blocking ADB port (5555)
- Try reconnecting:
  ```bash
  adb disconnect
  adb connect <device_ip>:5555
  ```

*WiFi connection is very slow:*
- WiFi is slower than USB for large file transfers
- Use USB connection for initial deployment (`push_models_to_device.sh`)
- Use WiFi only for running measurements

*"Connection refused" error:*
```bash
# Reconnect via USB and enable TCP mode again
adb usb
adb devices
adb tcpip 5555
adb connect <device_ip>:5555
```

**Multiple devices connected**
```bash
# List all devices
adb devices

# Use specific device
adb -s <device_id> shell
# Example: adb -s ABC123XYZ shell
# Example (WiFi): adb -s 192.168.1.100:5555 shell
```

### Build Issues

**"NDK not found"**
```bash
# Check if NDK exists
ls ~/Library/Android/sdk/ndk/

# Update Makefile with correct path
# Edit Makefile and set: NDK_ROOT = /your/ndk/path
```

**"No .onnx models found"**
```bash
# Put your models in the models/ directory
cp your_model.onnx ./models/
ls models/
```

### Runtime Issues

**"Permission denied"**
```bash
# Fix executable permissions
adb shell chmod +x /data/local/tmp/onnx_runner
```

**"error while loading shared libraries: libonnxruntime.so"**
```bash
# Re-push the library
./scripts/push_models_to_device.sh

# Verify library exists
adb shell ls -la /data/local/tmp/libonnxruntime.so
```

**"Model file not found on device"**
```bash
# Check if model was pushed
adb shell ls -la /data/local/tmp/models/

# Re-push models
./scripts/push_models_to_device.sh
```

### Measurement Issues

**Power readings show charging (negative current)**
- **Unplug your device from USB** before running measurements
- Charging current interferes with power measurements
- Run measurements on battery power only

**Inconsistent results**
- Close all background apps before measurement
- Let device cool down between runs (wait 1-2 minutes)
- Run measurements 3+ times and average results
- Ensure device is not overheating

**Very low sample count (< 3 samples)**
- Measurement duration too short
- Increase `MEASUREMENT_DURATION` in `run_full_measurement_for_model.sh`
- Recommended: at least 48 seconds for 3-4 samples

## Requirements

- macOS (tested) or Linux
- Android NDK (v27+)
- Android device with USB debugging enabled
- ONNX models (.onnx files)

## Workflow Summary

```bash
# One-time setup
make
./scripts/push_models_to_device.sh

# Run measurements
./scripts/run_all_models.sh 3

# View results
./scripts/parse_measurements.sh
cat reports/*.txt
```

