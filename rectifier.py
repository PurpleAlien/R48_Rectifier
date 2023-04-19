import can
import struct
import subprocess

# This could be 0x0607FF83 or 0x06080783
arbitrationid = 0x0607FF83

# needs root/sudo access, or configure this part on the OS
def config(channel):
    subprocess.call(['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', '125000' , 'restart-ms' , '1500'])
    subprocess.call(['ip', 'link', 'set', 'up', channel])

# To convert floating point units to 4 bytes in a bytearray
def float_to_bytearray(f):
    value = hex(struct.unpack('<I', struct.pack('<f', f))[0])
    return bytearray.fromhex(value.lstrip('0x').rstrip('L'))


# Set the output voltage to the new value. 
# The 'fixed' parameter 
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
# Voltage between 41.0 and 58.5V - fan will go high below 48V! 
def set_voltage(channel, voltage, fixed=False):
    
    if voltage < 41.0 or voltage > 58.5:
        print('Voltage should be between 41.0V and 58.5V')    
        return

    bus = can.interface.Bus(bustype='socketcan', channel=channel, bitrate=125000)    

    b = float_to_bytearray(voltage)

    p = 0x21 if fixed == False else 0x24
    
    msg = can.Message(
        arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, p, b[0], b[1], b[2], b[3]], is_extended_id=True
    )
        
    try:
        bus.send(msg)
        print(f"Voltage set on {bus.channel_info}")
    except can.CanError:
        print("Voltage NOT set")


# The output current is set in percent to the rated value of the rectifier written in the manual
# Possible values for 'current': 10% - 121% (rated current in the datasheet = 121%)
# The 'fixed' parameter
#  - if True makes the change permanent ('offline command')
#  - if False the change is temporary (30 seconds per command received, 'online command', repeat at 15 second intervals).
def set_current(channel, current, fixed=False):
    
    if current < 10 or current > 121:
        print('Current should be between 10% and 121%')    
        return

    bus = can.interface.Bus(bustype='socketcan', channel=channel, bitrate=125000)

    
    limit = current/100 #floating point 0.1 to 1.21
    b = float_to_bytearray(limit)

    p = 0x22 if fixed == False else 0x19

    msg = can.Message(
        arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, p, b[0], b[1], b[2], b[3]], is_extended_id=True
    )
     
    try:
        bus.send(msg)
        print(f"Current set on {bus.channel_info}")
    except can.CanError:
        print("Current NOT set")

# Time to ramp up the rectifiers output voltage to the set voltage value, and enable/disable
def walk_in(channel, time=0, enable=False):

    bus = can.interface.Bus(bustype='socketcan', channel=channel, bitrate=125000)

    if enable == False:
        msg = can.Message(
            arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00], is_extended_id=True
        ) 
        
        try:
            bus.send(msg)
            print(f"Ramp up disabled on {bus.channel_info}")
        except can.CanError:
            print("Ramp up NOT set")
        
        return

    else:
        msg = can.Message(
            arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x32, 0x00, 0x01, 0x00, 0x00], is_extended_id=True
        )
    
        try:
            bus.send(msg)
            print(f"Ramp up enabled on {bus.channel_info}")
        except can.CanError:
            print("Ramp up NOT set")
        
        b = float_to_bytearray(time)

        msg = can.Message(
            arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x29, b[0], b[1], b[2], b[3]], is_extended_id=True
        )

        try:
            bus.send(msg)
            print(f"Ramp up time set on {bus.channel_info}")
        except can.CanError:
            print("Ramp up NOT set")

# AC input current limit (called Diesel power limit): gives the possibility to reduce the overall power of the rectifier
def limit_input(channel, current):

    bus = can.interface.Bus(bustype='socketcan', channel=channel, bitrate=125000)
    
    b = float_to_bytearray(current)
    
    msg = can.Message(
        arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x1A, b[0], b[1], b[2], b[3]], is_extended_id=True
    )

    try:
        bus.send(msg)
        print(f"Input limited on {bus.channel_info}")
    except can.CanError:
        print("Input limit NOT set")

# Restart after overvoltage enable/disable
def restart_overvoltage(channel, state=False):

    bus = can.interface.Bus(bustype='socketcan', channel=channel, bitrate=125000)
    
    if state == False:
        msg = can.Message(
            arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x39, 0x00, 0x00, 0x00, 0x00], is_extended_id=True
        )
    
        try:
            bus.send(msg)
            print(f"Restart on overvoltage disabled on {bus.channel_info}")
        except can.CanError:
            print("Restart condition NOT set")
    else:
        msg = can.Message(
            arbitration_id=arbitrationid, data=[0x03, 0xF0, 0x00, 0x39, 0x00, 0x01, 0x00, 0x00], is_extended_id=True
        )
    
        try:
            bus.send(msg)
            print(f"Restart on overvoltage enabled on {bus.channel_info}")
        except can.CanError:
            print("Restart condition NOT set")


if __name__ == "__main__":
    config('can0')
    set_voltage('can0', 52.0, False)
    #set_current('can0', 10.0, False)
    #walk_in('can0', False)
    #limit_input('can0', 10.0)
    #restart_overvoltage('can0', False)
