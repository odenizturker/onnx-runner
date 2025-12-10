#!/usr/bin/env python3
"""
Visualize ONNX model power measurement results.

This script loads the measurements DataFrame and creates various plots to analyze:
- Power consumption distribution
- Energy consumption by model
- Performance vs power trade-offs
- Model type comparisons
- Voltage and current variations

Usage:
    python3 visualize_measurements.py [pkl_file]

If no file is specified, it will use the most recent pkl file from reports/
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from datetime import datetime

# Configuration
PLOT_STYLE = 'seaborn-v0_8-darkgrid'
FIGURE_SIZE = (16, 10)
OUTPUT_DIR = "../reports/plots"


def find_latest_pkl():
    """Find the most recent pkl file in reports directory."""
    reports_dir = Path("../reports")

    if not reports_dir.exists():
        print("Error: reports/ directory not found")
        return None

    pkl_files = list(reports_dir.glob("measurements_data_*.pkl"))

    if not pkl_files:
        print("Error: No pickle files found in reports/")
        return None

    latest = sorted(pkl_files)[-1]
    return latest


def extract_model_info(df):
    """Extract model type and parameters from filename."""
    # Extract model type (conv, tconv, relu, add, mul, etc.)
    df['model_type'] = df['filename'].str.extract(r'(conv|tconv|relu|add|mul|fc|decoder|encoder)', expand=False)

    # Extract image dimensions
    df['width'] = df['filename'].str.extract(r'w(\d+)', expand=False).astype(float)
    df['height'] = df['filename'].str.extract(r'h(\d+)', expand=False).astype(float)

    # Extract channel info
    df['channels_in'] = df['filename'].str.extract(r'cin(\d+)', expand=False).astype(float)
    df['channels_out'] = df['filename'].str.extract(r'cout(\d+)', expand=False).astype(float)

    # Calculate total pixels
    df['total_pixels'] = df['width'] * df['height']

    # Extract short model name
    df['model_short'] = df['filename'].apply(lambda x: x.split('/')[-1].replace('.onnx', ''))

    return df


def plot_power_distribution(df, output_dir):
    """Plot power consumption distribution histogram."""
    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    plt.hist(df['avg_power'], bins=30, edgecolor='black', alpha=0.7, color='#2E86AB')
    plt.xlabel('Average Power (W)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Power Consumption Distribution', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)

    # Add statistics text
    stats_text = f"Mean: {df['avg_power'].mean():.3f} W\n"
    stats_text += f"Median: {df['avg_power'].median():.3f} W\n"
    stats_text += f"Std: {df['avg_power'].std():.3f} W"
    plt.text(0.98, 0.97, stats_text, transform=plt.gca().transAxes,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
             fontsize=10)

    plt.subplot(1, 2, 2)
    plt.hist(df['energy'], bins=30, edgecolor='black', alpha=0.7, color='#A23B72')
    plt.xlabel('Energy (Wh)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Energy Consumption Distribution', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)

    # Add statistics text
    stats_text = f"Mean: {df['energy'].mean():.6f} Wh\n"
    stats_text += f"Median: {df['energy'].median():.6f} Wh\n"
    stats_text += f"Total: {df['energy'].sum():.6f} Wh"
    plt.text(0.98, 0.97, stats_text, transform=plt.gca().transAxes,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
             fontsize=10)

    plt.tight_layout()
    output_file = output_dir / "01_power_energy_distribution.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_top_consumers(df, output_dir, top_n=15):
    """Plot top power consumers."""
    top_models = df.nlargest(top_n, 'avg_power')

    plt.figure(figsize=(14, 8))

    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(top_models)))
    bars = plt.barh(range(len(top_models)), top_models['avg_power'], color=colors, edgecolor='black')

    plt.yticks(range(len(top_models)), top_models['model_short'], fontsize=9)
    plt.xlabel('Average Power (W)', fontsize=12)
    plt.title(f'Top {top_n} Power Consumers', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='x')

    # Add value labels on bars
    for i, (bar, power) in enumerate(zip(bars, top_models['avg_power'])):
        plt.text(power + 0.05, i, f'{power:.3f} W',
                va='center', fontsize=8)

    plt.tight_layout()
    output_file = output_dir / "02_top_power_consumers.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_model_type_comparison(df, output_dir):
    """Compare power consumption across different model types."""
    if 'model_type' not in df.columns or df['model_type'].isna().all():
        print("  ⚠ Skipping model type comparison (no model type data)")
        return

    # Filter out rows with missing model_type
    df_filtered = df[df['model_type'].notna()].copy()

    if len(df_filtered) == 0:
        print("  ⚠ Skipping model type comparison (no valid data)")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Box plot
    model_types = df_filtered.groupby('model_type')['avg_power'].count()
    model_types = model_types[model_types >= 3].index  # Only types with 3+ samples

    if len(model_types) > 0:
        df_plot = df_filtered[df_filtered['model_type'].isin(model_types)]
        df_plot.boxplot(column='avg_power', by='model_type', ax=axes[0, 0])
        axes[0, 0].set_xlabel('Model Type', fontsize=11)
        axes[0, 0].set_ylabel('Average Power (W)', fontsize=11)
        axes[0, 0].set_title('Power by Model Type (Box Plot)', fontsize=12, fontweight='bold')
        axes[0, 0].get_figure().suptitle('')  # Remove default title
        axes[0, 0].grid(True, alpha=0.3)
    else:
        axes[0, 0].text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
        axes[0, 0].set_title('Power by Model Type')

    # 2. Bar plot - Average power by type
    avg_by_type = df_filtered.groupby('model_type')['avg_power'].mean().sort_values(ascending=False)
    colors = plt.cm.Set3(np.arange(len(avg_by_type)))
    avg_by_type.plot(kind='bar', ax=axes[0, 1], color=colors, edgecolor='black')
    axes[0, 1].set_xlabel('Model Type', fontsize=11)
    axes[0, 1].set_ylabel('Average Power (W)', fontsize=11)
    axes[0, 1].set_title('Average Power by Model Type', fontsize=12, fontweight='bold')
    axes[0, 1].tick_params(axis='x', rotation=45)
    axes[0, 1].grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, v in enumerate(avg_by_type):
        axes[0, 1].text(i, v + 0.05, f'{v:.3f}', ha='center', fontsize=9)

    # 3. Energy by type
    energy_by_type = df_filtered.groupby('model_type')['energy'].sum().sort_values(ascending=False)
    colors = plt.cm.Set2(np.arange(len(energy_by_type)))
    energy_by_type.plot(kind='bar', ax=axes[1, 0], color=colors, edgecolor='black')
    axes[1, 0].set_xlabel('Model Type', fontsize=11)
    axes[1, 0].set_ylabel('Total Energy (Wh)', fontsize=11)
    axes[1, 0].set_title('Total Energy by Model Type', fontsize=12, fontweight='bold')
    axes[1, 0].tick_params(axis='x', rotation=45)
    axes[1, 0].grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, v in enumerate(energy_by_type):
        axes[1, 0].text(i, v + 0.001, f'{v:.4f}', ha='center', fontsize=9)

    # 4. Count by type
    count_by_type = df_filtered['model_type'].value_counts().sort_values(ascending=False)
    colors = plt.cm.Pastel1(np.arange(len(count_by_type)))
    count_by_type.plot(kind='bar', ax=axes[1, 1], color=colors, edgecolor='black')
    axes[1, 1].set_xlabel('Model Type', fontsize=11)
    axes[1, 1].set_ylabel('Number of Models', fontsize=11)
    axes[1, 1].set_title('Model Count by Type', fontsize=12, fontweight='bold')
    axes[1, 1].tick_params(axis='x', rotation=45)
    axes[1, 1].grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, v in enumerate(count_by_type):
        axes[1, 1].text(i, v + 0.5, str(v), ha='center', fontsize=9)

    plt.tight_layout()
    output_file = output_dir / "03_model_type_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_performance_vs_power(df, output_dir):
    """Plot performance (inference time) vs power consumption."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. Inference time vs power
    scatter = axes[0].scatter(df['usperinf'] / 1000, df['avg_power'],
                             c=df['iterations'], cmap='viridis',
                             s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    axes[0].set_xlabel('Inference Time (ms)', fontsize=11)
    axes[0].set_ylabel('Average Power (W)', fontsize=11)
    axes[0].set_title('Power vs Inference Time', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[0], label='Iterations')

    # 2. Energy efficiency (energy per inference)
    df['energy_per_inference'] = (df['energy'] * 3600 * 1000) / df['iterations']  # mWh per inference

    scatter2 = axes[1].scatter(df['usperinf'] / 1000, df['energy_per_inference'],
                              c=df['avg_power'], cmap='plasma',
                              s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    axes[1].set_xlabel('Inference Time (ms)', fontsize=11)
    axes[1].set_ylabel('Energy per Inference (mWh)', fontsize=11)
    axes[1].set_title('Energy Efficiency', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=axes[1], label='Avg Power (W)')

    plt.tight_layout()
    output_file = output_dir / "04_performance_vs_power.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_voltage_current_analysis(df, output_dir, sample_size=10):
    """Analyze voltage and current variations."""
    # Select a sample of models
    sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Voltage distribution across all measurements
    all_voltages = []
    for volt_list in df['voltage_list']:
        all_voltages.extend(volt_list)

    axes[0, 0].hist(all_voltages, bins=50, edgecolor='black', alpha=0.7, color='#F18F01')
    axes[0, 0].set_xlabel('Voltage (mV)', fontsize=11)
    axes[0, 0].set_ylabel('Frequency', fontsize=11)
    axes[0, 0].set_title('Voltage Distribution (All Samples)', fontsize=12, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)

    stats_text = f"Mean: {np.mean(all_voltages):.1f} mV\n"
    stats_text += f"Std: {np.std(all_voltages):.1f} mV"
    axes[0, 0].text(0.98, 0.97, stats_text, transform=axes[0, 0].transAxes,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # 2. Current distribution across all measurements
    all_currents = []
    for curr_list in df['current_list']:
        all_currents.extend([abs(c) for c in curr_list])  # Take absolute values

    axes[0, 1].hist(all_currents, bins=50, edgecolor='black', alpha=0.7, color='#C73E1D')
    axes[0, 1].set_xlabel('Current (mA)', fontsize=11)
    axes[0, 1].set_ylabel('Frequency', fontsize=11)
    axes[0, 1].set_title('Current Distribution (All Samples)', fontsize=12, fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)

    stats_text = f"Mean: {np.mean(all_currents):.1f} mA\n"
    stats_text += f"Std: {np.std(all_currents):.1f} mA"
    axes[0, 1].text(0.98, 0.97, stats_text, transform=axes[0, 1].transAxes,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # 3. Sample voltage traces
    for idx, row in sample_df.iterrows():
        axes[1, 0].plot(row['voltage_list'], alpha=0.6, linewidth=1.5)

    axes[1, 0].set_xlabel('Sample #', fontsize=11)
    axes[1, 0].set_ylabel('Voltage (mV)', fontsize=11)
    axes[1, 0].set_title(f'Voltage Traces ({sample_size} models)', fontsize=12, fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Sample current traces
    for idx, row in sample_df.iterrows():
        axes[1, 1].plot([abs(c) for c in row['current_list']], alpha=0.6, linewidth=1.5)

    axes[1, 1].set_xlabel('Sample #', fontsize=11)
    axes[1, 1].set_ylabel('Current (mA)', fontsize=11)
    axes[1, 1].set_title(f'Current Traces ({sample_size} models)', fontsize=12, fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = output_dir / "05_voltage_current_analysis.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_resolution_impact(df, output_dir):
    """Analyze impact of image resolution on power consumption."""
    if 'total_pixels' not in df.columns or df['total_pixels'].isna().all():
        print("  ⚠ Skipping resolution impact (no resolution data)")
        return

    df_filtered = df[df['total_pixels'].notna()].copy()

    if len(df_filtered) == 0:
        print("  ⚠ Skipping resolution impact (no valid data)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. Power vs resolution
    scatter = axes[0].scatter(df_filtered['total_pixels'], df_filtered['avg_power'],
                             c=df_filtered['iterations'], cmap='coolwarm',
                             s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    axes[0].set_xlabel('Total Pixels (Width × Height)', fontsize=11)
    axes[0].set_ylabel('Average Power (W)', fontsize=11)
    axes[0].set_title('Power vs Image Resolution', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[0], label='Iterations')

    # Add trend line
    z = np.polyfit(df_filtered['total_pixels'].dropna(),
                   df_filtered[df_filtered['total_pixels'].notna()]['avg_power'], 1)
    p = np.poly1d(z)
    x_trend = np.linspace(df_filtered['total_pixels'].min(), df_filtered['total_pixels'].max(), 100)
    axes[0].plot(x_trend, p(x_trend), "r--", linewidth=2, alpha=0.8, label='Trend')
    axes[0].legend()

    # 2. Power by resolution groups
    df_filtered['resolution_group'] = pd.cut(df_filtered['total_pixels'],
                                             bins=5,
                                             labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'])

    resolution_power = df_filtered.groupby('resolution_group', observed=True)['avg_power'].mean()
    colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(resolution_power)))
    resolution_power.plot(kind='bar', ax=axes[1], color=colors, edgecolor='black')
    axes[1].set_xlabel('Resolution Group', fontsize=11)
    axes[1].set_ylabel('Average Power (W)', fontsize=11)
    axes[1].set_title('Power by Resolution Group', fontsize=12, fontweight='bold')
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, v in enumerate(resolution_power):
        axes[1].text(i, v + 0.05, f'{v:.3f}', ha='center', fontsize=9)

    plt.tight_layout()
    output_file = output_dir / "06_resolution_impact.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def plot_channel_impact(df, output_dir):
    """Analyze impact of channel count on power consumption."""
    if 'channels_in' not in df.columns or df['channels_in'].isna().all():
        print("  ⚠ Skipping channel impact (no channel data)")
        return

    df_filtered = df[(df['channels_in'].notna()) & (df['channels_out'].notna())].copy()

    if len(df_filtered) == 0:
        print("  ⚠ Skipping channel impact (no valid data)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. Power vs input channels
    scatter = axes[0].scatter(df_filtered['channels_in'], df_filtered['avg_power'],
                             c=df_filtered['channels_out'], cmap='plasma',
                             s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    axes[0].set_xlabel('Input Channels', fontsize=11)
    axes[0].set_ylabel('Average Power (W)', fontsize=11)
    axes[0].set_title('Power vs Input Channels', fontsize=12, fontweight='bold')
    axes[0].set_xscale('log')
    axes[0].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[0], label='Output Channels')

    # 2. Power vs output channels
    scatter2 = axes[1].scatter(df_filtered['channels_out'], df_filtered['avg_power'],
                              c=df_filtered['channels_in'], cmap='viridis',
                              s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    axes[1].set_xlabel('Output Channels', fontsize=11)
    axes[1].set_ylabel('Average Power (W)', fontsize=11)
    axes[1].set_title('Power vs Output Channels', fontsize=12, fontweight='bold')
    axes[1].set_xscale('log')
    axes[1].grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=axes[1], label='Input Channels')

    plt.tight_layout()
    output_file = output_dir / "07_channel_impact.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def create_summary_dashboard(df, output_dir):
    """Create a comprehensive summary dashboard."""
    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

    # Title
    fig.suptitle('ONNX Model Power Measurement Summary Dashboard',
                 fontsize=16, fontweight='bold', y=0.995)

    # 1. Key metrics (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.axis('off')

    metrics_text = f"""
    📊 Summary Statistics
    
    Total Models: {len(df)}
    Unique Models: {df['filename'].nunique()}
    
    Power Consumption:
      • Average: {df['avg_power'].mean():.3f} W
      • Min: {df['avg_power'].min():.3f} W
      • Max: {df['avg_power'].max():.3f} W
      • Std Dev: {df['avg_power'].std():.3f} W
    
    Energy:
      • Total: {df['energy'].sum():.6f} Wh
      • Average: {df['energy'].mean():.6f} Wh
    
    Performance:
      • Total Iterations: {df['iterations'].sum():,}
      • Avg Time/Inference: {df['usperinf'].mean()/1000:.2f} ms
    """

    ax1.text(0.1, 0.5, metrics_text, fontsize=10, verticalalignment='center',
            family='monospace', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))

    # 2. Power distribution (top middle)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(df['avg_power'], bins=25, edgecolor='black', alpha=0.7, color='#2E86AB')
    ax2.set_xlabel('Power (W)', fontsize=9)
    ax2.set_ylabel('Count', fontsize=9)
    ax2.set_title('Power Distribution', fontsize=10, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # 3. Energy distribution (top right)
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.hist(df['energy'], bins=25, edgecolor='black', alpha=0.7, color='#A23B72')
    ax3.set_xlabel('Energy (Wh)', fontsize=9)
    ax3.set_ylabel('Count', fontsize=9)
    ax3.set_title('Energy Distribution', fontsize=10, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # 4. Top 10 power consumers (middle left)
    ax4 = fig.add_subplot(gs[1, :])
    top10 = df.nlargest(10, 'avg_power')
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(top10)))
    bars = ax4.barh(range(len(top10)), top10['avg_power'], color=colors, edgecolor='black')
    ax4.set_yticks(range(len(top10)))
    ax4.set_yticklabels([name[:50] for name in top10['model_short']], fontsize=8)
    ax4.set_xlabel('Average Power (W)', fontsize=9)
    ax4.set_title('Top 10 Power Consumers', fontsize=10, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='x')

    for i, (bar, power) in enumerate(zip(bars, top10['avg_power'])):
        ax4.text(power + 0.05, i, f'{power:.3f}W', va='center', fontsize=7)

    # 5. Model type comparison (bottom left)
    ax5 = fig.add_subplot(gs[2, 0])
    if 'model_type' in df.columns and not df['model_type'].isna().all():
        type_avg = df.groupby('model_type')['avg_power'].mean().sort_values(ascending=False)
        colors = plt.cm.Set3(np.arange(len(type_avg)))
        type_avg.plot(kind='bar', ax=ax5, color=colors, edgecolor='black')
        ax5.set_xlabel('Model Type', fontsize=9)
        ax5.set_ylabel('Avg Power (W)', fontsize=9)
        ax5.set_title('Power by Model Type', fontsize=10, fontweight='bold')
        ax5.tick_params(axis='x', rotation=45, labelsize=8)
        ax5.grid(True, alpha=0.3, axis='y')
    else:
        ax5.text(0.5, 0.5, 'No model type data', ha='center', va='center')

    # 6. Performance vs Power (bottom middle)
    ax6 = fig.add_subplot(gs[2, 1])
    scatter = ax6.scatter(df['usperinf']/1000, df['avg_power'],
                         c=df['iterations'], cmap='viridis',
                         s=50, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax6.set_xlabel('Inference Time (ms)', fontsize=9)
    ax6.set_ylabel('Power (W)', fontsize=9)
    ax6.set_title('Power vs Performance', fontsize=10, fontweight='bold')
    ax6.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax6, label='Iterations')

    # 7. Efficiency ranking (bottom right)
    ax7 = fig.add_subplot(gs[2, 2])
    df_eff = df.copy()
    df_eff['energy_per_inf'] = (df_eff['energy'] * 3600 * 1000) / df_eff['iterations']
    most_efficient = df_eff.nsmallest(10, 'energy_per_inf')
    colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(most_efficient)))
    bars = ax7.barh(range(len(most_efficient)), most_efficient['energy_per_inf'],
                    color=colors, edgecolor='black')
    ax7.set_yticks(range(len(most_efficient)))
    ax7.set_yticklabels([name[:30] + '...' if len(name) > 30 else name
                         for name in most_efficient['model_short']], fontsize=7)
    ax7.set_xlabel('Energy/Inference (mWh)', fontsize=9)
    ax7.set_title('Most Energy Efficient', fontsize=10, fontweight='bold')
    ax7.grid(True, alpha=0.3, axis='x')

    output_file = output_dir / "00_summary_dashboard.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file.name}")
    plt.close()


def main():
    """Main execution function."""
    print("=" * 70)
    print("ONNX Measurement Visualization")
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

    # Extract model information
    print("\n🔍 Extracting model information...")
    df = extract_model_info(df)

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📊 Generating plots in: {output_dir}")

    # Set plot style
    try:
        plt.style.use(PLOT_STYLE)
    except:
        print(f"   ⚠ Style '{PLOT_STYLE}' not found, using default")

    # Generate all plots
    print("\n📈 Creating visualizations:")

    create_summary_dashboard(df, output_dir)
    plot_power_distribution(df, output_dir)
    plot_top_consumers(df, output_dir)
    plot_model_type_comparison(df, output_dir)
    plot_performance_vs_power(df, output_dir)
    plot_voltage_current_analysis(df, output_dir)
    plot_resolution_impact(df, output_dir)
    plot_channel_impact(df, output_dir)

    print("\n" + "=" * 70)
    print("✅ All visualizations generated successfully!")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print("=" * 70)


if __name__ == "__main__":
    main()

