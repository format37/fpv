from pymavlink import mavutil
import csv
import time

# Connect to the autopilot
connection_string = 'COM5'  # Adjust for your system (e.g., '/dev/ttyACM0' on Linux, 'udp:127.0.0.1:14550' for telemetry)
try:
    vehicle = mavutil.mavlink_connection(connection_string)
    vehicle.wait_heartbeat()
    print("Connected to vehicle")
except Exception as e:
    print(f"Failed to connect: {e}")
    exit(1)

# Request all parameters
vehicle.mav.param_request_list_send(vehicle.target_system, vehicle.target_component)
parameters = []
start_time = time.time()
timeout = 10  # seconds

while time.time() - start_time < timeout:
    try:
        message = vehicle.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if message:
            param_id = message.param_id  # No .decode() needed; it's already a string
            param_value = message.param_value
            param_type = message.param_type
            parameters.append({
                'param_id': param_id,
                'value': param_value,
                'type': param_type
            })
            print(f"Received: {param_id} = {param_value}")
    except Exception as e:
        print(f"Error receiving parameter: {e}")
        break

# Save all parameters to CSV
try:
    with open('all_parameters.csv', 'w', newline='') as csvfile:
        fieldnames = ['param_id', 'value', 'type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for param in parameters:
            writer.writerow(param)
    print("Parameters saved to all_parameters.csv")
except Exception as e:
    print(f"Error saving CSV: {e}")

# Close the connection
vehicle.close()