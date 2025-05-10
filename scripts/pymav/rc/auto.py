import time
import math
from pymavlink import mavutil
import time

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
    parser.add_argument('--goal', type=float, default=0.5, help='Goal height in meters (default: 1.0)')
    parser.add_argument('--kp', type=float, default=400.0, help='Proportional gain for controller (default: 400.0)')
    args = parser.parse_args()

    vehicle = connect_to_vehicle(args.port, args.baud)
    request_data_streams(vehicle)

    center_pwm = 1500  # Neutral PWM value for CH2
    min_pwm = 989
    max_pwm = 2013
    goal_height = args.goal
    kp = args.kp

    print(f"Auto height control started. Goal: {goal_height} m. Press Ctrl+C to stop.")

    # Frequency metrics
    loop_count = 0
    rangefinder_count = 0
    last_rangefinder_time = time.time()
    last_loop_time = time.time()
    loop_freq = 0.0
    rangefinder_freq = 0.0

    try:
        while True:
            loop_start = time.time()
            msg = vehicle.recv_match(type='RANGEFINDER', blocking=True, timeout=1)
            loop_count += 1
            now = time.time()
            # Update loop frequency every second
            if now - last_loop_time >= 1.0:
                loop_freq = loop_count / (now - last_loop_time)
                loop_count = 0
                last_loop_time = now
            if msg is None:
                print(f"\rNo RANGEFINDER data received. | Loop Hz: {loop_freq:.1f} | RF Hz: {rangefinder_freq:.1f}   ", end="")
                continue
            rangefinder_count += 1
            # Update rangefinder frequency every second
            if now - last_rangefinder_time >= 1.0:
                rangefinder_freq = rangefinder_count / (now - last_rangefinder_time)
                rangefinder_count = 0
                last_rangefinder_time = now
            if msg.distance == 0:
                print(f"\rInvalid RANGEFINDER value (0). Skipping. | Loop Hz: {loop_freq:.1f} | RF Hz: {rangefinder_freq:.1f}   ", end="")
                continue
            current_height = msg.distance
            error = goal_height - current_height
            control = kp * error
            # ch2_pwm = int(center_pwm + control) # Reversed
            ch2_pwm = int(center_pwm - control)
            ch2_pwm = max(min_pwm, min(max_pwm, ch2_pwm))
            send_rc_override(vehicle, ch2_pwm)
            print(f"\rHeight: {current_height:.2f} m | Error: {error:.2f} | CH2 PWM: {ch2_pwm} | Loop Hz: {loop_freq:.1f} | RF Hz: {rangefinder_freq:.1f}   ", end="")
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