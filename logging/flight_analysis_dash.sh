#!/bin/bash

# Define the log number or identifier
LOG_ID="00000053"
CSV_DIR="CSV_OUTPUT"
# REPORT_DIR="reports" # No longer needed for Dash app output file
# REPORT_FILE="${REPORT_DIR}/${LOG_ID}.flight_analysis.html" # No longer needed

# Ensure CSV directory exists (optional check)
if [ ! -d "${CSV_DIR}" ]; then
    echo "Error: CSV directory '${CSV_DIR}' not found."
    exit 1
fi

# Construct the python command for the Dash app
# Use the new script name: flight_analysis_dash.py
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

# REMOVED: Output file argument is not used by the Dash app
# PYTHON_CMD+=" -o ${REPORT_FILE}"

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

# Add optional host/port arguments if needed (example)
# PYTHON_CMD+=" --port 8051"

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