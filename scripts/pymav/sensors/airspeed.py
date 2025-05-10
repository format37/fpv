import time
from pymavlink import mavutil
from tqdm import tqdm

def connect_to_vehicle(port='/dev/ttyS0', baud=1500000):
    print(f"Connecting to vehicle on {port} at {baud} baud...")
    connection = mavutil.mavlink_connection(port, baud=baud)
    connection.wait_heartbeat()
    print("Heartbeat received. Connection established.")
    return connection

def request_data_streams(connection):
    # Request DATA_STREAM_ALL at 10 Hz
    connection.mav.request_data_stream_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        10,  # Rate in Hz
        1    # Start streaming
    )

def main():
    try:
        # Establish connection
        vehicle = connect_to_vehicle('/dev/ttyS0', 1500000)

        # Request data streams
        request_data_streams(vehicle)

        print("Reading airspeed data... (Press Ctrl+C to stop)")

        # Initialize tqdm bar for airspeed (assuming a max of 50 m/s for display)
        airspeed_bar = tqdm(total=50, desc='Airspeed (m/s)', position=0, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} m/s')

        # Store last airspeed to avoid unnecessary tqdm updates
        last_airspeed = None

        while True:
            # Wait for a MAVLink message
            msg = vehicle.recv_match(blocking=True)

            if msg is None:
                continue

            # Handle VFR_HUD message for airspeed
            if msg.get_type() == 'VFR_HUD':
                airspeed = msg.airspeed  # Airspeed in meters per second
                # Clamp and update tqdm
                if last_airspeed != airspeed:
                    airspeed_bar.n = min(max(airspeed, 0), airspeed_bar.total)
                    airspeed_bar.refresh()
                    last_airspeed = airspeed

    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Closing connection...")
        vehicle.close()
        print("Connection closed.")

    except Exception as e:
        print(f"An error occurred: {e}")
        vehicle.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()