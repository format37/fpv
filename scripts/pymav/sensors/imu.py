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

        print("Reading IMU data... (Press Ctrl+C to stop)")

        # Initialize tqdm bars for accelerometer and gyroscope (assuming reasonable ranges)
        accelx_bar = tqdm(total=20, desc='Accel X (m/s²)', position=0, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} m/s²')
        accely_bar = tqdm(total=20, desc='Accel Y (m/s²)', position=1, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} m/s²')
        accelz_bar = tqdm(total=20, desc='Accel Z (m/s²)', position=2, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} m/s²')
        gyrox_bar = tqdm(total=5, desc='Gyro X (rad/s)', position=3, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} rad/s')
        gyroy_bar = tqdm(total=5, desc='Gyro Y (rad/s)', position=4, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} rad/s')
        gyroz_bar = tqdm(total=5, desc='Gyro Z (rad/s)', position=5, leave=True, bar_format='{l_bar}{bar}| {n:.2f}/{total} rad/s')

        # Store last values to avoid unnecessary tqdm updates
        last_accelx = None
        last_accely = None
        last_accelz = None
        last_gyrox = None
        last_gyroy = None
        last_gyroz = None

        while True:
            # Wait for a MAVLink message
            msg = vehicle.recv_match(blocking=True)

            if msg is None:
                continue

            # Handle RAW_IMU message
            if msg.get_type() == 'RAW_IMU':
                # Convert raw values to physical units
                accel_x = msg.xacc / 1000.0 * 9.81  # Convert milli-g to m/s²
                accel_y = msg.yacc / 1000.0 * 9.81  # Convert milli-g to m/s²
                accel_z = msg.zacc / 1000.0 * 9.81  # Convert milli-g to m/s²
                gyro_x = msg.xgyro / 1000.0  # Convert milli-rad/s to rad/s
                gyro_y = msg.ygyro / 1000.0  # Convert milli-rad/s to rad/s
                gyro_z = msg.zgyro / 1000.0  # Convert milli-rad/s to rad/s

                # Clamp and update tqdm for accelerometer
                if last_accelx != accel_x:
                    accelx_bar.n = min(max(accel_x, -accelx_bar.total), accelx_bar.total)
                    accelx_bar.refresh()
                    last_accelx = accel_x
                if last_accely != accel_y:
                    accely_bar.n = min(max(accel_y, -accely_bar.total), accely_bar.total)
                    accely_bar.refresh()
                    last_accely = accel_y
                if last_accelz != accel_z:
                    accelz_bar.n = min(max(accel_z, -accelz_bar.total), accelz_bar.total)
                    accelz_bar.refresh()
                    last_accelz = accel_z

                # Clamp and update tqdm for gyroscope
                if last_gyrox != gyro_x:
                    gyrox_bar.n = min(max(gyro_x, -gyrox_bar.total), gyrox_bar.total)
                    gyrox_bar.refresh()
                    last_gyrox = gyro_x
                if last_gyroy != gyro_y:
                    gyroy_bar.n = min(max(gyro_y, -gyroy_bar.total), gyroy_bar.total)
                    gyroy_bar.refresh()
                    last_gyroy = gyro_y
                if last_gyroz != gyro_z:
                    gyroz_bar.n = min(max(gyro_z, -gyroz_bar.total), gyroz_bar.total)
                    gyroz_bar.refresh()
                    last_gyroz = gyro_z

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