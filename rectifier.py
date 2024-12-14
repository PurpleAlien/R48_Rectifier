import sys
import can
import struct
import subprocess
import time
import argparse

# CAN stuff
ARBITRATION_ID = 0x0607FF83 # or 06080783 ?
ARBITRATION_ID_READ = 0x06000783
BITRATE = 125000

# individual properties to read out, data: 0x01, 0xF0, 0x00, p, 0x00, 0x00, 0x00, 0x00 with p:
# 01 : output voltage
# 02 : output current
# 03 : output current limit
# 04 : temperature in C
# 05 : supply voltage
READ_COMMANDS = [0x01, 0x02, 0x03, 0x04, 0x05]

# Reads all of the above and a few more at once
READ_ALL = [0x00, 0xF0, 0x00, 0x80, 0x46, 0xA5, 0x34, 0x00]

# 62.5A is the nominal current of Emerson/Vertiv R48-3000e and corresponds to 121%
OUTPUT_CURRENT_RATED_VALUE = 62.5
OUTPUT_CURRENT_RATED_PERCENTAGE_MIN = 10
OUTPUT_CURRENT_RATED_PERCENTAGE_MAX = 121
OUTPUT_VOLTAGE_MIN = 41.0
OUTPUT_VOLTAGE_MAX = 58.5
OUTPUT_CURRENT_MIN = 5.5
OUTPUT_CURRENT_MAX = OUTPUT_CURRENT_RATED_VALUE

# Helper Functions

# Needs root/sudo access, or configure this part on the OS
def config(channel):
    """Configure the CAN interface."""
    try:
        subprocess.run(['ip', 'link', 'set', 'down', channel], check=True)
        subprocess.run(['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', str(BITRATE), 'restart-ms', '1500'], check=True)
        subprocess.run(['ip', 'link', 'set', 'up', channel], check=True)
        print(f"Configured CAN interface: {channel}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to configure CAN interface {channel}: {e}")

# Converts a few possible strings to boolean
def str_to_bool(value):
    """Parse string to boolean (case-insensitive)."""
    if isinstance(value, bool):
        return value
    if value.lower() in {'true', 't', 'yes', '1'}:
        return True
    elif value.lower() in {'false', 'f', 'no', '0'}:
        return False
    else:
        raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")

# To convert floating point units to 4 bytes in a bytearray
def float_to_bytearray(f):
    """Convert a float to a 4-byte array."""
    return bytearray(struct.pack('<f', f))

# Check if options passed are within accepted range
def validate_range(value, min_val, max_val, name):
    """Validate that a value is within the specified range."""
    if not (min_val <= value <= max_val):
        raise ValueError(f"{name} must be between {min_val} and {max_val}. Got {value}.")
    return value

# Get the bus and send data to the specified CAN bus
def send_can_message(channel, data):
    """Send a message to the CAN bus."""
    try:
        with can.interface.Bus(bustype='socketcan', channel=channel, bitrate=BITRATE) as bus:
            msg = can.Message(arbitration_id=ARBITRATION_ID, data=data, is_extended_id=True)
            bus.send(msg)
            print(f"Command sent on {bus.channel_info}")
    except can.CanError as e:
        print(f"CAN message send error: {e}")

# CAN message receiver
def receive_can_message(channel):
    """Receive and print messages from the CAN bus."""
    try:
        with can.interface.Bus(receive_own_messages=True, bustype='socketcan', channel=channel, bitrate=BITRATE) as bus:
            #print_listener = can.Printer()
            #can.Notifier(bus, [print_listener])
            can.Notifier(bus, [can_listener])

            # Keep sending requests for all data every second
            while True:
                # Individually
                #for p in READ_COMMANDS:
                #    data = [0x01, 0xF0, 0x00, p, 0x00, 0x00, 0x00, 0x00]
                #    msg = can.Message(arbitration_id=ARBITRATION_ID_READ, data=data, is_extended_id=True)
                #    bus.send(msg)
                #    time.sleep(0.1)
                
                # All at once
                msg = can.Message(arbitration_id=ARBITRATION_ID_READ, data=READ_ALL, is_extended_id=True)
                bus.send(msg)
                time.sleep(1.0)
    except can.CanError as e:
        print(f"CAN message receive error: {e}")

# CAN receiver listener
def can_listener(msg):
    """Process received CAN messages."""
    # Is it a response to our request
    if msg.data[0] == 0x41:
        # Convert value to float (it's the same for all)
        val = struct.unpack('>f', msg.data[4:8])[0]
        # Check what data it is
        match msg.data[3]:
            case 0x01: print(f"Vout (VDC): {val}")
            case 0x02: print(f"Iout (IDC): {val}")
            case 0x03: print(f"Output Current Limit: {val}")
            case 0x04: print(f"Temp (°C): {val}")
            case 0x05: print(f"Vin (VAC): {val}")

