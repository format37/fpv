import time
import math
from pymavlink import mavutil

def connect_to_vehicle(port='COM4', baud=1500000):
    print(f"Connecting to vehicle on {port} at {baud} baud...")
    connection = mavutil.mavlink_connection(port, baud=baud)
    connection.wait_heartbeat()
    print("Heartbeat received. Connection established.")
    return connection

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
    # Establish connection
    vehicle = connect_to_vehicle('/dev/ttyACM0', 1500000)
    try:
        # Sinusoid parameters
        amplitude = 300  # PWM amplitude (±300 from center)
        center_pwm = 1500  # Neutral PWM value for CH2
        frequency = 0.5  # Hz (one cycle every 2 seconds)

        print("Sending sinusoidal RC override to CH2 for elevon control... (Press Ctrl+C to stop)")

        start_time = time.time()

        while True:
            # Calculate current time offset
            elapsed_time = time.time() - start_time

            # Generate sinusoidal signal for CH2
            angle = 2 * math.pi * frequency * elapsed_time
            signal = math.sin(angle) * amplitude

            # Calculate CH2 PWM value
            ch2_pwm = int(center_pwm + signal)

            # Clamp PWM value to safe range (1000-2000)
            ch2_pwm = max(1000, min(2000, ch2_pwm))

            # Send RC override for CH2
            send_rc_override(vehicle, ch2_pwm)

            # Print current value for monitoring
            print(f"\rCH2 PWM (Elevons): {ch2_pwm:.0f}", end="")

            # Small delay to prevent overwhelming the system
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Sending neutral RC override and closing connection...")
        # Send neutral CH2 value before exiting
        send_rc_override(vehicle, 1500)
        vehicle.close()
        print("Connection closed.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        # Send neutral CH2 value before exiting
        send_rc_override(vehicle, 1500)
        vehicle.close()
        print(f"Error occurred at line {e.__traceback__.tb_lineno}: {str(e)}")
        print("Connection closed.")

if __name__ == "__main__":
    main()