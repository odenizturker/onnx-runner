#!/usr/bin/env python3
"""
Parse ONNX model measurement files and create a pandas DataFrame.

This script reads performance CSV files and corresponding batterystats files,
extracts relevant metrics, and creates a consolidated DataFrame saved as pickle.

Output columns:
- filename: Model name (e.g., "conv_w128_h128_cin1_cout1_zi_t.onnx")
- date_time: Timestamp of measurement (YYYYMMDD_HHMMSS)
- current_list: List of current samples in mA
- voltage_list: List of voltage samples in mV
- avg_power: Average power consumption in Watts
- energy: Energy per single inference in Watt-hours
- iterations: Number of inference iterations
- usperinf: Microseconds per inference
- totaltimesec: Total measurement time in seconds
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

# Configuration
MEASUREMENTS_DIR = "./measurements"
REPORTS_DIR = "./reports"


def parse_performance_csv(csv_path: Path) -> Optional[Dict]:
    """
    Parse performance CSV file and extract metrics.

    Returns dict with: model, timestamp, iterations, us_per_inference, total_time_sec
    """
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return None

        row = df.iloc[0]
        return {
            'model': row['model'],
            'timestamp': row['timestamp'],
            'iterations': int(row['measurement_iterations']),
            'us_per_inference': float(row['us_per_inference']),
            'total_time_sec': float(row['total_time_sec']),
        }
    except Exception as e:
        print(f"Error parsing {csv_path}: {e}", file=sys.stderr)
        return None


def parse_batterystats_samples(stats_path: Path, total_time_sec: float) -> Optional[Dict]:
    """
    Extract voltage and current measurements from batterystats file.

    Returns dict with: voltage_list, current_list, avg_power, energy
    """
    try:
        with open(stats_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Find lines with current measurements
        current_lines = []
        for line in content.split('\n'):
            if 'current=' in line:
                current_lines.append(line)

        if not current_lines:
            return None

        voltage_list = []
        current_list = []
        last_volt = None

        # Extract voltage and current pairs
        for line in current_lines:
            # Extract voltage
            volt_match = re.search(r'volt=(\d+)', line)
            if volt_match:
                last_volt = int(volt_match.group(1))

            # Extract current
            curr_match = re.search(r'current=(-?\d+)', line)
            if curr_match and last_volt is not None:
                current = int(curr_match.group(1))
                voltage_list.append(last_volt)
                current_list.append(current)

        if not voltage_list or not current_list:
            return None

        # Calculate average power
        # Power (W) = Voltage (mV) * |Current| (mA) / 1,000,000
        # Current is negative for discharge, so we take absolute value
        power_samples = [
            (v * abs(c)) / 1_000_000.0
            for v, c in zip(voltage_list, current_list)
        ]
        avg_power = sum(power_samples) / len(power_samples) if power_samples else 0.0

        # Calculate energy (Wh) = Power (W) * Time (s) / 3600
        energy = (avg_power * total_time_sec) / 3600.0 if total_time_sec > 0 else 0.0

        return {
            'voltage_list': voltage_list,
            'current_list': current_list,
            'avg_power': avg_power,
            'energy': energy,
        }
    except Exception as e:
        print(f"Error parsing {stats_path}: {e}", file=sys.stderr)
        return None


def find_matching_batterystats(perf_path: Path, measurements_dir: Path) -> Optional[Path]:
    """
    Find the batterystats file that matches the performance file.

    Performance file format: model_TIMESTAMP_performance.csv
    Batterystats file format: model_TIMESTAMP_batterystats.txt
    """
    # Remove _performance.csv suffix
    base_name = perf_path.stem.replace('_performance', '')

    # Look for matching batterystats file with same timestamp
    stats_path = measurements_dir / f"{base_name}_batterystats.txt"

    if stats_path.exists():
        return stats_path

    return None


def extract_model_name_from_path(model_path: str) -> str:
    """
    Extract just the model filename from a path like 'zi_t/model.onnx'.
    Returns the full path as stored in the performance CSV.
    """
    return model_path


def process_measurements(measurements_dir: Path) -> pd.DataFrame:
    """
    Process all measurement files and create a DataFrame.

    Returns DataFrame with columns:
    - filename: Model name
    - date_time: Timestamp
    - current_list: List of current samples
    - voltage_list: List of voltage samples
    - avg_power: Average power (W)
    - energy: Energy per single inference (Wh)
    - iterations: Number of inferences
    - usperinf: Microseconds per inference
    - totaltimesec: Total time (seconds)
    """
    records = []

    # Find all performance CSV files
    perf_files = list(measurements_dir.glob("*_performance.csv"))

    if not perf_files:
        print("No performance files found!", file=sys.stderr)
        return pd.DataFrame()

    print(f"Found {len(perf_files)} performance file(s)")

    processed = 0
    skipped = 0

    for perf_path in sorted(perf_files):
        # Parse performance data
        perf_data = parse_performance_csv(perf_path)
        if not perf_data:
            print(f"  ⚠ Skipped (no perf data): {perf_path.name}", file=sys.stderr)
            skipped += 1
            continue

        # Find matching batterystats file
        stats_path = find_matching_batterystats(perf_path, measurements_dir)
        if not stats_path:
            print(f"  ⚠ Skipped (no batterystats): {perf_path.name}", file=sys.stderr)
            skipped += 1
            continue

        # Parse battery data
        battery_data = parse_batterystats_samples(stats_path, perf_data['total_time_sec'])
        if not battery_data:
            print(f"  ⚠ Skipped (no battery data): {perf_path.name}", file=sys.stderr)
            skipped += 1
            continue

        # Calculate energy per inference
        # Energy per inference (Wh) = Power (W) * Time per inference (s) / 3600
        time_per_inf_sec = perf_data['us_per_inference'] / 1_000_000.0  # Convert µs to seconds
        energy_per_inf = (battery_data['avg_power'] * time_per_inf_sec) / 3600.0

        # Create record
        record = {
            'filename': perf_data['model'],
            'date_time': perf_data['timestamp'],
            'current_list': battery_data['current_list'],
            'voltage_list': battery_data['voltage_list'],
            'avg_power': battery_data['avg_power'],
            'iterations': perf_data['iterations'],
            'usperinf': perf_data['us_per_inference'],
            'totaltimesec': perf_data['total_time_sec'],
            'energy': energy_per_inf,
        }

        records.append(record)
        processed += 1
        print(f"  ✓ Processed: {perf_data['model']} ({perf_data['timestamp']})")

    print(f"\nProcessed: {processed}, Skipped: {skipped}")

    # Create DataFrame
    df = pd.DataFrame(records)

    # Reorder columns to match specification
    column_order = [
        'current_list',
        'voltage_list',
        'filename',
        'date_time',
        'avg_power',
        'iterations',
        'usperinf',
        'totaltimesec',
        'energy'
    ]

    df = df[column_order]

    return df


def main():
    """Main entry point."""
    print("=" * 60)
    print("ONNX Measurement Data Parser")
    print("=" * 60)

    measurements_dir = Path(MEASUREMENTS_DIR)

    if not measurements_dir.exists():
        print(f"ERROR: Directory not found: {measurements_dir}", file=sys.stderr)
        sys.exit(1)

    # Process measurements
    df = process_measurements(measurements_dir)

    if df.empty:
        print("\nNo data to save!", file=sys.stderr)
        sys.exit(1)

    # Generate timestamp for output filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save to pickle in reports directory
    reports_dir = Path(REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_filename = f"measurements_data_{timestamp}.pkl"
    output_path = reports_dir / output_filename

    try:
        df.to_pickle(str(output_path))
        print(f"\n✓ DataFrame saved to: {output_path.absolute()}")
        print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"  Unique models: {df['filename'].nunique()}")
        print(f"  Date range: {df['date_time'].min()} to {df['date_time'].max()}")
    except Exception as e:
        print(f"\n✗ Error saving pickle file: {e}", file=sys.stderr)
        sys.exit(1)

    # Display sample
    print("\nSample data (first 3 rows):")
    print("-" * 60)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 50)
    print(df.head(3).to_string())

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()

