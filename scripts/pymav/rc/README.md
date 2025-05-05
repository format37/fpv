By default, the RPi’s serial port (typically /dev/serial0 or /dev/ttyS0, mapped to GPIO14/TX and GPIO15/RX) might be disabled or repurposed (e.g., for console output or Bluetooth). If it’s not enabled, no serial devices will appear when your script runs.

    Action: Enable the serial port on the RPi:
        Run sudo raspi-config.
        Go to Interfacing Options > Serial.
        Select No for "Would you like a login shell to be accessible over serial?"
        Select Yes for "Would you like the serial port hardware to be enabled?"
        Finish and reboot the RPi with sudo reboot.
