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
    
    # Look for MAG csv files to determine available log IDs
    MAG_FILES=$(find "${CSV_DIR}" -name "*.MAG.csv" -type f 2>/dev/null | sort)
    if [ -z "${MAG_FILES}" ]; then
        # If no MAG files, try ATT files as alternative
        ATT_FILES=$(find "${CSV_DIR}" -name "*.ATT.csv" -type f 2>/dev/null | sort)
        if [ -z "${ATT_FILES}" ]; then
            echo "Error: No MAG.csv or ATT.csv files found in ${CSV_DIR}"
            echo "Please ensure logs have been extracted and converted to CSV."
            exit 1
        fi
        
        FIRST_ATT=$(echo "${ATT_FILES}" | head -n 1)
        LOG_ID=$(basename "${FIRST_ATT}" .ATT.csv)
    else
        FIRST_MAG=$(echo "${MAG_FILES}" | head -n 1)
        LOG_ID=$(basename "${FIRST_MAG}" .MAG.csv)
    fi
    
    echo "Found log ID: ${LOG_ID}"
fi

# Construct the python command for the Dash app
PYTHON_CMD="python mag_analysis_dash.py"

# Add required arguments - check if they exist
MAG_CSV="${CSV_DIR}/${LOG_ID}.MAG.csv"
ATT_CSV="${CSV_DIR}/${LOG_ID}.ATT.csv"

# Require at least one of MAG or ATT to proceed
if [ ! -f "${MAG_CSV}" ] && [ ! -f "${ATT_CSV}" ]; then
    echo "Error: Neither MAG nor ATT CSV file found for log ID ${LOG_ID}."
    echo "At least one of these files is required:"
    echo "  - ${MAG_CSV}"
    echo "  - ${ATT_CSV}"
    exit 1
fi

# Add required files if they exist
[ -f "${MAG_CSV}" ] && PYTHON_CMD+=" --mag-csv ${MAG_CSV}"
[ -f "${ATT_CSV}" ] && PYTHON_CMD+=" --att-csv ${ATT_CSV}"

# Add optional arguments if files exist
# Add MAG2, MAG3 if they exist (multiple compasses)
[ -f "${CSV_DIR}/${LOG_ID}.MAG2.csv" ] && PYTHON_CMD+=" --mag2-csv ${CSV_DIR}/${LOG_ID}.MAG2.csv"
[ -f "${CSV_DIR}/${LOG_ID}.MAG3.csv" ] && PYTHON_CMD+=" --mag3-csv ${CSV_DIR}/${LOG_ID}.MAG3.csv"

# Add EKF data if it exists
[ -f "${CSV_DIR}/${LOG_ID}.XKF3.csv" ] && PYTHON_CMD+=" --xkf3-csv ${CSV_DIR}/${LOG_ID}.XKF3.csv"
[ -f "${CSV_DIR}/${LOG_ID}.XKF4.csv" ] && PYTHON_CMD+=" --xkf4-csv ${CSV_DIR}/${LOG_ID}.XKF4.csv"

# Add GPS data if it exists (for comparison with magnetic heading)
[ -f "${CSV_DIR}/${LOG_ID}.GPS.csv" ] && PYTHON_CMD+=" --gps-csv ${CSV_DIR}/${LOG_ID}.GPS.csv"

# Echo the command being run
echo "Running magnetometer analysis with command:"
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