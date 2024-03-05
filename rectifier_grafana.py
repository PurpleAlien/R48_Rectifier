import sys
import can
import struct
import subprocess
import time
import os

# CAN stuff
ARBITRATION_ID_READ = 0x06000783
BITRATE = 125000

CAN_INTERFACE = 'can0'

# individual properties to read out:
# 01 : output voltage
# 02 : output current
# 03 : output current limit
# 04 : temperature in C
# 05 : supply voltage

# Reads all of the above and a few more at once
READ_ALL = [0x00, 0xF0, 0x00, 0x80, 0x46, 0xA5, 0x34, 0x00] 

# needs root/sudo access, or configure this part on the OS
def config(channel):
    subprocess.call(['ip', 'link', 'set', 'down', channel])
    subprocess.call(['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', str(BITRATE), 'restart-ms', '1500'])
    subprocess.call(['ip', 'link', 'set', 'up', channel])

# To convert floating point units to 4 bytes in a bytearray
def float_to_bytearray(f):
    value = hex(struct.unpack('<I', struct.pack('<f', f))[0])
    return bytearray.fromhex(value.lstrip('0x').rstrip('L'))

# CAN message receiver
def receive_can_message(channel):
    try:
        with can.interface.Bus(receive_own_messages=True, bustype='socketcan', channel=channel, bitrate=BITRATE) as bus:
          can.Notifier(bus, [can_listener])
          
          # Keep sending requests for all data every second 
          while True:
            # All at once
            msg = can.Message(arbitration_id=ARBITRATION_ID_READ, data=READ_ALL, is_extended_id=True)
            bus.send(msg)
            # Every 10 seconds
            time.sleep(10.0)

    except can.CanError:
        print("Receive went wrong")

# CAN receiver listener
def can_listener(msg):
    if not hasattr(can_listener, "counter"):
        can_listener.counter = 0
    
    v_out = 0.0
    i_out = 0.0
    temp = 0.0
    v_in = 0.0
    i_limit = 0.0

    # Is it a response to our request
    if msg.data[0] == 0x41:
        # Convert value to float (it's the same for all)
        val = struct.unpack('>f', msg.data[4:8])[0]
        # Check what data it is
        match msg.data[3] :
            case 0x01:
                v_out = val
                can_listener.counter += 1
            case 0x02:
                i_out = val
                can_listener.counter += 1
            case 0x03:
                i_limit = val
                can_listener.counter += 1
            case 0x04:
                temp = val
                can_listener.counter += 1
            case 0x05:
                v_in = val
                can_listener.counter += 1

    # Write to the file
    if can_listener.counter >= 5:
        fileObj = open('/ramdisk/R48_RECTIFIER.prom.tmp', mode='w')

        valName  = "mode=\"outputV\""
        valName  = "{" + valName + "}"
        dataStr  = f"R48_RECTIFIER{valName} {v_out}"
        print(dataStr, file=fileObj)         

        valName  = "mode=\"outputI\""
        valName  = "{" + valName + "}"
        dataStr  = f"R48_RECTIFIER{valName} {i_out}"
        print(dataStr, file=fileObj)         

        valName  = "mode=\"limitI\""
        valName  = "{" + valName + "}"
        dataStr  = f"R48_RECTIFIER{valName} {i_limit}"
        print(dataStr, file=fileObj)         

        valName  = "mode=\"temp\""
        valName  = "{" + valName + "}"
        dataStr  = f"R48_RECTIFIER{valName} {temp}"
        print(dataStr, file=fileObj)         

        valName  = "mode=\"inputV\""
        valName  = "{" + valName + "}"
        dataStr  = f"R48_RECTIFIER{valName} {v_in}"
        print(dataStr, file=fileObj)         

        fileObj.flush()
        fileObj.close()
        outLine = os.system('/bin/mv /ramdisk/R48_RECTIFIER.prom.tmp /ramdisk/R48_RECTIFIER.prom')

        can_listener.counter = 0

if __name__ == "__main__":
    config(CAN_INTERFACE)
    receive_can_message(CAN_INTERFACE)

