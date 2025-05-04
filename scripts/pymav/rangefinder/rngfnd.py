import time
from pymavlink import mavutil
from tqdm import tqdm

def connect_to_vehicle(port='COM4', baud=115200):
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
        vehicle = connect_to_vehicle('COM4', 1500000)

        # Request data streams
        request_data_streams(vehicle)

        print("Reading rangefinder and optical flow data... (Press Ctrl+C to stop)")

        # Initialize tqdm bars with correct ranges
        rngfnd_bar = tqdm(total=2, desc='Rangefinder (m)', position=0, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} m')
        flowx_bar = tqdm(total=10, desc='FlowX (px)', position=1, leave=True, bar_format='{l_bar}{bar}| {n}/{total} px')
        flowy_bar = tqdm(total=10, desc='FlowY (px)', position=2, leave=True, bar_format='{l_bar}{bar}| {n}/{total} px')

        # Store last values to avoid unnecessary tqdm updates
        last_distance = None
        last_flowx = None
        last_flowy = None

        while True:
            # Wait for a MAVLink message
            msg = vehicle.recv_match(blocking=True)

            if msg is None:
                continue

            # Handle RANGEFINDER message
            if msg.get_type() == 'RANGEFINDER':
                distance = msg.distance  # Distance in meters
                # Clamp and update tqdm
                if last_distance != distance:
                    rngfnd_bar.n = min(max(distance, 0), rngfnd_bar.total)
                    rngfnd_bar.refresh()
                    last_distance = distance

            # Handle OPTICAL_FLOW message
            if msg.get_type() == 'OPTICAL_FLOW':
                flow_x = msg.flow_comp_m_x  # Flow in x-axis (pixels)
                flow_y = msg.flow_comp_m_y  # Flow in y-axis (pixels)
                # Clamp and update tqdm
                if last_flowx != flow_x:
                    flowx_bar.n = min(max(flow_x, -flowx_bar.total), flowx_bar.total)
                    flowx_bar.refresh()
                    last_flowx = flow_x
                if last_flowy != flow_y:
                    flowy_bar.n = min(max(flow_y, -flowy_bar.total), flowy_bar.total)
                    flowy_bar.refresh()
                    last_flowy = flow_y

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