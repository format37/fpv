import time
import math
from pymavlink import mavutil

def connect_to_vehicle(port='COM4', baud=1500000):
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

def send_rc_override(connection, ch2_value):
    """
    Send RC override for CH2 to control elevons.
    ch2_value is the PWM value for channel 2 (1000-2000 µs).
    Other channels are set to 0 (no override).
    """
    connection.mav.rc_channels_override_send(
        connection.target_system,
        connection.target_component,
        0,          # CH1
        ch2_value,  # CH2 (elevons)
        0,          # CH3
        0,          # CH4
        0,          # CH5
        0,          # CH6
        0,          # CH7
        0           # CH8
    )

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Auto height control using rangefinder and vtail elevons (CH2).")
    parser.add_argument('--port', type=str, default='/dev/ttyS0', help='Serial port to connect to (default: /dev/ttyS0)')
    parser.add_argument('--baud', type=int, default=1500000, help='Baud rate for serial connection (default: 1500000)')
    parser.add_argument('--goal', type=float, default=1.0, help='Goal height in meters (default: 1.0)')
    parser.add_argument('--kp', type=float, default=400.0, help='Proportional gain for controller (default: 400.0)')
    args = parser.parse_args()

    vehicle = connect_to_vehicle(args.port, args.baud)
    request_data_streams(vehicle)

    center_pwm = 1500  # Neutral PWM value for CH2
    min_pwm = 1000
    max_pwm = 2000
    goal_height = args.goal
    kp = args.kp

    print(f"Auto height control started. Goal: {goal_height} m. Press Ctrl+C to stop.")

    try:
        while True:
            msg = vehicle.recv_match(type='RANGEFINDER', blocking=True, timeout=1)
            if msg is None:
                print("No RANGEFINDER data received.")
                continue
            current_height = msg.distance
            error = goal_height - current_height
            control = kp * error
            ch2_pwm = int(center_pwm - control)
            ch2_pwm = max(min_pwm, min(max_pwm, ch2_pwm))
            send_rc_override(vehicle, ch2_pwm)
            print(f"\rHeight: {current_height:.2f} m | Error: {error:.2f} | CH2 PWM: {ch2_pwm}", end="")
            # time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Sending neutral RC override and closing connection...")
        send_rc_override(vehicle, center_pwm)
        vehicle.close()
        print("Connection closed.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        send_rc_override(vehicle, center_pwm)
        vehicle.close()
        print(f"Error occurred at line {e.__traceback__.tb_lineno}: {str(e)}")
        print("Connection closed.")

if __name__ == "__main__":
    main()