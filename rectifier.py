import sys
import can
import struct
import subprocess
import time
import argparse

# CAN stuff
ARBITRATION_ID = 0x0607FF83
BITRATE = 125000

# 62.5A is the nominal current of Emerson/Vertiv R48-3000e and corresponds to 121%
OUTPUT_CURRENT_RATED_VALUE = 62.5
OUTPUT_CURRENT_RATED_PERCENTAGE_MIN = 10
OUTPUT_CURRENT_RATED_PERCENTAGE_MAX = 121
OUTPUT_CURRENT_RATED_PERCENTAGE = 121
OUTPUT_VOLTAGE_MIN = 41.0
OUTPUT_VOLTAGE_MAX = 58.5
OUTPUT_CURRENT_MIN = 5.5 # 10%, rounded up to nearest 0.5V 
OUTPUT_CURRENT_MAX = OUTPUT_CURRENT_RATED_VALUE

# needs root/sudo access, or configure this part on the OS
def config(channel):
    subprocess.call(['ip', 'link', 'set', 'down', channel])
    subprocess.call(['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', str(BITRATE), 'restart-ms', '1500'])
    subprocess.call(['ip', 'link', 'set', 'up', channel])

# To convert floating point units to 4 bytes in a bytearray
def float_to_bytearray(f):
    value = hex(struct.unpack('<I', struct.pack('<f', f))[0])
    return bytearray.fromhex(value.lstrip('0x').rstrip('L'))

# Get the bus and send data to the specified CAN bus
def send_can_message(channel, data):
    try:
        with can.interface.Bus(bustype='socketcan', channel=channel, bitrate=BITRATE) as bus:
            msg = can.Message(arbitration_id=ARBITRATION_ID, data=data, is_extended_id=True)
            bus.send(msg)
            print(f"Command sent on {bus.channel_info}")
    except can.CanError:
        print("Command NOT sent")

# Set the output voltage to the new value. 
# The 'fixed' parameter 
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
# Voltage between 41.0 and 58.5V - fan will go high below 48V!
def set_voltage(channel, voltage, fixed=False):
    if OUTPUT_VOLTAGE_MIN <= voltage <= OUTPUT_VOLTAGE_MAX:
        b = float_to_bytearray(voltage)
        p = 0x21 if not fixed else 0x24
        data = [0x03, 0xF0, 0x00, p, *b]
        send_can_message(channel, data)
    else:
        print(f"Voltage should be between {OUTPUT_VOLTAGE_MIN}V and {OUTPUT_VOLTAGE_MAX}V")

# The output current is set in percent to the rated value of the rectifier written in the manual
# Possible values for 'current': 10% - 121% (rated current in the datasheet = 121%)
# The 'fixed' parameter
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
def set_current_percentage(channel, current, fixed=False):
    if OUTPUT_CURRENT_RATED_PERCENTAGE_MIN <= current <= OUTPUT_CURRENT_RATED_PERCENTAGE_MAX:
        limit = current / 100
        b = float_to_bytearray(limit)
        p = 0x22 if not fixed else 0x19
        data = [0x03, 0xF0, 0x00, p, *b]
        send_can_message(channel, data)
    else:
        print(f"Current should be between {OUTPUT_CURRENT_RATED_PERCENTAGE_MIN}% and {OUTPUT_CURRENT_RATED_PERCENTAGE_MAX}%")

# The output current is set as a value
# Possible values for 'current': 5.5A - 62.5A
# The 'fixed' parameter
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
def set_current_value(channel, current, fixed=False):
    
    if OUTPUT_CURRENT_MIN <= current <= OUTPUT_CURRENT_MAX:
        # 62.5A is the nominal current of Emerson/Vertiv R48-3000e and corresponds to 121%
        percentage = (current/OUTPUT_CURRENT_RATED_VALUE)*OUTPUT_CURRENT_RATED_PERCENTAGE
        set_current_percentage(channel , percentage, fixed)
    else:
        print(f"Current should be between {OUTPUT_CURRENT_MIN}A and {OUTPUT_CURRENT_MAX}A")



# Time to ramp up the rectifiers output voltage to the set voltage value, and enable/disable
def walk_in(channel, time=0, enable=False):
    if not enable:
        data = [0x03, 0xF0, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00]
    else:
        data = [0x03, 0xF0, 0x00, 0x32, 0x00, 0x01, 0x00, 0x00]
        b = float_to_bytearray(time)
        data.extend(b)
    send_can_message(channel, data)

# AC input current limit (called Diesel power limit): gives the possibility to reduce the overall power of the rectifier
def limit_input(channel, current):
    b = float_to_bytearray(current)
    data = [0x03, 0xF0, 0x00, 0x1A, *b]
    send_can_message(channel, data)

# Restart after overvoltage enable/disable
def restart_overvoltage(channel, state=False):
    if not state:
        data = [0x03, 0xF0, 0x00, 0x39, 0x00, 0x00, 0x00, 0x00]
    else:
        data = [0x03, 0xF0, 0x00, 0x39, 0x00, 0x01, 0x00, 0x00]
    send_can_message(channel, data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set/Get Parameters from Emerson/Vertiv Rectifiers.')

    parser.add_argument('-m', '--mode', default="none",
                    help='Mode of Operation (set/get)')

    parser.add_argument('-v', '--voltage', type=float,
                    help='Voltage Set Point of the Charger (41.0VDC - 58.5VDV)')

    parser.add_argument('-cv', '--current_value', type=float,
                    help='Current Set Point of the Charger (5.5ADC - 62.5ADC)')
    parser.add_argument('-cp', '--current_percent', type=float,
                    help='Current Set Point of the Charger in percent (10% - 121%)')

    parser.add_argument('-p', '--permanent', action='store_true',
                    help='Make settings permanent')

    parser.add_argument('-I', '--interface', default="can0",
                    help='Adapter Interface (can0, can1, ...)')

    parser.add_argument('-C', '--configure', action='store_true',
                    help='Configure link (bitrate, bring up interface) as well') 

    args = parser.parse_args()    

    if args.configure == True:
        config(args.interface)    

    if args.mode == "set":
        print(f"{args.permanent}")
        if args.voltage is not None:
            set_voltage(args.interface , args.voltage , args.permanent)
        if args.current_value is not None:
            set_current_value(args.interface , args.current_value , args.permanent)
        if args.current_percent is not None:
            set_current_percentage(args.interface , args.current_percent , args.permanent)
    elif args.mode== "get":
        print("Mode 'get' not implemented yet")

    #config('can0')
    #set_voltage('can0', 52.0, False)
    #set_current('can0', 10.0, False)
    #walk_in('can0', False)
    #limit_input('can0', 10.0)
    #restart_overvoltage('can0', False)
