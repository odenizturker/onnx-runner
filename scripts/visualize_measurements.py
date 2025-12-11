#!/usr/bin/env python3
"""
Visualize ONNX model power measurement results as a table.

This script loads the measurements DataFrame and creates a table visualization
showing energy consumption sorted by highest to lowest, with run counts for
models that have been measured multiple times.

Usage:
    python3 visualize_measurements.py [pkl_file]

If no file is specified, it will use the most recent pkl file from reports/
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Configuration
# Get the script's directory and set paths relative to project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "reports" / "plots"


def find_latest_pkl():
    """Find the most recent pkl file in reports directory."""
    reports_dir = PROJECT_ROOT / "reports"

    if not reports_dir.exists():
        print("Error: reports/ directory not found")
        return None

    pkl_files = list(reports_dir.glob("measurements_data_*.pkl"))

    if not pkl_files:
        print("Error: No pickle files found in reports/")
        return None

    latest = sorted(pkl_files)[-1]
    return latest


def aggregate_measurements(df):
    """
    Aggregate measurements by model name.
    Calculate average metrics and count runs for each model.

    A "run" is defined as a unique timestamp (date_time) for a model.
    Models with the same filename but different timestamps represent
    multiple measurement runs of the same model.
    """
    # Group by filename and aggregate
    df_agg = df.groupby('filename').agg({
        'avg_power': 'mean',
        'energy': 'mean',
        'iterations': 'mean',
        'usperinf': 'mean',
        'totaltimesec': 'mean',
    }).reset_index()

    # Count unique timestamps (runs) for each model
    # Each unique date_time for a model represents one measurement run
    run_counts = df.groupby('filename')['date_time'].nunique().reset_index(name='runs')
    df_agg = df_agg.merge(run_counts, on='filename')

    # Rename filename to model_name for clarity
    df_agg.rename(columns={'filename': 'model_name'}, inplace=True)

    # Sort by number of runs (descending), then by energy (descending)
    df_agg = df_agg.sort_values(['runs', 'energy'], ascending=[False, False]).reset_index(drop=True)

    return df_agg


def create_measurement_table(df_agg, output_dir):
    """
    Create a table visualization of measurements sorted by energy consumption.
    Shows: Model Name, Runs, Avg Power (W), Energy (Wh), Iterations,
           Time/Inference (ms), Total Time (s)
    """
    # Prepare display data
    display_df = df_agg.copy()

    # Shorten model names for better display
    display_df['Model'] = display_df['model_name'].apply(
        lambda x: x.split('/')[-1].replace('.onnx', '')
    )

    # Format numeric columns
    display_df['Runs'] = display_df['runs'].astype(int)
    display_df['Avg Power (W)'] = display_df['avg_power'].apply(lambda x: f'{x:.3f}')
    display_df['Energy (Wh)'] = display_df['energy'].apply(lambda x: f'{x:.6f}')
    display_df['Iterations'] = display_df['iterations'].astype(int)
    display_df['Time/Inf (ms)'] = (display_df['usperinf'] / 1000).apply(lambda x: f'{x:.2f}')
    display_df['Total Time (s)'] = display_df['totaltimesec'].apply(lambda x: f'{x:.2f}')

    # Select columns for display
    table_data = display_df[['Model', 'Runs', 'Avg Power (W)', 'Energy (Wh)',
                              'Iterations', 'Time/Inf (ms)', 'Total Time (s)']]

    # Calculate figure size based on number of rows
    num_rows = len(table_data)
    row_height = 0.4
    header_height = 0.6
    fig_height = min(header_height + (num_rows * row_height), 40)  # Cap at 40 inches

    # Create figure
    fig, ax = plt.subplots(figsize=(18, fig_height))
    ax.axis('tight')
    ax.axis('off')

    # Create table
    table = ax.table(cellText=table_data.values,
                    colLabels=table_data.columns,
                    cellLoc='left',
                    loc='center',
                    colWidths=[0.35, 0.08, 0.12, 0.12, 0.11, 0.12, 0.10])

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)

    # Color the header
    for i in range(len(table_data.columns)):
        cell = table[(0, i)]
        cell.set_facecolor('#4472C4')
        cell.set_text_props(weight='bold', color='white')

    # Color rows with gradient based on number of runs
    max_runs = df_agg['runs'].max()
    min_runs = df_agg['runs'].min()

    for i in range(len(table_data)):
        row_num = i + 1
        runs_val = df_agg.iloc[i]['runs']

        # Normalize runs value to 0-1 range
        if max_runs > min_runs:
            norm_runs = (runs_val - min_runs) / (max_runs - min_runs)
        else:
            norm_runs = 0.5

        # Blue gradient - darker blue for more runs
        r = 0.3 + (1 - norm_runs) * 0.7  # 0.3 to 1.0
        g = 0.5 + (1 - norm_runs) * 0.5  # 0.5 to 1.0
        b = 1.0  # Always 1.0 for blue

        row_color = (r, g, b, 0.3)  # Alpha = 0.3 for transparency

        for j in range(len(table_data.columns)):
            cell = table[(row_num, j)]
            cell.set_facecolor(row_color)

    # Add title
    title = f'ONNX Model Power Measurements - Sorted by Number of Runs\n'
    title += f'Total Models: {df_agg["model_name"].nunique()} | '
    title += f'Total Measurements: {df_agg["runs"].sum()} | '
    title += f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

    plt.title(title, fontsize=14, fontweight='bold', pad=20)

    # Save
    output_file = output_dir / "measurements_table.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"     ✓ Saved: {output_file.name}")
    plt.close()

    return table_data


def create_measurement_table_by_runs(df_agg, output_dir):
    """
    Create a table visualization of measurements sorted by number of runs.
    Shows: Model Name, Runs, Avg Power (W), Energy (Wh), Iterations,
           Time/Inference (ms), Total Time (s)
    """
    # Sort by runs (highest first), then by energy
    df_sorted = df_agg.sort_values(['runs', 'energy'], ascending=[False, False]).reset_index(drop=True)

    # Prepare display data
    display_df = df_sorted.copy()

    # Shorten model names for better display
    display_df['Model'] = display_df['model_name'].apply(
        lambda x: x.split('/')[-1].replace('.onnx', '')
    )

    # Format numeric columns
    display_df['Runs'] = display_df['runs'].astype(int)
    display_df['Avg Power (W)'] = display_df['avg_power'].apply(lambda x: f'{x:.3f}')
    display_df['Energy (Wh)'] = display_df['energy'].apply(lambda x: f'{x:.6f}')
    display_df['Iterations'] = display_df['iterations'].astype(int)
    display_df['Time/Inf (ms)'] = (display_df['usperinf'] / 1000).apply(lambda x: f'{x:.2f}')
    display_df['Total Time (s)'] = display_df['totaltimesec'].apply(lambda x: f'{x:.2f}')

    # Select columns for display
    table_data = display_df[['Model', 'Runs', 'Avg Power (W)', 'Energy (Wh)',
                              'Iterations', 'Time/Inf (ms)', 'Total Time (s)']]

    # Calculate figure size based on number of rows
    num_rows = len(table_data)
    row_height = 0.4
    header_height = 0.6
    fig_height = min(header_height + (num_rows * row_height), 40)  # Cap at 40 inches

    # Create figure
    fig, ax = plt.subplots(figsize=(18, fig_height))
    ax.axis('tight')
    ax.axis('off')

    # Create table
    table = ax.table(cellText=table_data.values,
                    colLabels=table_data.columns,
                    cellLoc='left',
                    loc='center',
                    colWidths=[0.35, 0.08, 0.12, 0.12, 0.11, 0.12, 0.10])

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)

    # Color the header
    for i in range(len(table_data.columns)):
        cell = table[(0, i)]
        cell.set_facecolor('#4472C4')
        cell.set_text_props(weight='bold', color='white')

    # Color rows with gradient based on number of runs
    max_runs = df_sorted['runs'].max()
    min_runs = df_sorted['runs'].min()

    for i in range(len(table_data)):
        row_num = i + 1
        runs_val = df_sorted.iloc[i]['runs']

        # Normalize runs value to 0-1 range
        if max_runs > min_runs:
            norm_runs = (runs_val - min_runs) / (max_runs - min_runs)
        else:
            norm_runs = 0.5

        # Blue gradient - darker blue for more runs
        r = 0.3 + (1 - norm_runs) * 0.7  # 0.3 to 1.0
        g = 0.5 + (1 - norm_runs) * 0.5  # 0.5 to 1.0
        b = 1.0  # Always 1.0 for blue

        row_color = (r, g, b, 0.3)  # Alpha = 0.3 for transparency

        for j in range(len(table_data.columns)):
            cell = table[(row_num, j)]
            cell.set_facecolor(row_color)

    # Add title
    title = f'ONNX Model Power Measurements - Sorted by Number of Runs\n'
    title += f'Total Models: {df_sorted["model_name"].nunique()} | '
    title += f'Total Measurements: {df_sorted["runs"].sum()} | '
    title += f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

    plt.title(title, fontsize=14, fontweight='bold', pad=20)

    # Save
    output_file = output_dir / "measurements_table_by_runs.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"     ✓ Saved: {output_file.name}")
    plt.close()

    return table_data


def print_summary_stats(df, df_agg):
    """Print summary statistics to console."""
    print("\n" + "=" * 70)
    print("📊 SUMMARY STATISTICS")
    print("=" * 70)
    print(f"\nTotal unique models: {df['filename'].nunique()}")
    print(f"Total measurements: {len(df)}")
    print(f"Average runs per model: {df_agg['runs'].mean():.1f}")
    print(f"\nPower Consumption:")
    print(f"  Average: {df_agg['avg_power'].mean():.3f} W")
    print(f"  Min: {df_agg['avg_power'].min():.3f} W")
    print(f"  Max: {df_agg['avg_power'].max():.3f} W")
    print(f"\nEnergy Consumption:")
    print(f"  Average: {df_agg['energy'].mean():.6f} Wh")
    print(f"  Min: {df_agg['energy'].min():.6f} Wh")
    print(f"  Max: {df_agg['energy'].max():.6f} Wh")
    print(f"  Total: {df_agg['energy'].sum():.6f} Wh")
    print(f"\nPerformance:")
    print(f"  Avg iterations: {df_agg['iterations'].mean():.0f}")
    print(f"  Avg time per inference: {df_agg['usperinf'].mean()/1000:.2f} ms")
    print(f"  Avg total time: {df_agg['totaltimesec'].mean():.2f} s")

    # Top 5 energy consumers
    print(f"\n🔥 TOP 5 ENERGY CONSUMERS:")
    for idx, row in df_agg.head(5).iterrows():
        model_name = row['model_name'].split('/')[-1].replace('.onnx', '')
        print(f"  {idx+1}. {model_name[:60]}")
        print(f"     Energy: {row['energy']:.6f} Wh | Runs: {row['runs']} | Avg Power: {row['avg_power']:.3f} W")

    print("=" * 70)


def main():
    """Main execution function."""
    print("=" * 70)
    print("ONNX Measurement Table Visualization")
    print("=" * 70)

    # Determine which file to load
    if len(sys.argv) > 1:
        pkl_path = Path(sys.argv[1])
    else:
        pkl_path = find_latest_pkl()
        if pkl_path is None:
            sys.exit(1)

    if not pkl_path.exists():
        print(f"Error: File not found: {pkl_path}")
        sys.exit(1)

    # Load DataFrame
    print(f"\n📂 Loading: {pkl_path}")
    df = pd.read_pickle(pkl_path)
    print(f"   Loaded {len(df)} measurements")

    # Aggregate measurements by model
    print("\n🔍 Aggregating measurements by model...")
    df_agg = aggregate_measurements(df)
    print(f"   Aggregated into {len(df_agg)} unique models")

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📊 Generating table in: {output_dir}")

    # Generate table visualization
    print("\n📈 Creating table visualization:")
    table_data = create_measurement_table(df_agg, output_dir)

    # Print summary statistics
    print_summary_stats(df, df_agg)

    print("\n" + "=" * 70)
    print("✅ Table visualization generated successfully!")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print("=" * 70)


if __name__ == "__main__":
    main()

