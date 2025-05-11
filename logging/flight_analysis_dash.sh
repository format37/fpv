#!/bin/bash

# Get date parameter
DATE="${1}"
if [ -z "${DATE}" ]; then
    echo "Error: Date not provided."
    echo "Usage: $0 <date> [log_id]"
    echo "Example: $0 2025-04-05"
    exit 1
fi

# Set up directory paths based on date
CSV_DIR="CSV_OUTPUT/${DATE}"
EXTRACTED_DIR="EXTRACTED/${DATE}"

# Create directories if they don't exist
mkdir -p "${CSV_DIR}"
mkdir -p "${EXTRACTED_DIR}"

# Optional second parameter for specific log_id
LOG_ID="${2}"
if [ -z "${LOG_ID}" ]; then
    # If no specific log_id is provided, we'll look in the CSV directory
    # for available log files to get the log ID
    
    # Look for ATT csv files to determine available log IDs
    ATT_FILES=$(find "${CSV_DIR}" -name "*.ATT.csv" -type f 2>/dev/null | sort)
    if [ -z "${ATT_FILES}" ]; then
        echo "Error: No ATT.csv files found in ${CSV_DIR}"
        echo "Please ensure logs have been extracted and converted to CSV."
        exit 1
    fi
    
    # Use the first log ID found (or allow user to select if multiple)
    FIRST_ATT=$(echo "${ATT_FILES}" | head -n 1)
    LOG_ID=$(basename "${FIRST_ATT}" .ATT.csv)
    
    echo "Found log ID: ${LOG_ID}"
fi

# Construct the python command for the Dash app
PYTHON_CMD="python flight_analysis_dash.py"

# Add required arguments - check if they exist
ATT_CSV="${CSV_DIR}/${LOG_ID}.ATT.csv"
IMU_CSV="${CSV_DIR}/${LOG_ID}.IMU.csv"

if [ ! -f "${ATT_CSV}" ]; then
    echo "Error: Required file '${ATT_CSV}' not found."
    exit 1
fi
PYTHON_CMD+=" --att-csv ${ATT_CSV}"

if [ ! -f "${IMU_CSV}" ]; then
    echo "Error: Required file '${IMU_CSV}' not found."
    exit 1
fi
PYTHON_CMD+=" --imu-csv ${IMU_CSV}"

# Add optional arguments if files exist
[ -f "${CSV_DIR}/${LOG_ID}.RCIN.csv" ] && PYTHON_CMD+=" --rcin-csv ${CSV_DIR}/${LOG_ID}.RCIN.csv"
[ -f "${CSV_DIR}/${LOG_ID}.POS.csv" ]  && PYTHON_CMD+=" --pos-csv ${CSV_DIR}/${LOG_ID}.POS.csv"
[ -f "${CSV_DIR}/${LOG_ID}.GPS.csv" ]  && PYTHON_CMD+=" --gps-csv ${CSV_DIR}/${LOG_ID}.GPS.csv"
[ -f "${CSV_DIR}/${LOG_ID}.ARSP.csv" ] && PYTHON_CMD+=" --arsp-csv ${CSV_DIR}/${LOG_ID}.ARSP.csv"
[ -f "${CSV_DIR}/${LOG_ID}.XKF5.csv" ] && PYTHON_CMD+=" --xkf5-csv ${CSV_DIR}/${LOG_ID}.XKF5.csv"
[ -f "${CSV_DIR}/${LOG_ID}.RFND.csv" ] && PYTHON_CMD+=" --rfnd-csv ${CSV_DIR}/${LOG_ID}.RFND.csv"
[ -f "${CSV_DIR}/${LOG_ID}.BARO.csv" ] && PYTHON_CMD+=" --baro-csv ${CSV_DIR}/${LOG_ID}.BARO.csv"
[ -f "${CSV_DIR}/${LOG_ID}.TERR.csv" ] && PYTHON_CMD+=" --terr-csv ${CSV_DIR}/${LOG_ID}.TERR.csv"
[ -f "${CSV_DIR}/${LOG_ID}.BAT.csv" ] && PYTHON_CMD+=" --bat-csv ${CSV_DIR}/${LOG_ID}.BAT.csv"
[ -f "${CSV_DIR}/${LOG_ID}.PIDP.csv" ] && PYTHON_CMD+=" --pidp-csv ${CSV_DIR}/${LOG_ID}.PIDP.csv"
[ -f "${CSV_DIR}/${LOG_ID}.PIDR.csv" ] && PYTHON_CMD+=" --pidr-csv ${CSV_DIR}/${LOG_ID}.PIDR.csv"
[ -f "${CSV_DIR}/${LOG_ID}.MSG.csv" ] && PYTHON_CMD+=" --msg-csv ${CSV_DIR}/${LOG_ID}.MSG.csv"

# Echo the command being run
echo "Running analysis with command:"
echo "${PYTHON_CMD}"
echo # Newline

# Execute the command
# Use exec to replace the shell process with the Python process
# This ensures CTRL+C correctly stops the Python server
exec ${PYTHON_CMD}

# This part will only be reached if exec fails
echo # Newline
echo "Failed to execute the Python script."
exit 1