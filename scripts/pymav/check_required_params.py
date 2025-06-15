import csv
import time
import os
from pymavlink import mavutil

# ANSI color codes
GREEN = '\033[92m'
ORANGE = '\033[93m'
RESET = '\033[0m'

# Path to required.csv
base_dir = os.path.dirname(__file__)
required_csv = os.path.join(base_dir, 'params', 'required.csv')

# Read required parameters
required_params = {}
with open(required_csv, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        param_id = row['param_id']
        value = row['value']
        comment = row.get('comment', '')
        required_params[param_id] = {'value': value, 'comment': comment}

# Connect to the autopilot
connection_string = '/dev/ttyACM0'  # Default: MatekH743-bdshot
try:
    vehicle = mavutil.mavlink_connection(connection_string)
    vehicle.wait_heartbeat()
    print("Connected to vehicle")
except Exception as e:
    print(f"Failed to connect: {e}")
    exit(1)

# Request all parameters
vehicle.mav.param_request_list_send(vehicle.target_system, vehicle.target_component)
params = {}
start_time = time.time()
timeout = 10  # seconds

while time.time() - start_time < timeout:
    try:
        message = vehicle.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if message:
            param_id = message.param_id
            param_value = message.param_value
            params[param_id] = param_value
    except Exception as e:
        break

# Compare and print
for param_id, req in required_params.items():
    required_value = req['value']
    comment = req['comment']
    actual_value = params.get(param_id)
    if actual_value is None:
        # Not found in ArduPilot, skip or print as needed
        continue
    # Compare as float for robustness
    try:
        required_value_f = float(required_value)
        actual_value_f = float(actual_value)
    except Exception:
        required_value_f = required_value
        actual_value_f = actual_value
    if required_value_f == actual_value_f:
        color = GREEN
        status = 'OK'
    else:
        color = ORANGE
        status = 'MISMATCH'
    print(f"{color}{param_id}: required={required_value} actual={actual_value} [{status}] {comment}{RESET}")

vehicle.close() 