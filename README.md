# ONNX Inference Power Measurement on Android

A simple tool to measure **power consumption** of ONNX models running on Android devices.

## What Does This Do?

This project helps you:
1. Run ONNX models on Android devices
2. Measure how much power (Watts) each model consumes during inference
3. Generate detailed battery statistics reports

## Features

- **Automated workflow**: Build → Deploy → Measure
- **Batch processing**: Test multiple models automatically
- **Multiple runs**: Run each model multiple times for statistical reliability
- **Detailed measurements**: 3-phase measurement (warmup → silence → measurement)
- **Battery statistics**: Comprehensive power consumption data

## Quick Start

The fastest way to get started:

```bash
# 1. Prepare your models
mkdir -p models
cp /path/to/your/model.onnx models/

# 2. Build and run measurements on all models
./scripts/run_all_models.sh 3    # Run each model 3 times
```

That's it! Results will be in `./measurements/`

## Setup

### Prerequisites

- **macOS** or **Linux** computer
- **Android device** (ARM64 recommended)
- **USB cable** to connect device to computer
- **Android NDK** (for building)

### 1. Install ADB (Android Debug Bridge)

**macOS:**
```bash
brew install android-platform-tools
```

**Linux:**
```bash
sudo apt-get install android-tools-adb
```

**Verify:**
```bash
adb version
```

### 2. Install Android NDK

