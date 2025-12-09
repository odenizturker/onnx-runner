#!/usr/bin/env bash
# Generate comprehensive power measurement reports
# Combines performance metrics (JSON) and battery statistics (batterystats)
# Output format: CSV with all voltage/current samples + aggregated metrics

set -euo pipefail

MEASUREMENTS_DIR="./measurements"
REPORTS_DIR="./reports"

log() {
    echo "[$(date '+%H:%M:%S')] $1" >&2
}

# Parse CSV file and extract performance metrics
parse_performance_csv() {
    local csv_file="$1"

    if [ ! -f "$csv_file" ]; then
        return 1
    fi

    # Read the CSV file (skip header, read data row)
    local data_row=$(tail -n +2 "$csv_file" | head -1)

    if [ -z "$data_row" ]; then
        return 1
    fi

    # Parse CSV values (format: model,timestamp,iterations,elapsed_ms,us_per_inf,total_time,warmup_iter,warmup_ms)
    IFS=',' read -r model timestamp iterations elapsed_ms us_per_inference total_time_sec warmup_iterations warmup_elapsed_ms <<< "$data_row"

    # Remove any quotes
    model=$(echo "$model" | tr -d '"')
    timestamp=$(echo "$timestamp" | tr -d '"')

    echo "${model}|${timestamp}|${iterations}|${us_per_inference}|${total_time_sec}"
}

