#!/bin/bash

CSV_DIR="CSV_OUTPUT"

# Find the only ATT and IMU CSVs
ATT_CSV=$(find "$CSV_DIR" -maxdepth 1 -name "*.ATT.csv" | head -n 1)
IMU_CSV=$(find "$CSV_DIR" -maxdepth 1 -name "*.IMU.csv" | head -n 1)

if [ -z "$ATT_CSV" ] || [ -z "$IMU_CSV" ]; then
    echo "Error: Required ATT or IMU CSV not found in $CSV_DIR"
    exit 1
fi

PYTHON_CMD="python flight_analysis_dash.py --att-csv $ATT_CSV --imu-csv $IMU_CSV"

# Add optional files if present
for TYPE in RCIN POS GPS ARSP XKF5 RFND BARO TERR BAT PIDP PIDR MODE MSG OF; do
    FILE=$(find "$CSV_DIR" -maxdepth 1 -name "*.$TYPE.csv" | head -n 1)
    if [ -n "$FILE" ]; then
        ARG_NAME=$(echo "$TYPE" | tr '[:upper:]' '[:lower:]')
        PYTHON_CMD+=" --${ARG_NAME}-csv $FILE"
    fi
done

echo "Running: $PYTHON_CMD"
exec $PYTHON_CMD 