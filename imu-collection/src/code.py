import time
import board
import busio
import bitbangio
import math
import digitalio
import microcontroller
import neopixel
import os
import random
import ipaddress
import ssl
import wifi
import socketpool
import adafruit_requests
import secrets
import json

from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
from adafruit_bno08x.i2c import BNO08X_I2C

# Bitbangio is used instead of busio because the bno08x does not implement the I2C
# protocol correctly (it violates I2C's SDA-high to SCL-high setup-time requirement)
# Bitbangio (which is software based) appears to be more lenient with the I2C requirement
# allowing the program to (generally) function without issue
#
# More information: https://forums.adafruit.com/viewtopic.php?t=201558
i2c = bitbangio.I2C(board.SCL, board.SDA, frequency=400000, timeout=1000)
bno = BNO08X_I2C(i2c)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

# Change to reflect which foot the sensor is on
CONST_FOOT = "left"

# Set up the file name to store data to. This includes a file number that is based on the number of existing
# data files (to cause it to increment), plus a random component (to differentiate once files are removed
# from the device)
new_file_name = ""
while new_file_name == "" or new_file_name in os.listdir('/data/'):
    new_file_name = f"{CONST_FOOT}-{len(os.listdir('/data/')):07d}-{random.randint(100000,999999)}.csv"

print("Writing output to:", new_file_name)
print("Waiting for start button")

button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.DOWN

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.1

# The pixel starts at red to let the user know it is not recording data
pixel.fill((255, 0, 0))

# The button press starts the "calibration" phase (which is really just ignoring the first few IMU sensor
# readings while it calibrates)
started = False
while not started:
    if not button.value:
        started=True
    time.sleep(0.1)

# The pixel is yellow while it is calibrating
pixel.fill((200, 80, 0))

print("Calibrating")
roll_adjust = None
pitch_adjust = None
yaw_adjust = None

quat_adjust = []

for a in range(10):
    quat_i, quat_j, quat_k, quat_real = bno.quaternion
    
print("Calibration complete:")

pixel.fill((0, 255, 0))

with open("/data/" + new_file_name, "a") as fp:
        while started:
            try:
                    quat_i, quat_j, quat_k, quat_real = bno.quaternion
            except:
                    # We got a read error - time to stop (and save the file)
                    # Usually this is caused by someone touching one of the I2C
                    # wires (their capacitance causes the clock issue to get worse)
                print("BNO08X read error!")
                break
            output_string = f"{time.monotonic()},{quat_i},{quat_j},{quat_k},{quat_real}"
            fp.write(output_string + "\n")
            print(output_string)
            if not button.value:
                started=False

# The pixel is red once recording stops
pixel.fill((255, 0, 0))

# Code to get the time is from AdaFruit: https://learn.adafruit.com/adafruit-magtag/getting-the-date-time

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")

# If we can't connect we won't be able to store the time
try:
    # Get our username, key and desired timezone
    aio_username = secrets["aio_username"]
    aio_key = secrets["aio_key"]
    location = secrets.get("timezone", None)
    TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s&tz=%s" % (aio_username, aio_key, location)
    TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L"

    print("Connecting to %s"%secrets["ssid"])
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    print("Connected to %s!"%secrets["ssid"])
    print("My IP address is", wifi.radio.ipv4_address)

    ipv4 = ipaddress.ip_address("8.8.4.4")

    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool, ssl.create_default_context())

    print("Fetching time")
    response = requests.get(TIME_URL)
    current_time = response.text
    print(current_time)
    time_offset = time.monotonic()
    print(time_offset)
except:
    current_time = "Unknown"
    time_offset = time.monotonic()

# Store this file in the unsaved file list until we successfully upload it
with open("/data/unsaved_file_list.csv", "a") as fp:
    file_info = f"{new_file_name},{current_time},{time_offset}\n"
    fp.write(file_info)

unsaved_file_list = open('/data/unsaved_file_list.csv', 'r')
unsaved_files = unsaved_file_list.readlines()

try:
    for file in unsaved_files:
        file_name, file_time, file_time_offset = str.split(file, ",")

        request_object = {}
        request_object['file_name'] = file_name
        request_object['file_time'] = file_time
        request_object['file_time_offset'] = file_time_offset
        request_object['data'] = []

        sending_file = open("/data/" + file_name, "r")
        sending_file_lines = sending_file.readlines()
        line_count = 0
        for line in sending_file_lines:
            line_count += 1
            line_time, quat_i, quat_j, quat_k, quat_real = str.split(line, ",")
            line_object = {}
            line_object['line_time'] = line_time.strip()
            line_object['quat_i'] = quat_i
            line_object['quat_j'] = quat_j
            line_object['quat_k'] = quat_k
            line_object['quat_real'] = quat_real
            request_object['data'].append(line_object)
            if line_count == 50:
                response = requests.post("https://j88641zc71.execute-api.us-east-2.amazonaws.com/items", json=request_object)
                print(response.text)
                print(json.dumps(request_object))
                request_object['data'] = []
                time.sleep(5)
        
        response = requests.post("https://j88641zc71.execute-api.us-east-2.amazonaws.com/items", json=request_object)
        print(response.text)
        print(json.dumps(request_object))
        request_object['data'] = []
        time.sleep(5)

        print(file_name, file_time, file_time_offset)
    os.remove('/data/unsaved_file_list.csv')
except:
    print("Error uploading files to API")