# Extract voltage and current measurements from batterystats
parse_batterystats_samples() {
    local file="$1"
    local temp_file=$(mktemp)

    grep 'current=' "$file" > "$temp_file" 2>/dev/null || {
        rm -f "$temp_file"
        return 1
    }

    local measurements=""
    local last_volt=""
    local voltage_list=""
    local current_list=""

    while IFS= read -r line; do
        if [[ "$line" =~ volt=([0-9]+) ]]; then
            last_volt="${BASH_REMATCH[1]}"
        fi

        if [[ "$line" =~ current=(-?[0-9]+) ]]; then
            local curr="${BASH_REMATCH[1]}"
            if [ -n "$last_volt" ]; then
                # Add to lists
                if [ -z "$voltage_list" ]; then
                    voltage_list="$last_volt"
                    current_list="$curr"
                else
                    voltage_list="${voltage_list},${last_volt}"
                    current_list="${current_list},${curr}"
                fi
                measurements="${measurements}${last_volt} ${curr}"$'\n'
            fi
        fi
    done < "$temp_file"

    rm -f "$temp_file"

    if [ -z "$measurements" ]; then
        return 1
    fi

    # Calculate average power
    local avg_power=$(echo "$measurements" | awk '
        BEGIN { power_sum=0; count=0 }
        NF == 2 {
            volt = $1
            curr = $2
            # Current from batterystats is negative for discharge
            # Take absolute value: P = V * |I|
            # P in Watts = (V in mV) * (|I| in mA) / 1,000,000
            if (curr < 0) {
                curr = -curr
            }
            power_w = (volt * curr) / 1000000.0
            power_sum += power_w
            count++
        }
        END {
            if (count > 0) {
                printf "%.6f", power_sum / count
            } else {
                printf "0"
            }
        }
    ')

    # Calculate energy (Power * Time)
    local total_time_sec="$2"
    local energy_wh="0"
    if [ -n "$total_time_sec" ] && [ "$total_time_sec" != "0" ]; then
        energy_wh=$(echo "$avg_power $total_time_sec" | awk '{printf "%.6f", $1 * $2 / 3600}')
    fi

    echo "${voltage_list}|${current_list}|${avg_power}|${energy_wh}"
}

# Generate comprehensive report for a measurement
generate_report() {
    local perf_file="$1"

    # Extract base name (remove _performance.csv suffix)
    local base_name=$(basename "$perf_file" _performance.csv)

    # Find corresponding batterystats file
    # The performance file has format: model_TIMESTAMP_performance.csv
    # We need to find batterystats that matches the model part

    # Extract model name and timestamp from performance filename
    # Format: zi_t_model_20251209_143052_performance.csv
    local model_part=$(echo "$base_name" | sed 's/_[0-9]\{8\}_[0-9]\{6\}$//')
    local timestamp_part=$(echo "$base_name" | grep -o '[0-9]\{8\}_[0-9]\{6\}$' || echo "")

    # Find batterystats file - it should have the same model part but different or no timestamp
    local batterystats_file=""

    # Try exact match first with run suffix
    for stats_pattern in "${MEASUREMENTS_DIR}/${model_part}_run"*"_batterystats.txt" \
                         "${MEASUREMENTS_DIR}/${model_part}_batterystats.txt"; do
        if [ -f "$stats_pattern" ]; then
            batterystats_file="$stats_pattern"
            break
        fi
    done

    if [ -z "$batterystats_file" ] || [ ! -f "$batterystats_file" ]; then
        log "  ⚠ No matching batterystats found for: $base_name"
        return 1
    fi

    # Parse performance metrics from CSV
    local perf_data=$(parse_performance_csv "$perf_file")
    if [ -z "$perf_data" ]; then
        log "  ✗ Failed to parse: $perf_file"
        return 1
    fi

    IFS='|' read -r model timestamp iterations us_per_inf total_time_sec <<< "$perf_data"

    # Parse battery statistics
    local battery_data=$(parse_batterystats_samples "$batterystats_file" "$total_time_sec")
    if [ -z "$battery_data" ]; then
        log "  ✗ No battery data for: $base_name"
        return 1
    fi

    IFS='|' read -r voltage_list current_list avg_power energy <<< "$battery_data"

    # Create identifier: model_name + date_time
    local identifier="${model}_${timestamp}"

    # For us_per_download, we'll set it to 0 as there's no download in the current implementation
    local us_per_download="0"

    log "  ✓ Processed: $identifier"

    # Output CSV row
    echo "\"${identifier}\",\"${model}\",\"${timestamp}\",\"${voltage_list}\",\"${current_list}\",${avg_power},${energy},${iterations},${us_per_inf},${us_per_download},${total_time_sec}"
}

# Main execution
main() {
    log "Starting comprehensive report generation"

    mkdir -p "$REPORTS_DIR"

    if [ ! -d "$MEASUREMENTS_DIR" ]; then
        log "ERROR: $MEASUREMENTS_DIR directory not found"
        exit 1
    fi

    # Count performance CSV files
    local file_count=$(find "$MEASUREMENTS_DIR" -name "*_performance.csv" | wc -l | tr -d ' ')

    if [ "$file_count" -eq 0 ]; then
        log "ERROR: No performance CSV files found in $MEASUREMENTS_DIR"
        log "       Make sure you've run measurements with the updated binary"
        exit 1
    fi

    log "Found $file_count performance file(s)"

    # Create CSV report
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local csv_file="$REPORTS_DIR/power_report_${timestamp}.csv"

    # Write CSV header
    cat > "$csv_file" << EOF
identifier,model,timestamp,voltage_list_mV,current_list_mA,avg_power_W,energy_Wh,iterations,us_per_inference,us_per_download,total_time_sec
EOF

    # Process each performance CSV file
    local success=0
    for perf_file in "$MEASUREMENTS_DIR"/*_performance.csv; do
        if [ -f "$perf_file" ]; then
            if report_line=$(generate_report "$perf_file" 2>/dev/null); then
                echo "$report_line" >> "$csv_file"
                success=$((success + 1))
            fi
        fi
    done

    log "============================================================"
    log "Report generation complete!"
    log "Processed: $success/$file_count measurements"
    log "CSV report: $csv_file"
    log "============================================================"

    # Also generate human-readable summary
    local summary_file="$REPORTS_DIR/summary_${timestamp}.txt"
    cat > "$summary_file" << EOF
===============================================
Power Measurement Summary Report
===============================================
Generated: $(date '+%Y-%m-%d %H:%M:%S')
Total Measurements: $success

Detailed data available in: $csv_file

Column Descriptions:
--------------------
- identifier:       Model name + timestamp (unique ID)
- model:           ONNX model filename
- timestamp:       Measurement timestamp (YYYYMMDD_HHMMSS)
- voltage_list_mV: All voltage samples (mV), comma-separated
- current_list_mA: All current samples (mA), comma-separated
- avg_power_W:     Average power consumption (Watts)
- energy_Wh:       Total energy consumed (Watt-hours)
- iterations:      Number of inferences executed
- us_per_inference: Microseconds per inference
- us_per_download: Microseconds per download (0 if N/A)
- total_time_sec:  Total measurement time (seconds)

Usage Example:
--------------
# View in spreadsheet
open "$csv_file"

# Quick analysis with awk
awk -F',' 'NR>1 {print \$2, \$6}' "$csv_file" | sort -k2 -n

# Find highest power consumption
awk -F',' 'NR>1 {print \$2, \$6}' "$csv_file" | sort -k2 -rn | head -5
===============================================
EOF

    log "Summary: $summary_file"

    # Display quick summary
    if [ "$success" -gt 0 ]; then
        log ""
        log "Top 5 models by power consumption:"
        awk -F',' 'NR>1 {print $2, $6}' "$csv_file" | \
            sort -t' ' -k2 -rn | \
            head -5 | \
            awk '{printf "  %.3f W - %s\n", $2, $1}' >&2
    fi
}

main

