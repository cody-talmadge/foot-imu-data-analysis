import time
import board
import bitbangio
import digitalio
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

# Bitbangio is used instead of busio because the BNO08X IMU does not implement the I2C
# protocol correctly (it violates I2C's SDA-high to SCL-high setup-time requirement)
# Bitbangio (which is software based) appears to be more lenient with the I2C requirement
# allowing the program to (generally) function without issue
#
# More information: https://forums.adafruit.com/viewtopic.php?t=201558
i2c = bitbangio.I2C(board.SCL, board.SDA, frequency=400000, timeout=1000)
bno = BNO08X_I2C(i2c)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

# Change to reflect which foot the sensor is on - this affects the file name where the
# data is saved (and also the file name that's used in the API upload)
CONST_FOOT = "left"

# Set up the file name to store data to. This includes a file number that is based on the number of existing
# data files (to cause it to increment), plus a random component (to differentiate once files are removed
# from the device and file numbers repeat)
new_file_name = ""
while new_file_name == "" or new_file_name in os.listdir('/data/'):
    new_file_name = f"{CONST_FOOT}-{len(os.listdir('/data/')):07d}-{random.randint(100000,999999)}.csv"

print("Writing output to:", new_file_name)
print("Waiting for start button")

# Initialize the button (we'll use it to know that the user is ready for recording to start) and
# the pixel (we'll use it as a light to indicate basic status information to the user)
button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.DOWN
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.1

# The pixel is set red to let the user know it is not recording data
pixel.fill((255, 0, 0))

# Wait until the button is pressed to start the "calibration" phase (which is really just
# ignoring the first few IMU sensor readings while it calibrates/starts to read sensor data)
started = False
while not started:
    if not button.value:
        started=True
    time.sleep(0.1)

# Set the pixel to yellow while it is "calibrating"
pixel.fill((200, 80, 0))

# Take 10 readings to let it calibrate and the readings to settle
for a in range(10):
    quat_i, quat_j, quat_k, quat_real = bno.quaternion
    
# When "calibration" is complete, set the pixel to green
print("Calibration complete:")
pixel.fill((0, 255, 0))

# The start time is stored as seconds since the microcontroller was turned on
# We will later pull the current time from an API and back-calculate the start
# time as an actual time.  This is sent in the API call and displayed to the user
# when they're analyzing the data in the web UI to help them find the right file.
start_time = time.monotonic()

# Main recording loop
with open("/data/" + new_file_name, "a") as fp:
        while started:
            try:
                    # Read the quaternion data from the BNO08X
                    quat_i, quat_j, quat_k, quat_real = bno.quaternion

            except:
                # We got a read error - time to stop (and save the file)
                # Usually this is caused by someone touching one of the I2C
                # wires (their capacitance causes the clock issue to get worse)
                print("BNO08X read error!")
                break

            # Store the current time and the quaternion readings
            output_string = f"{time.monotonic()},{quat_i},{quat_j},{quat_k},{quat_real}"
            fp.write(output_string + "\n")
            print(output_string)

            # Check if the button has been pressed - if so, stop the recording
            if not button.value:
                started=False

# The pixel is set red once recording stops
pixel.fill((255, 0, 0))

# Below is code to get the current time from a web API
# It is heavily based on a tutorial from AdaFruit: https://learn.adafruit.com/adafruit-magtag/getting-the-date-time

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")

# Connect to the web API to get the time
try:
    # Get our username, key and desired timezone from the secrets file
    aio_username = secrets["aio_username"]
    aio_key = secrets["aio_key"]
    location = secrets.get("timezone", None)
    TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s&tz=%s" % (aio_username, aio_key, location)
    TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L"

    # Connect to our wifi network
    print("Connecting to %s"%secrets["ssid"])
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    print("Connected to %s!"%secrets["ssid"])
    print("My IP address is", wifi.radio.ipv4_address)

    # Get the time from the AdaFruit API
    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool, ssl.create_default_context())
    print("Fetching time")
    response = requests.get(TIME_URL)
    current_time = response.text
    #We will use the time_offset to calculate the time that the recording started
    time_offset = time.monotonic() - start_time
    date_format = "%Y-%m-%d %H:%M:%S.%f"
    print("Current Time: ", current_time)
    print("Time Offset: " , time_offset)
except:
    # Use this as a default time if no time information is available because we
    # were not able to connect to the API
    current_time = "2000-01-01 00:00:00.000000"
    time_offset = 0

# Store this file/time/offset in the list of unsaved files until we successfully upload it
with open("/data/unsaved_file_list.csv", "a") as fp:
    file_info = f"{new_file_name},{current_time},{time_offset}\n"
    fp.write(file_info)

# Next go through the list of unsaved files and upload them to the API
unsaved_file_list = open('/data/unsaved_file_list.csv', 'r')
unsaved_files = unsaved_file_list.readlines()
try:
    for file in unsaved_files:
        file_name, current_time, time_offset = str.split(file, ",")

        # Build out the skeleton of the json object that we'll include in the request
        request_object = {}
        request_object['file_name'] = file_name
        request_object['current_time'] = current_time
        request_object['time_offset'] = time_offset.strip()
        request_object['data'] = []
        request_object['data_points'] = 0

        # Store file data in the request object line-by-line
        sending_file = open("/data/" + file_name, "r")
        sending_file_lines = sending_file.readlines()
        for line in sending_file_lines:
            request_object['data_points'] += 1
            line_time, quat_i, quat_j, quat_k, quat_real = str.split(line, ",")
            request_object['data'].append([float(line_time), float(quat_i), float(quat_j), float(quat_k), float(str.strip(quat_real))])

            # Send the data to the API in 500 row chunks (so we don't run out of memory to store our request_object on the ESP32)
            if request_object['data_points'] >= 500:
                print(json.dumps(request_object))
                response = requests.post("https://j88641zc71.execute-api.us-east-2.amazonaws.com/items", json=request_object)
                print(response.text)
                request_object['data'] = []
                time.sleep(1)
                request_object['data_points'] = 0

        # Send any unsent data to the API
        response = requests.post("https://j88641zc71.execute-api.us-east-2.amazonaws.com/items", json=request_object)
        print(response.text)
        request_object['data'] = []

    # If we sent data for all the files without error, remove the list of unsaved files
    os.remove('/data/unsaved_file_list.csv')

    # Turn the pixel green so the user knows the log upload was successful
    pixel.fill((0, 127, 0))

except Exception as error:
    print("An exception occurred uploading to the API:", error)
    # Turn the pixel yellow so the user knows there was an issue uploading the log
    pixel.fill((200, 80, 0))

# Keep the pixel on for five seconds before the program finishes up so the user
# can view the upload status.
time.sleep(5)