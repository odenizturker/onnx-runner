#!/bin/bash

# Parse battery measurements and generate human-readable reports
# Extracts voltage and current data from batterystats files

set -euo pipefail

# Configuration
MEASUREMENTS_DIR="./measurements"
REPORTS_DIR="./reports"

# Logging helper
log() {
    echo "[$(date '+%H:%M:%S')] $1" >&2
}

# Extract voltage and current values from a batterystats file
parse_batterystats() {
    local file="$1"
    local model_name=$(basename "$file" _batterystats.txt)

    # Extract voltage and current separately, then pair them
    # Voltage may not change often, so we track the last known value

    # First, extract all lines with current readings
    local temp_file=$(mktemp)
    grep 'current=' "$file" > "$temp_file" || {
        log "  ✗ $model_name: No current data found"
        rm -f "$temp_file"
        return 1
    }

    # Process each line, extracting voltage (if present) and current
    local measurements=""
    local last_volt=""

    while IFS= read -r line; do
        # Extract voltage if present in this line
        if [[ "$line" =~ volt=([0-9]+) ]]; then
            last_volt="${BASH_REMATCH[1]}"
        fi

        # Extract current (always present in filtered lines)
        if [[ "$line" =~ current=(-?[0-9]+) ]]; then
            local curr="${BASH_REMATCH[1]}"
            # Only add measurement if we have a voltage reading
            if [ -n "$last_volt" ]; then
                measurements="${measurements}${last_volt} ${curr}"$'\n'
            fi
        fi
    done < "$temp_file"

    rm -f "$temp_file"

    if [ -z "$measurements" ]; then
        log "  ✗ $model_name: No paired voltage/current data found"
        return 1
    fi

    # Calculate statistics from paired measurements
    local stats=$(echo "$measurements" | awk '
        BEGIN {
            volt_sum=0; curr_sum=0
            volt_min=999999; volt_max=0
            curr_min=0; curr_max=-999999
            count=0
        }
        NF == 2 {
            volt = $1
            curr = $2

            volt_sum += volt
            curr_sum += curr
            count++

            if (volt < volt_min) volt_min = volt
            if (volt > volt_max) volt_max = volt
            if (curr < curr_min) curr_min = curr
            if (curr > curr_max) curr_max = curr
        }
        END {
            if (count > 0) {
                volt_avg = volt_sum / count
                curr_avg = curr_sum / count

                # Convert current to positive (discharge)
                # When negating, min and max swap places
                curr_avg = -curr_avg
                curr_min_pos = -curr_max
                curr_max_pos = -curr_min

                printf "%.2f %.0f %.0f %.2f %.0f %.0f %d",
                    volt_avg, volt_min, volt_max,
                    curr_avg, curr_max_pos, curr_min_pos, count
            }
        }
    ')

    # Parse stats
    read volt_avg volt_min volt_max curr_avg curr_max curr_min count <<< "$stats"

    # Calculate average power (P = V * I, convert mV to V)
    local power_avg=$(echo "$volt_avg $curr_avg" | awk '{printf "%.3f", ($1 * $2) / 1000000}')

    log "  ✓ $model_name: ${volt_avg} mV | ${curr_avg} mA | ${power_avg} W (${count} samples)"
    local report_file="$REPORTS_DIR/${model_name}_report.txt"
    cat > "$report_file" << EOF
===============================================
Power Measurement Report
===============================================
Model: $model_name
Generated: $(date '+%Y-%m-%d %H:%M:%S')
Measurement Samples: ${count}

VOLTAGE STATISTICS (mV)
-----------------------------------------------
Average:        ${volt_avg} mV
Minimum:        ${volt_min} mV
Maximum:        ${volt_max} mV

CURRENT STATISTICS (mA - discharge)
-----------------------------------------------
Average:        ${curr_avg} mA
Maximum:        ${curr_max} mA
Minimum:        ${curr_min} mA

POWER CONSUMPTION
-----------------------------------------------
Average Power:  ${power_avg} W

Note: Each sample represents a paired voltage/current
      measurement from Android batterystats (~13s interval)
===============================================
EOF

    return 0
}

# Main execution
main() {
    log "Starting measurement parsing"

    # Create reports directory
    mkdir -p "$REPORTS_DIR"

    # Check if measurements directory exists
    if [ ! -d "$MEASUREMENTS_DIR" ]; then
        log "ERROR: $MEASUREMENTS_DIR directory not found"
        exit 1
    fi

    # Check if there are any batterystats files
    local file_count=$(find "$MEASUREMENTS_DIR" -name "*_batterystats.txt" | wc -l | tr -d ' ')
    if [ "$file_count" -eq 0 ]; then
        log "ERROR: No batterystats files found in $MEASUREMENTS_DIR"
        exit 1
    fi

    log "Found $file_count measurement file(s)"

    # Process each batterystats file
    local success=0
    for file in "$MEASUREMENTS_DIR"/*_batterystats.txt; do
        if [ -f "$file" ]; then
            if parse_batterystats "$file"; then
                success=$((success + 1))
            fi
        fi
    done

    log "Done! Processed $success file(s). Reports saved in: $REPORTS_DIR/"
}

# Run main
main