**Option A: Via Android Studio (Recommended)**
1. Download [Android Studio](https://developer.android.com/studio)
2. Open Android Studio → **Tools** → **SDK Manager**
3. Click **SDK Tools** tab
4. Check ☑ **NDK (Side by side)**
5. Click **Apply**

**Option B: Direct Download**
- Download from [developer.android.com/ndk](https://developer.android.com/ndk/downloads)
- Extract and update `NDK_ROOT` in `Makefile`

### 3. Enable Developer Mode on Android

1. Open **Settings** → **About Phone**
2. Tap **Build Number** 7 times
3. You'll see: "You are now a developer!"

### 4. Enable USB Debugging

1. Open **Settings** → **Developer Options**
2. Enable **USB Debugging**

### 5. Connect Device

**USB Connection:**
```bash
# Connect via USB cable
adb devices

# You should see:
# List of devices attached
# ABC123XYZ    device
```

**WiFi Connection (for accurate power measurement):**
```bash
# 1. Connect via USB first
adb devices

# 2. Enable WiFi mode
adb tcpip 5555

# 3. Find device IP (Settings → WiFi → Your Network → IP)
# 4. Disconnect USB and connect via WiFi
adb connect 192.168.1.100:5555

# 5. Verify
adb devices
# Should show: 192.168.1.100:5555    device
```

> **Note:** Use system terminal (Terminal.app/iTerm2), not IDE terminal for WiFi ADB.

## Usage

### Full Workflow (Recommended)

Run everything with one command:

```bash
# Run each model once
./scripts/run_all_models.sh 1

# Run each model 3 times (recommended for reliability)
./scripts/run_all_models.sh 3
```

This automatically:
1. **Builds** the binary
2. **Deploys** to device
3. **Pushes** each model individually
4. **Measures** power consumption
5. **Saves** results to `./measurements/`

### Step-by-Step Workflow

If you prefer manual control:

#### 1. Build Binary
```bash
make
```

#### 2. Deploy Binary
```bash
./scripts/push_binary_to_device.sh
```

#### 3. Measure Single Model
```bash
# Basic
./scripts/measure_model.sh model.onnx

# Model in subdirectory
./scripts/measure_model.sh zi_t/conv_model.onnx

# With run index (for multiple runs)
./scripts/measure_model.sh model.onnx 2
```

#### 4. Parse Results
```bash
./scripts/parse_measurements.sh
```

## How It Works

### Measurement Process

Each measurement has 3 phases:

1. **Warmup (6s)**: Warms CPU caches, loads model
2. **Silence (6s)**: System stabilization
3. **Measurement (48s)**: 
   - Battery stats reset at start
   - Model runs continuously
   - Android records voltage/current every ~13s
   - Statistics exported at end

### What Gets Measured

Android's `batterystats` provides:
- **Voltage** (mV): Battery voltage
- **Current** (mA): Current draw
- **Power** (W): Calculated as Voltage × Current

### Understanding Results

Example output:
```
Model: conv_w128_h128_cin3_cout3_zi_t.onnx
Samples: 6

VOLTAGE (mV):
  Average: 4051 mV (4.05V)

CURRENT (mA):
  Average: 490 mA
  Max: 563 mA
  Min: 410 mA

POWER:
  Average: 1.986 W
```

**Interpretation:** Model consumed **1.986 Watts** on average.

## Project Structure

```
onnx-runner/
├── src/
│   └── main.cpp                    # C++ inference code
├── scripts/
│   ├── run_all_models.sh           # Full workflow: build → deploy → measure
│   ├── measure_model.sh            # Measure single model
│   ├── push_binary_to_device.sh    # Deploy binary only
│   ├── push_models_to_device.sh    # Deploy all models (legacy)
│   ├── parse_measurements.sh       # Parse results
│   └── export_batterystats.sh      # Export stats (legacy)
├── models/                         # Your ONNX models
│   ├── zi_t/                       # Organized in subdirectories
│   │   ├── conv_model.onnx
│   │   └── relu_model.onnx
│   └── zi_f/
│       └── another_model.onnx
├── measurements/                   # Raw battery statistics
├── reports/                        # Parsed CSV reports
├── onnxruntime/                    # ONNX Runtime libraries
├── Makefile                        # Build configuration
└── README.md                       # This file
```

## Output Files

### measurements/ Directory

Raw battery statistics for each run:

```
measurements/
├── zi_t_conv_model.onnx_batterystats.txt
├── zi_t_conv_model.onnx_run2_batterystats.txt
└── zi_f_another_model.onnx_batterystats.txt
```

Naming:
- Single run: `<model_path>_batterystats.txt`
- Multiple runs: `<model_path>_run<N>_batterystats.txt`

### reports/ Directory

Parsed CSV reports:

```
reports/
├── power_measurements.csv
└── detailed_stats.csv
```

## Configuration

Adjust measurement durations in `scripts/measure_model.sh`:

```bash
WARMUP_DURATION=6       # Cache warmup (seconds)
SILENT_DURATION=6       # Stabilization (seconds)
MEASUREMENT_DURATION=48 # Measurement (seconds)
```

Longer durations = more accurate but slower.

## Tips for Accurate Measurements

1. **Use WiFi ADB**: Disconnect USB to avoid charging interference
2. **Close apps**: Close all background apps
3. **Airplane mode**: Reduce background activity
4. **Screen off**: Turn off screen during measurement
5. **Multiple runs**: Run 3-5 times and average
6. **Cool down**: Let device cool between measurements
7. **Full battery**: Start with fully charged device

## Troubleshooting

### Build Fails

```bash
# Update NDK path
export ANDROID_NDK=/path/to/ndk
make
```

### Device Not Found

```bash
# Restart ADB
adb kill-server
adb start-server
adb devices
```

### Model Not Found Error

The `run_all_models.sh` script automatically pushes each model. If using `measure_model.sh` manually:

```bash
# Verify model exists locally
ls -la models/your_model.onnx

# Push manually
adb push models/your_model.onnx /data/local/tmp/models/
```

### Binary Crashes

```bash
# Check architecture
adb shell getprop ro.product.cpu.abi

# Rebuild for correct arch
make clean
make ANDROID_ARCH=arm64-v8a  # or armeabi-v7a
```

### WiFi ADB Issues

- Use system terminal, not IDE terminal
- Both devices on same WiFi network
- Check device IP hasn't changed
- Reconnect via USB and retry

## Advanced Usage

### Model Input Shapes

Models automatically detect:
- Input dimensions (batch, channels, height, width)
- Data types
- Number of inputs/outputs

No manual configuration needed.

### Parallel Measurements (Multiple Devices)

```bash
# Terminal 1 (Device A)
ADB_SERIAL=192.168.1.100:5555 ./scripts/run_all_models.sh 1

# Terminal 2 (Device B)
ADB_SERIAL=192.168.1.101:5555 ./scripts/run_all_models.sh 1
```

### Custom Binary-Only Deployment

If you only update the binary (not models):

```bash
make
./scripts/push_binary_to_device.sh
```

## License

See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:
1. Test on your device
2. Update README if adding features
3. Follow existing code style