# Set the output voltage to the new value. 
# The 'fixed' parameter 
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
# Voltage between 41.0 and 58.5V - fan will go high below 48V!
def set_voltage(channel, voltage, fixed=False):
    """Set output voltage."""
    validate_range(voltage, OUTPUT_VOLTAGE_MIN, OUTPUT_VOLTAGE_MAX, "Voltage")
    cmd = 0x24 if fixed else 0x21
    send_can_message(channel, [0x03, 0xF0, 0x00, cmd, *float_to_bytearray(voltage)])

# The output current is set in percent to the rated value of the rectifier written in the manual
# Possible values for 'current': 10% - 121% (rated current in the datasheet = 121%)
# The 'fixed' parameter
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals)
def set_current_percentage(channel, percent, fixed=False):
    """Set output current as a percentage."""
    validate_range(percent, OUTPUT_CURRENT_RATED_PERCENTAGE_MIN, OUTPUT_CURRENT_RATED_PERCENTAGE_MAX, "Current percentage")
    cmd = 0x19 if fixed else 0x22
    send_can_message(channel, [0x03, 0xF0, 0x00, cmd, *float_to_bytearray(percent / 100)])

# The output current is set as a value
# Possible values for 'current': 5.5A - 62.5A
# The 'fixed' parameter
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
def set_current_value(channel, current, fixed=False):
    """Set output current in amps."""
    validate_range(current, OUTPUT_CURRENT_MIN, OUTPUT_CURRENT_MAX, "Current")
    percent = (current / OUTPUT_CURRENT_RATED_VALUE) * OUTPUT_CURRENT_RATED_PERCENTAGE_MAX
    set_current_percentage(channel, percent, fixed)

# Time to ramp up the rectifiers output voltage to the set voltage value, and enable/disable
def walk_in(channel, time=0, enable=False):
    """Enable or disable walk-in functionality."""
    data = [0x03, 0xF0, 0x00, 0x32, 0x00, 0x01 if enable else 0x00, 0x00, 0x00]
    if enable:
        data.extend(float_to_bytearray(time))
    send_can_message(channel, data)

# AC input current limit (called Diesel power limit): gives the possibility to reduce the overall power of the rectifier
def limit_input(channel, current):
    """Set AC input current limit."""
    send_can_message(channel, [0x03, 0xF0, 0x00, 0x1A, *float_to_bytearray(current)])

# Restart after overvoltage enable/disable
def restart_overvoltage(channel, state=False):
    """Enable or disable restart after overvoltage."""
    send_can_message(channel, [0x03, 0xF0, 0x00, 0x39, 0x00, 0x01 if state else 0x00, 0x00, 0x00])

# Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control Emerson/Vertiv Rectifiers via CAN.")
    parser.add_argument("-m", "--mode", choices=["set", "get"], help="Operation mode: set or get")
    parser.add_argument("-v", "--voltage", type=float, help="Set output voltage (41.0V - 58.5V)")
    parser.add_argument("-cv", "--current_value", type=float, help="Set output current in amps (5.5A - 62.5A)")
    parser.add_argument("-cp", "--current_percent", type=float, help="Set output current as percentage (10%% - 121%%)")
    parser.add_argument("-p", "--permanent", action="store_true", help="Make settings permanent")
    parser.add_argument("-I", "--interface", default="can0", help="CAN interface (default: can0)")
    parser.add_argument("-C", "--configure", action="store_true", help="Configure CAN interface")
    parser.add_argument("--walk_in", type=str_to_bool, help="Enable or disable walk-in")
    parser.add_argument("--walk_in_time", type=float, help="Walk-in ramp-up time (seconds)")
    parser.add_argument("--limit_input", type=float, help="Set AC input current limit (amps)")
    parser.add_argument("--restart_overvoltage", type=str_to_bool, help="Enable or disable restart after overvoltage")

    args = parser.parse_args()

    if args.configure:
        config(args.interface)

    if args.mode == "set":
        if args.voltage:
            set_voltage(args.interface, args.voltage, args.permanent)
        if args.current_value:
            set_current_value(args.interface, args.current_value, args.permanent)
        if args.current_percent:
            set_current_percentage(args.interface, args.current_percent, args.permanent)
        if args.walk_in is not None:
            walk_in(args.interface, time=args.walk_in_time or 0, enable=args.walk_in)
        if args.limit_input:
            limit_input(args.interface, args.limit_input)
        if args.restart_overvoltage is not None:
            restart_overvoltage(args.interface, state=args.restart_overvoltage)
    elif args.mode == "get":
        receive_can_message(args.interface)

