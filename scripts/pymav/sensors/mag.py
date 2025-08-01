import time
import argparse
from pymavlink import mavutil
from tqdm import tqdm
import math

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

def calculate_heading(mag_x, mag_y):
    """Calculate magnetic heading from X and Y magnetometer readings"""
    heading_rad = math.atan2(mag_y, mag_x)
    heading_deg = math.degrees(heading_rad)
    # Normalize to 0-360 degrees
    if heading_deg < 0:
        heading_deg += 360
    return heading_deg

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Read magnetometer data from MAVLink connection')
    parser.add_argument('--port', '-p', default='/dev/ttyS0', 
                       help='Serial port to connect to (default: /dev/ttyS0)')
    parser.add_argument('--baud', '-b', type=int, default=1500000,
                       help='Baud rate for serial connection (default: 1500000)')
    args = parser.parse_args()

    try:
        # Establish connection
        vehicle = connect_to_vehicle(args.port, args.baud)

        # Request data streams
        request_data_streams(vehicle)

        print("Reading magnetometer data... (Press Ctrl+C to stop)")

        # Initialize tqdm bars for magnetometer readings
        mag_min, mag_max = -3000, 3000  # mGauss (typical range for magnetometer)
        heading_min, heading_max = 0, 360  # degrees
        mag_range = mag_max - mag_min
        heading_range = heading_max - heading_min
        
        magx_bar = tqdm(total=mag_range, desc='Mag X (mGauss)', position=0, leave=True, 
                       bar_format='{l_bar}{bar}| {n:.1f}/{total} mGauss', initial=-mag_min)
        magy_bar = tqdm(total=mag_range, desc='Mag Y (mGauss)', position=1, leave=True, 
                       bar_format='{l_bar}{bar}| {n:.1f}/{total} mGauss', initial=-mag_min)
        magz_bar = tqdm(total=mag_range, desc='Mag Z (mGauss)', position=2, leave=True, 
                       bar_format='{l_bar}{bar}| {n:.1f}/{total} mGauss', initial=-mag_min)
        heading_bar = tqdm(total=heading_range, desc='Heading (deg)', position=3, leave=True, 
                          bar_format='{l_bar}{bar}| {n:.1f}° / {total}°', initial=0)

        # Store last values to avoid unnecessary tqdm updates
        last_magx = None
        last_magy = None
        last_magz = None
        last_heading = None

        while True:
            # Wait for a MAVLink message
            msg = vehicle.recv_match(blocking=True)

            if msg is None:
                continue

            # Handle RAW_IMU message (contains magnetometer data)
            if msg.get_type() == 'RAW_IMU':
                # Extract magnetometer values (in mGauss)
                mag_x = msg.xmag
                mag_y = msg.ymag
                mag_z = msg.zmag
                
                # Calculate magnetic heading
                heading = calculate_heading(mag_x, mag_y)

                # Clamp and update tqdm for magnetometer readings
                if last_magx != mag_x:
                    magx_bar.n = min(max(mag_x, mag_min), mag_max) - mag_min
                    magx_bar.refresh()
                    last_magx = mag_x
                    
                if last_magy != mag_y:
                    magy_bar.n = min(max(mag_y, mag_min), mag_max) - mag_min
                    magy_bar.refresh()
                    last_magy = mag_y
                    
                if last_magz != mag_z:
                    magz_bar.n = min(max(mag_z, mag_min), mag_max) - mag_min
                    magz_bar.refresh()
                    last_magz = mag_z

                # Update heading bar
                if last_heading != heading:
                    heading_bar.n = heading
                    heading_bar.refresh()
                    last_heading = heading

            # Also handle SCALED_IMU message if available (alternative magnetometer source)
            elif msg.get_type() == 'SCALED_IMU':
                # Extract magnetometer values (in mGauss)
                mag_x = msg.xmag
                mag_y = msg.ymag
                mag_z = msg.zmag
                
                # Calculate magnetic heading
                heading = calculate_heading(mag_x, mag_y)

                # Clamp and update tqdm for magnetometer readings
                if last_magx != mag_x:
                    magx_bar.n = min(max(mag_x, mag_min), mag_max) - mag_min
                    magx_bar.refresh()
                    last_magx = mag_x
                    
                if last_magy != mag_y:
                    magy_bar.n = min(max(mag_y, mag_min), mag_max) - mag_min
                    magy_bar.refresh()
                    last_magy = mag_y
                    
                if last_magz != mag_z:
                    magz_bar.n = min(max(mag_z, mag_min), mag_max) - mag_min
                    magz_bar.refresh()
                    last_magz = mag_z

                # Update heading bar
                if last_heading != heading:
                    heading_bar.n = heading
                    heading_bar.refresh()
                    last_heading = heading

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
